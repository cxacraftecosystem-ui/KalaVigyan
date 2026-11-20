import re
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from pydantic import (
    AliasChoices,
    EmailStr,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

_ALLOWED_JWT_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})

_VERCEL_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

VERCEL_PREVIEW_ID = r"[a-z0-9]{9}"

_LOCAL_DB_HOSTNAMES = frozenset({"localhost", "host.docker.internal", "postgres", "db"})

_SSL_QUERY_KEYS = frozenset({"sslmode", "sslrootcert", "sslcert", "sslkey", "sslpassword"})


def is_local_db_host(host: str) -> bool:
    host = host.strip().strip("[]").lower()
    if not host or host in _LOCAL_DB_HOSTNAMES or host.endswith((".local", ".internal", ".localhost")):
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def with_explicit_sslmode(url: str, require: bool | None) -> str:
    if require is False:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.scheme.startswith("postgres"):
        return url
    existing = {key.lower() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
    if existing & _SSL_QUERY_KEYS:
        return url
    if require is None and is_local_db_host(parts.hostname or ""):
        return url
    query = f"{parts.query}&sslmode=require" if parts.query else "sslmode=require"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _vercel_slug(value: str) -> str:
    slug = value.strip()
    if not _VERCEL_SLUG.fullmatch(slug):
        raise ValueError("must be a Vercel slug: lowercase letters and digits joined by single hyphens")
    return slug


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias=AliasChoices("DATABASE_POOL_SIZE", "DATABASE_CONNECTION_LIMIT"),
    )
    database_max_overflow: int = Field(default=0, ge=0, le=50, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, ge=1, alias="DATABASE_POOL_TIMEOUT")
    database_connect_timeout: int = Field(default=30, ge=1, alias="DATABASE_CONNECT_TIMEOUT")
    database_require_ssl: bool | None = Field(default=None, alias="DATABASE_REQUIRE_SSL")

    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expires_minutes: int = Field(default=60 * 24 * 7, alias="JWT_EXPIRES_MINUTES")
    allow_weak_jwt_secret: bool = Field(default=False, alias="ALLOW_WEAK_JWT_SECRET")

    secrets_encryption_key: str | None = Field(default=None, alias="SECRETS_ENCRYPTION_KEY")
    two_factor_encryption_key: str | None = Field(default=None, alias="TWO_FACTOR_ENCRYPTION_KEY")
    two_factor_previous_keys: str | None = Field(default=None, alias="TWO_FACTOR_PREVIOUS_KEYS")
    transcript_encryption_key: str | None = Field(default=None, alias="TRANSCRIPT_ENCRYPTION_KEY")
    voice_session_hmac_key: str | None = Field(default=None, alias="VOICE_SESSION_HMAC_KEY")
    media_bundle_hmac_key: str | None = Field(default=None, alias="MEDIA_BUNDLE_HMAC_KEY")

    app_env: str = Field(default="development", alias="APP_ENV")
    public_web_url: str = Field(default="http://localhost:3000", alias="PUBLIC_WEB_URL")
    public_api_url: str | None = Field(default=None, alias="PUBLIC_API_URL")
    backend_cors_origins: str = Field(default="http://localhost:3000", alias="BACKEND_CORS_ORIGINS")
    cors_preview_project: str | None = Field(default=None, alias="BACKEND_CORS_PREVIEW_PROJECT")
    cors_preview_scope: str | None = Field(
        default=None, alias="BACKEND_CORS_PREVIEW_SCOPE", validate_default=True
    )
    forwarded_client_hops: int = Field(default=2, ge=1, le=5, alias="FORWARDED_CLIENT_HOPS")
    web_proxy_secret: str | None = Field(default=None, alias="WEB_PROXY_SECRET")
    web_revalidate_secret: str | None = Field(default=None, alias="WEB_REVALIDATE_SECRET")
    backend_expose_docs: bool = Field(default=False, alias="BACKEND_EXPOSE_DOCS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    release: str = Field(default="dev", alias="RELEASE")

    master_admin_email: str = Field(alias="MASTER_ADMIN_EMAIL")
    master_admin_name: str = Field(default="Master Admin", alias="MASTER_ADMIN_NAME")
    default_signup_role: str = Field(default="STUDENT", alias="DEFAULT_SIGNUP_ROLE")
    access_pending_max: int = Field(default=500, ge=1, alias="ACCESS_PENDING_MAX")

    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    microsoft_client_id: str | None = Field(default=None, alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: str | None = Field(default=None, alias="MICROSOFT_CLIENT_SECRET")
    microsoft_tenant: str = Field(default="common", alias="MICROSOFT_TENANT")
    yahoo_client_id: str | None = Field(default=None, alias="YAHOO_CLIENT_ID")
    yahoo_client_secret: str | None = Field(default=None, alias="YAHOO_CLIENT_SECRET")

    mail_from_address: str | None = Field(default=None, alias="MAIL_FROM_ADDRESS")
    mail_from_name: str = Field(default="KalaVigyan", alias="MAIL_FROM_NAME")
    mail_reply_to: str | None = Field(default=None, alias="MAIL_REPLY_TO")
    mail_ses_region: str = Field(default="ap-south-1", alias="MAIL_SES_REGION")
    mail_ses_configuration_set: str | None = Field(default=None, alias="MAIL_SES_CONFIGURATION_SET")
    alert_digest_enabled: bool = Field(default=False, alias="ALERT_DIGEST_ENABLED")

    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, validation_alias=AliasChoices("S3_BUCKET", "AWS_S3_BUCKET"))

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_agent_id: str | None = Field(default=None, alias="ELEVENLABS_AGENT_ID")
    voice_llm_bearer: str | None = Field(default=None, alias="VOICE_LLM_BEARER")
    voice_call_enabled: bool = Field(default=False, alias="VOICE_CALL_ENABLED")
    artisan_conversation_enabled: bool = Field(default=False, alias="ARTISAN_CONVERSATION_ENABLED")
    elevenlabs_artisan_agent_id: str | None = Field(default=None, alias="ELEVENLABS_ARTISAN_AGENT_ID")
    signature_figures_enabled: bool = Field(default=False, alias="SIGNATURE_FIGURES_ENABLED")
    brave_search_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("BRAVE_SEARCH_API_KEY", "BRAVE_API_KEY")
    )
    searxng_url: str = Field(default="http://127.0.0.1:8888", alias="SEARXNG_URL")
    fetcher_url: str = Field(default="http://127.0.0.1:8090", alias="FETCHER_URL")
    exa_api_key: str | None = Field(default=None, alias="EXA_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    openalex_api_key: str | None = Field(default=None, alias="OPENALEX_API_KEY")
    research_contact_email: EmailStr = Field(
        default="cxa.craftecosystem@gmail.com", alias="RESEARCH_CONTACT_EMAIL"
    )
    semantic_scholar_api_key: str | None = Field(default=None, alias="SEMANTIC_SCHOLAR_API_KEY")
    core_api_key: str | None = Field(default=None, alias="CORE_API_KEY")
    springer_nature_api_key: str | None = Field(default=None, alias="SPRINGER_NATURE_API_KEY")
    elsevier_api_key: str | None = Field(default=None, alias="ELSEVIER_API_KEY")
    elsevier_insttoken: str | None = Field(default=None, alias="ELSEVIER_INSTTOKEN")
    wiley_tdm_token: str | None = Field(default=None, alias="WILEY_TDM_TOKEN")
    data_gov_in_api_key: str | None = Field(default=None, alias="DATA_GOV_IN_API_KEY")
    turnstile_secret_key: str | None = Field(default=None, alias="TURNSTILE_SECRET_KEY")
    turnstile_site_key: str | None = Field(default=None, alias="TURNSTILE_SITE_KEY")
    cross_portal_token: str | None = Field(default=None, alias="CROSS_PORTAL_TOKEN")
    designer_portal_api_url: str | None = Field(default=None, alias="DESIGNER_PORTAL_API_URL")
    field_repository_api_url: str | None = Field(default=None, alias="FIELD_REPOSITORY_API_URL")
    field_voices_enabled: bool = Field(default=False, alias="FIELD_VOICES_ENABLED")
    field_voices_image_hosts: str | None = Field(default=None, alias="FIELD_VOICES_IMAGE_HOSTS")
    mcp_server_enabled: bool = Field(default=False, alias="MCP_SERVER_ENABLED")
    vercel_deploy_hook_url: str | None = Field(default=None, alias="VERCEL_DEPLOY_HOOK_URL")

    sign_in_attempts_per_ip: int = Field(default=20, ge=1, alias="SIGN_IN_ATTEMPTS_PER_IP")
    sign_in_attempts_per_account: int = Field(default=10, ge=1, alias="SIGN_IN_ATTEMPTS_PER_ACCOUNT")
    sign_in_window_seconds: int = Field(default=900, ge=1, alias="SIGN_IN_WINDOW_SECONDS")

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def _normalise_jwt_algorithm(cls, value: str) -> str:
        algorithm = value.strip().upper()
        if algorithm not in _ALLOWED_JWT_ALGORITHMS:
            raise ValueError(f"JWT_ALGORITHM must be one of {sorted(_ALLOWED_JWT_ALGORITHMS)}")
        return algorithm

    @field_validator("cors_preview_project")
    @classmethod
    def _check_preview_project(cls, value: str | None) -> str | None:
        return None if value is None else _vercel_slug(value)

    @field_validator("cors_preview_scope")
    @classmethod
    def _check_preview_scope(cls, value: str | None, info: ValidationInfo) -> str | None:
        if (value is None) != (info.data.get("cors_preview_project") is None):
            raise ValueError(
                "BACKEND_CORS_PREVIEW_PROJECT and BACKEND_CORS_PREVIEW_SCOPE are set together or not at all"
            )
        return None if value is None else _vercel_slug(value)

    @model_validator(mode="after")
    def _harden_database_url(self) -> Settings:
        self.database_url = with_explicit_sslmode(self.database_url, self.database_require_ssl)
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        seen: set[str] = set()
        for chunk in self.backend_cors_origins.replace("\n", ",").split(","):
            origin = chunk.strip().strip("[]").strip().strip("\"'").strip().rstrip("/")
            if not origin or origin in seen:
                continue
            seen.add(origin)
            origins.append(origin)
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        if self.cors_preview_project is None or self.cors_preview_scope is None:
            return None
        project = re.escape(self.cors_preview_project)
        scope = re.escape(self.cors_preview_scope)
        return rf"https://{project}-{VERCEL_PREVIEW_ID}-{scope}\.vercel\.app"

    @property
    def cors_allow_credentials(self) -> bool:
        return "*" not in self.cors_origins


class SettingsError(RuntimeError):
    pass


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        problems = sorted(
            {f"{'.'.join(str(part) for part in item['loc'])} ({item['type']})" for item in error.errors()}
        )
        raise SettingsError(f"Invalid settings: {', '.join(problems)}") from None
