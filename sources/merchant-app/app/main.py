"""Merchant onboarding API (FastAPI + MySQL).

Every write here becomes a row change in MySQL, which Debezium streams to Kafka (Step 6).
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db import engine

app = FastAPI(title="FraudPulse merchant app", version="0.1.0")

MYSQL_DUPLICATE_KEY = 1062
MYSQL_MISSING_PARENT_ROW = 1452


class Status(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


# Which status changes are allowed. REJECTED and CLOSED are final.
ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.PENDING: {Status.ACTIVE, Status.REJECTED},
    Status.ACTIVE: {Status.SUSPENDED, Status.CLOSED},
    Status.SUSPENDED: {Status.ACTIVE, Status.CLOSED},
    Status.REJECTED: set(),
    Status.CLOSED: set(),
}

MerchantId = Annotated[str, Path(pattern=r"^M[0-9]{6}$")]


class MerchantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are an error, not ignored

    merchant_id: str = Field(pattern=r"^M[0-9]{6}$")
    legal_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=100)
    category_code: str = Field(pattern=r"^[A-Z_]{1,32}$")
    city: str = Field(min_length=1, max_length=64)
    # Synthetic data only: contact addresses must use the reserved example.com domain.
    contact_email: str | None = Field(
        default=None, max_length=254, pattern=r"^[A-Za-z0-9._-]+@example\.com$"
    )


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    version: int = Field(ge=1, description="The version you read. Stale versions are refused.")


class Merchant(BaseModel):
    merchant_id: str
    legal_name: str
    display_name: str
    upi_id: str
    category_code: str
    city: str
    status: Status
    contact_email: str | None
    version: int
    created_at: datetime
    updated_at: datetime


MERCHANT_COLUMNS = (
    "merchant_id, legal_name, display_name, upi_id, category_code, city, status, "
    "contact_email, version, created_at, updated_at"
)
SELECT_MERCHANT = text(  # noqa: S608 (fixed column list; all values are bound parameters)
    f"SELECT {MERCHANT_COLUMNS} FROM merchants WHERE merchant_id = :merchant_id"
)
LIST_MERCHANTS = text(  # noqa: S608
    f"SELECT {MERCHANT_COLUMNS} FROM merchants "
    "WHERE (:status IS NULL OR status = :status) "
    "ORDER BY merchant_id LIMIT :limit OFFSET :offset"
)
INSERT_MERCHANT = text(
    "INSERT INTO merchants "
    "(merchant_id, legal_name, display_name, upi_id, category_code, city, contact_email) "
    "VALUES (:merchant_id, :legal_name, :display_name, :upi_id, :category_code, :city, "
    ":contact_email)"
)
# Optimistic locking: the update only happens if nobody changed the row since we read it.
UPDATE_STATUS = text(
    "UPDATE merchants SET status = :status, version = version + 1 "
    "WHERE merchant_id = :merchant_id AND version = :version"
)


def _get_merchant(conn: Connection, merchant_id: str) -> dict:
    row = conn.execute(SELECT_MERCHANT, {"merchant_id": merchant_id}).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="merchant not found")
    return dict(row)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness: the process is running."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    """Readiness: the app can reach its database."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="database not reachable") from None
    return {"status": "ready"}


@app.get("/categories")
def list_categories() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.category_code, c.category_name, g.group_code, g.group_name "
                "FROM categories c JOIN category_groups g ON g.group_code = c.group_code "
                "ORDER BY c.category_code"
            )
        ).mappings()
        return [dict(row) for row in rows]


@app.post("/merchants", status_code=201, response_model=Merchant)
def create_merchant(body: MerchantCreate) -> dict:
    """Onboard a merchant. It starts as PENDING with version 1."""
    params = body.model_dump()
    params["upi_id"] = f"{body.merchant_id.lower()}@fpmerchant"
    with engine.begin() as conn:
        try:
            conn.execute(INSERT_MERCHANT, params)
        except IntegrityError as e:
            code = e.orig.args[0] if e.orig and e.orig.args else None
            if code == MYSQL_DUPLICATE_KEY:
                raise HTTPException(status_code=409, detail="merchant already exists") from None
            if code == MYSQL_MISSING_PARENT_ROW:
                raise HTTPException(status_code=422, detail="unknown category_code") from None
            raise
        return _get_merchant(conn, body.merchant_id)


@app.get("/merchants", response_model=list[Merchant])
def list_merchants(
    status: Status | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            LIST_MERCHANTS, {"status": status, "limit": limit, "offset": offset}
        ).mappings()
        return [dict(row) for row in rows]


@app.get("/merchants/{merchant_id}", response_model=Merchant)
def get_merchant(merchant_id: MerchantId) -> dict:
    with engine.connect() as conn:
        return _get_merchant(conn, merchant_id)


@app.patch("/merchants/{merchant_id}/status", response_model=Merchant)
def change_status(merchant_id: MerchantId, body: StatusChange) -> dict:
    """Approve, reject, suspend or close a merchant. Needs the version you last read."""
    with engine.begin() as conn:
        current = _get_merchant(conn, merchant_id)
        if current["version"] != body.version:
            raise HTTPException(
                status_code=409,
                detail=f"version conflict: merchant is at version {current['version']}",
            )
        if body.status not in ALLOWED_TRANSITIONS[Status(current["status"])]:
            raise HTTPException(
                status_code=409,
                detail=f"cannot change status from {current['status']} to {body.status}",
            )
        result = conn.execute(
            UPDATE_STATUS,
            {"status": body.status, "merchant_id": merchant_id, "version": body.version},
        )
        if result.rowcount == 0:
            # Someone else updated the row between our read and our write.
            raise HTTPException(status_code=409, detail="version conflict: read it again")
        return _get_merchant(conn, merchant_id)
