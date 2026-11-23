import asyncio
import sys
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.core.roles import MASTER_ADMIN
from app.scripts.operator_input import read_password
from app.services.object_store import media_bucket
from app.services.password_accounts import operator_password_refusal, upsert_password_account


async def seed(password: str) -> str:
    settings = get_settings()
    try:
        async with session_scope() as session:
            account = await upsert_password_account(
                session,
                email=settings.master_admin_email,
                name=settings.master_admin_name,
                role=MASTER_ADMIN,
                password=password,
                now=datetime.now(UTC),
                objects=media_bucket(),
            )
    finally:
        await dispose_engine()
    return account.outcome


def main() -> int:
    password = read_password()
    refusal = operator_password_refusal(password)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    outcome = asyncio.run(seed(password))
    print(f"Master admin account {outcome}. Two-step verification is set up at first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
