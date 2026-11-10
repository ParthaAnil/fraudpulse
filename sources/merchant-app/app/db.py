"""Database connection pool for the merchant app."""

import os

from sqlalchemy import URL, create_engine

_url = URL.create(
    "mysql+pymysql",
    username="merchant_app",  # the least-privilege user from db/init/03_roles.sh
    password=os.environ["MERCHANT_APP_PASSWORD"],
    host=os.environ.get("MERCHANT_DB_HOST", "merchant-db"),
    port=int(os.environ.get("MERCHANT_DB_PORT", "3306")),
    database="merchants",
)

# A pool keeps a few connections open and reuses them, instead of logging in on every request.
engine = create_engine(
    _url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,  # test a connection before using it, in case MySQL restarted
    pool_recycle=1800,  # replace connections older than 30 minutes
)
