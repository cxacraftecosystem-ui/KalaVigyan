import asyncio
import sys

from app.core.db import dispose_engine, session_scope
from app.scripts.operator_input import read_password
from app.services.e2e_account import E2E_ACCOUNT_EMAIL, E2E_ACCOUNT_ROLE, provision_e2e_account
from app.services.object_store import media_bucket
from app.services.password_accounts import operator_password_refusal


async def run(password: str) -> str:
    try:
        async with session_scope() as session:
            account = await provision_e2e_account(session, password, objects=media_bucket())
    finally:
        await dispose_engine()
    return account.outcome


def main() -> int:
    password = read_password()
    refusal = operator_password_refusal(password)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    outcome = asyncio.run(run(password))
    print(
        f"E2E account {E2E_ACCOUNT_EMAIL} {outcome}: {E2E_ACCOUNT_ROLE}, active, email verified, no two-step."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
