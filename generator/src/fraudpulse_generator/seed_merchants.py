"""Onboards the generator's merchants through the merchant app's API, then approves them.

    fraudpulse-seed-merchants --merchants 500

Safe to run again: merchants that already exist are left as they are.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from fraudpulse_generator.population import Merchant, make_merchants

DEFAULT_URL = "http://127.0.0.1:8001"
TIMEOUT_SECONDS = 10


def _call(base_url: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """Send one request. Returns (HTTP status, JSON body), also for 4xx and 5xx answers."""
    request = urllib.request.Request(  # noqa: S310 (main() only accepts http and https URLs)
        base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}


def onboard(base_url: str, merchant: Merchant) -> bool:
    """Create the merchant if missing and approve it if pending. True if it was new."""
    status, _ = _call(
        base_url,
        "POST",
        "/merchants",
        {
            "merchant_id": merchant.merchant_id,
            "legal_name": merchant.legal_name,
            "display_name": merchant.display_name,
            "category_code": merchant.category_code,
            "city": merchant.city,
            "contact_email": merchant.contact_email,
        },
    )
    if status not in (201, 409):  # 409 = already exists, which is fine
        raise RuntimeError(f"{merchant.merchant_id}: create answered HTTP {status}")
    is_new = status == 201

    status, current = _call(base_url, "GET", f"/merchants/{merchant.merchant_id}")
    if status != 200:
        raise RuntimeError(f"{merchant.merchant_id}: read answered HTTP {status}")
    if current["status"] == "PENDING":
        status, _ = _call(
            base_url,
            "PATCH",
            f"/merchants/{merchant.merchant_id}/status",
            {"status": "ACTIVE", "version": current["version"]},
        )
        if status != 200:
            raise RuntimeError(f"{merchant.merchant_id}: approve answered HTTP {status}")
    return is_new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fraudpulse-seed-merchants",
        description="Onboard and approve fake merchants through the merchant app.",
    )
    parser.add_argument("--merchants", type=int, default=500, help="default 500")
    parser.add_argument("--seed", type=int, default=42, help="same seed, same merchants")
    parser.add_argument(
        "--url", default=os.environ.get("MERCHANT_APP_URL", DEFAULT_URL), help="merchant app URL"
    )
    args = parser.parse_args(argv)

    base_url = args.url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        print("fraudpulse-seed-merchants: error: --url must start with http://", file=sys.stderr)
        return 2
    try:
        merchants = make_merchants(args.merchants, seed=args.seed)
    except ValueError as e:
        print(f"fraudpulse-seed-merchants: error: {e}", file=sys.stderr)
        return 2

    new = 0
    try:
        for merchant in merchants:
            new += onboard(base_url, merchant)
    except (OSError, RuntimeError) as e:
        print(f"fraudpulse-seed-merchants: failed after {new} new merchants: {e}", file=sys.stderr)
        return 1

    print(f"onboarded {new} new merchants, {len(merchants) - new} were already there")
    return 0
