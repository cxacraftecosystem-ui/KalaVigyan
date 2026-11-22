import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.services.e2e_account import (
    E2E_ROLE_ACCOUNTS,
    E2ERoleAccount,
    provision_role_account,
    totp_secret_refusal,
)
from app.services.object_store import media_bucket
from app.services.password_accounts import operator_password_refusal

__all__ = [
    "PARAMETER_PATH",
    "ParameterError",
    "RoleCredentials",
    "instance_role_client",
    "instance_role_session",
    "main",
    "parameter_name",
    "parameter_names",
    "read_credentials",
    "refusals",
    "run",
]

PARAMETER_PATH = "/kalavigyan/e2e"
PASSWORD = "PASSWORD"
TOTP_SECRET = "TOTP_SECRET"
PARTS = (PASSWORD, TOTP_SECRET)
SECURE_STRING = "SecureString"
NO_ARGUMENTS = (
    "provision_e2e_role_accounts takes no arguments: it reads every password and two-step secret "
    f"from {PARAMETER_PATH} in Parameter Store (docs/RUNBOOK.md, E2E production run)."
)


class ParameterError(Exception):
    pass


@dataclass(frozen=True)
class RoleCredentials:
    account: E2ERoleAccount
    password: str = field(repr=False)
    totp_secret: str = field(repr=False)


def parameter_name(account: E2ERoleAccount, part: str) -> str:
    return f"{PARAMETER_PATH}/{account.secret_name(part)}"


def parameter_names() -> list[str]:
    return [parameter_name(account, part) for account in E2E_ROLE_ACCOUNTS for part in PARTS]


def instance_role_session() -> Any:
    import boto3
    import botocore.session

    core = botocore.session.get_session()
    core.get_component("credential_provider").remove("env")
    return boto3.Session(botocore_session=core)


def instance_role_client() -> Any:
    return instance_role_session().client("ssm", region_name=get_settings().aws_region)


def _error_code(error: Exception) -> str:
    response = getattr(error, "response", None) or {}
    return str((response.get("Error") or {}).get("Code") or type(error).__name__)


def read_credentials(client: Any) -> list[RoleCredentials]:
    names = parameter_names()
    try:
        answer = client.get_parameters(Names=names, WithDecryption=True)
    except Exception as error:
        raise ParameterError(
            f"Could not read {PARAMETER_PATH} from Parameter Store ({_error_code(error)}). The box role "
            f"needs ssm:GetParameters on {PARAMETER_PATH}/* (infra/terraform/iam.tf)."
        ) from None
    found = {row["Name"]: row for row in answer.get("Parameters") or []}
    missing = [name for name in names if name not in found]
    if missing:
        raise ParameterError(f"Missing from Parameter Store: {', '.join(missing)}.")
    plain = [name for name in names if found[name].get("Type") != SECURE_STRING]
    if plain:
        raise ParameterError(f"Store these as {SECURE_STRING}: {', '.join(plain)}.")
    return [
        RoleCredentials(
            account=account,
            password=found[parameter_name(account, PASSWORD)]["Value"],
            totp_secret=found[parameter_name(account, TOTP_SECRET)]["Value"],
        )
        for account in E2E_ROLE_ACCOUNTS
    ]


def refusals(credentials: list[RoleCredentials]) -> list[str]:
    found = []
    for item in credentials:
        checks = {
            PASSWORD: operator_password_refusal(item.password),
            TOTP_SECRET: totp_secret_refusal(item.totp_secret),
        }
        found.extend(f"{parameter_name(item.account, part)}: {text}" for part, text in checks.items() if text)
    return found


async def run(credentials: list[RoleCredentials]) -> list[dict[str, Any]]:
    report = []
    try:
        async with session_scope() as session:
            for item in credentials:
                done = await provision_role_account(
                    session, item.account, item.password, item.totp_secret, objects=media_bucket()
                )
                report.append(
                    {
                        "email": done.user.email,
                        "role": done.user.role,
                        "outcome": done.outcome,
                        "twoStep": bool(done.user.twoFactorEnabled),
                    }
                )
    finally:
        await dispose_engine()
    return report


def main() -> int:
    if len(sys.argv) > 1:
        print(NO_ARGUMENTS, file=sys.stderr)
        return 2
    try:
        credentials = read_credentials(instance_role_client())
    except ParameterError as error:
        print(str(error), file=sys.stderr)
        return 2
    problems = refusals(credentials)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    accounts = asyncio.run(run(credentials))
    print(json.dumps({"ok": True, "accounts": accounts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
