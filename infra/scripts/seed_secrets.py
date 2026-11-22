import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import boto3
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

REGION = "ap-south-1"
ENV_PATH = "/kalavigyan/env"
DB_PASSWORD_PARAM = "/kalavigyan/db-password"
SUPABASE_REF = "inqbqiqspgvhfamupwuc"
POOLER_HOST = "aws-1-ap-south-1.pooler.supabase.com"
REPO = "cxacraftecosystem-ui/KalaVigyan"
WEB_ORIGIN = "https://kalavigyan.vercel.app"
VERCEL_TEAM = "cxacraftecosystem-8028s-projects"
VERCEL_PROJECT = "kalavigyan"
INFRA = Path(__file__).resolve().parents[1]

GENERATED = (
    "JWT_SECRET",
    "SECRETS_ENCRYPTION_KEY",
    "TWO_FACTOR_ENCRYPTION_KEY",
    "WEB_PROXY_SECRET",
    "WEB_REVALIDATE_SECRET",
    "TRANSCRIPT_ENCRYPTION_KEY",
    "VOICE_SESSION_HMAC_KEY",
    "VOICE_LLM_BEARER",
    "MEDIA_BUNDLE_HMAC_KEY",
)
TOKEN_GENERATED = (
    "JWT_SECRET",
    "WEB_PROXY_SECRET",
    "WEB_REVALIDATE_SECRET",
    "VOICE_SESSION_HMAC_KEY",
    "VOICE_LLM_BEARER",
    "MEDIA_BUNDLE_HMAC_KEY",
)
COPYABLE = (
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "BRAVE_SEARCH_API_KEY",
    "VOYAGE_API_KEY",
    "DATA_GOV_IN_API_KEY",
    "TURNSTILE_SECRET_KEY",
    "GOOGLE_CLIENT_ID",
    "MASTER_ADMIN_EMAIL",
    "MASTER_ADMIN_NAME",
)
GITHUB_SECRETS = (
    "DATABASE_URL",
    "JWT_SECRET",
    "SECRETS_ENCRYPTION_KEY",
    "TWO_FACTOR_ENCRYPTION_KEY",
    "TRANSCRIPT_ENCRYPTION_KEY",
    "VOICE_SESSION_HMAC_KEY",
    "VOICE_LLM_BEARER",
    "MEDIA_BUNDLE_HMAC_KEY",
    "ORIGIN_VERIFY_SECRET",
    "WEB_PROXY_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    *COPYABLE,
)
STALE = (
    "AWS_S3_BUCKET",
    "BRAVE_API_KEY",
    "NEXT_PUBLIC_APP_URL",
    "DATABASE_USE_TRANSACTION_POOLER",
    "TWO_FACTOR_KEY_REQUIRED",
    "MEDIA_PRESIGNED_READS",
)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def tf_outputs(tf_bin):
    out = subprocess.run(
        [tf_bin, "output", "-json"], cwd=INFRA / "terraform", capture_output=True, text=True, check=True
    ).stdout
    return {k: v["value"] for k, v in json.loads(out).items()}


class Params:
    def __init__(self):
        self.ssm = boto3.client("ssm", region_name=REGION)

    def get(self, name):
        try:
            return self.ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
        except self.ssm.exceptions.ParameterNotFound:
            return None

    def all_env(self):
        found = {}
        for page in self.ssm.get_paginator("get_parameters_by_path").paginate(
            Path=ENV_PATH, Recursive=True, WithDecryption=True
        ):
            for p in page["Parameters"]:
                found[p["Name"].rsplit("/", 1)[-1]] = p["Value"]
        return found

    def put(self, key, value, current):
        if current.get(key) == value:
            return False
        self.ssm.put_parameter(
            Name=f"{ENV_PATH}/{key}", Value=value, Type="SecureString", Overwrite=True, Tier="Standard"
        )
        current[key] = value
        return True

    def drop(self, key, current):
        if key not in current:
            return False
        self.ssm.delete_parameter(Name=f"{ENV_PATH}/{key}")
        current.pop(key, None)
        return True


def generated_value(key):
    if key in TOKEN_GENERATED:
        return secrets.token_urlsafe(64)
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def database_url(params):
    password = params.get(DB_PASSWORD_PARAM)
    if not password:
        raise SystemExit(f"{DB_PASSWORD_PARAM} is missing")
    user = f"postgres.{SUPABASE_REF}"
    return (
        f"postgresql://{user}:{urllib.parse.quote(password, safe='')}@{POOLER_HOST}:5432/postgres"
        "?sslmode=require"
    )


def ssm_run(instance_id, script, timeout=600):
    ssm = boto3.client("ssm", region_name=REGION)
    cid = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script], "executionTimeout": [str(timeout)]},
    )["Command"]["CommandId"]
    while True:
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            return inv


def copy_from_instance(instance_id, env_file, keys):
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    names = " ".join(keys)
    script = f"""set -eu
umask 077
pub="$(mktemp)"
cat > "$pub" <<'KEY'
{pem}KEY
for k in {names}; do
  v="$(grep -m1 "^$k=" '{env_file}' | cut -d= -f2- || true)"
  [ -n "$v" ] || continue
  printf '%s %s\\n' "$k" "$(printf '%s' "$v" | openssl pkeyutl -encrypt -pubin -inkey "$pub" -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256 -pkeyopt rsa_mgf1_md:sha256 | base64 -w0)"
done
rm -f "$pub"
"""
    inv = ssm_run(instance_id, script)
    if inv["Status"] != "Success":
        raise SystemExit(f"copy from {instance_id} failed: {inv['Status']} {inv['StandardErrorContent'][:300]}")
    oaep = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    found = {}
    for line in inv["StandardOutputContent"].splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) != 2:
            continue
        value = key.decrypt(base64.b64decode(parts[1]), oaep).decode().strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if value:
            found[parts[0]] = value
    return found


def gh_token():
    return subprocess.run(
        ["gh", "auth", "token", "--user", "ankits1802"], capture_output=True, text=True, check=True
    ).stdout.strip()


def gh(args, stdin=None):
    env = {**os.environ, "GH_TOKEN": gh_token()}
    r = subprocess.run(["gh", *args], check=False, input=stdin, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()[:300]}")


def vercel_token():
    path = Path(os.environ["APPDATA"]) / "com.vercel.cli" / "Data" / "auth.json"
    return json.loads(path.read_text(encoding="utf-8"))["token"]


def vercel(method, path, body=None):
    sep = "&" if "?" in path else "?"
    req = urllib.request.Request(
        f"https://api.vercel.com{path}{sep}slug={VERCEL_TEAM}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": "Bearer " + vercel_token(),
            "Content-Type": "application/json",
            "User-Agent": "kalavigyan-provisioner",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def main():
    ap = argparse.ArgumentParser(description="Seed the KalaVigyan environment into SSM, GitHub and Vercel.")
    ap.add_argument("--terraform", default="terraform")
    ap.add_argument("--copy-from-instance")
    ap.add_argument("--copy-env-file", default="/home/ubuntu/app/current/backend/.env")
    ap.add_argument("--skip-github", action="store_true")
    ap.add_argument("--skip-vercel", action="store_true")
    ap.add_argument("--skip-box", action="store_true")
    ap.add_argument("--preview-cors", action="store_true")
    a = ap.parse_args()

    tf = tf_outputs(a.terraform)
    params = Params()
    current = params.all_env()
    log(f"{len(current)} keys already under {ENV_PATH}")

    wanted = {}
    for key in GENERATED:
        wanted[key] = current.get(key) or generated_value(key)
    wanted["DATABASE_URL"] = database_url(params)
    wanted["AWS_ACCESS_KEY_ID"] = tf["media_access_key_id"]
    wanted["AWS_SECRET_ACCESS_KEY"] = tf["media_secret_access_key"]
    wanted["ORIGIN_VERIFY_SECRET"] = tf["origin_verify_secret"]
    wanted.update(
        {
            "APP_ENV": "production",
            "AWS_REGION": REGION,
            "S3_BUCKET": tf["media_bucket"],
            "BACKEND_CORS_ORIGINS": WEB_ORIGIN,
            "PUBLIC_WEB_URL": WEB_ORIGIN,
            "PUBLIC_API_URL": tf["api_base_url"],
            "FORWARDED_CLIENT_HOPS": "2",
            "DATABASE_CONNECTION_LIMIT": "12",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "SEARXNG_URL": "http://127.0.0.1:8888",
            "FETCHER_URL": "http://127.0.0.1:8090",
            "MAIL_SES_REGION": REGION,
            "MAIL_FROM_NAME": "KalaVigyan",
        }
    )
    if a.preview_cors:
        wanted["BACKEND_CORS_PREVIEW_PROJECT"] = VERCEL_PROJECT
        wanted["BACKEND_CORS_PREVIEW_SCOPE"] = VERCEL_TEAM
    if current.get("BRAVE_API_KEY") and not current.get("BRAVE_SEARCH_API_KEY"):
        wanted["BRAVE_SEARCH_API_KEY"] = current["BRAVE_API_KEY"]
    missing = [k for k in COPYABLE if not current.get(k)]
    if a.copy_from_instance and missing:
        copied = copy_from_instance(a.copy_from_instance, a.copy_env_file, missing)
        log(f"copied from {a.copy_from_instance}: {', '.join(sorted(copied)) or 'nothing'}")
        wanted.update(copied)

    changed = [k for k, v in wanted.items() if params.put(k, v, current)]
    dropped = [k for k in STALE if params.drop(k, current)]
    log(f"Parameter Store: {len(changed)} written ({', '.join(sorted(changed)) or 'none'}), {len(current)} total")
    if dropped:
        log(f"Parameter Store: removed unused {', '.join(dropped)}")
    still_missing = [k for k in COPYABLE if not current.get(k)]

    if not a.skip_github:
        for key in GITHUB_SECRETS:
            if current.get(key):
                gh(["secret", "set", key, "--repo", REPO], stdin=current[key])
        variables = {
            "AWS_REGION": REGION,
            "AWS_DEPLOY_ROLE_ARN": tf["deploy_role_arn"],
            "AWS_RIVER_LOAD_ROLE_ARN": tf["river_load_role_arn"],
            "EC2_INSTANCE_ID": tf["instance_id"],
            "MEDIA_BUCKET": tf["media_bucket"],
            "API_BASE_URL": tf["api_base_url"],
            "CLOUDFRONT_DISTRIBUTION_ID": tf["cloudfront_distribution_id"],
            "WEB_ORIGIN": WEB_ORIGIN,
        }
        st, proj = vercel("GET", f"/v9/projects/{VERCEL_PROJECT}")
        if st == 200:
            variables["VERCEL_ORG_ID"] = proj["accountId"]
            variables["VERCEL_PROJECT_ID"] = proj["id"]
        for key, value in variables.items():
            gh(["variable", "set", key, "--repo", REPO, "--body", value])
        log(f"GitHub: {sum(1 for k in GITHUB_SECRETS if current.get(k))} secrets, {len(variables)} variables")

    if not a.skip_vercel:
        envs = {"NEXT_PUBLIC_API_URL": tf["api_base_url"], "NEXT_PUBLIC_APP_URL": WEB_ORIGIN}
        for public, live_with in (
            ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID"),
            ("YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET"),
            ("MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"),
            ("MICROSOFT_TENANT", "MICROSOFT_CLIENT_SECRET"),
        ):
            if current.get(public) and current.get(live_with):
                envs[f"NEXT_PUBLIC_{public}"] = current[public]
        server_only = {key: current[key] for key in ("WEB_PROXY_SECRET", "WEB_REVALIDATE_SECRET")}
        for key, value in {**envs, **server_only}.items():
            kind = "sensitive" if key in server_only else "encrypted"
            st, out = vercel(
                "POST",
                f"/v10/projects/{VERCEL_PROJECT}/env?upsert=true",
                {"key": key, "value": value, "type": kind, "target": ["production", "preview"]},
            )
            if st not in (200, 201):
                raise SystemExit(f"Vercel env {key} failed: {st} {out}")
        log(f"Vercel: {', '.join([*envs, *server_only])}")

    if not a.skip_box:
        render = (INFRA / "deploy" / "render_env.sh").read_text(encoding="utf-8")
        script = (
            "set -eu\n"
            "cat > /usr/local/sbin/kv-render-env.new <<'RENDER'\n"
            f"{render}RENDER\n"
            "install -m 0755 /usr/local/sbin/kv-render-env.new /usr/local/sbin/kv-render-env\n"
            "rm -f /usr/local/sbin/kv-render-env.new\n"
            "/usr/local/sbin/kv-render-env\n"
            "grep -c . /opt/kalavigyan/.env\n"
        )
        inv = ssm_run(tf["instance_id"], script)
        log(f"box: {inv['Status']}\n{inv['StandardOutputContent'].strip()}\n{inv['StandardErrorContent'].strip()}")
        if inv["Status"] != "Success":
            raise SystemExit(1)

    log("keys: " + ", ".join(sorted(current)))
    if still_missing:
        log("owner must provide: " + ", ".join(still_missing))


if __name__ == "__main__":
    main()
