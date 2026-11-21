from app.models.base import pg_enum
from app.models.block_kinds import BLOCK_KINDS as BLOCK_KINDS
from app.models.people_vocabulary import (
    AGE_BANDS as AGE_BANDS,
    CONTRIBUTION_STATUSES as CONTRIBUTION_STATUSES,
    CREDIT_MODES as CREDIT_MODES,
    EXTRACTION_STATUSES as EXTRACTION_STATUSES,
    GENDERS as GENDERS,
    INTERVIEW_TOPICS as INTERVIEW_TOPICS,
    LOCATOR_PRECISIONS as LOCATOR_PRECISIONS,
    MINOR_AGE_BANDS as MINOR_AGE_BANDS,
    READING_STYLES as READING_STYLES,
    TESTIMONY_CONCEPT_TYPES as TESTIMONY_CONCEPT_TYPES,
    TESTIMONY_ENGLISH_SOURCES as TESTIMONY_ENGLISH_SOURCES,
    TESTIMONY_REJECT_REASONS as TESTIMONY_REJECT_REASONS,
    TESTIMONY_SCREENS as TESTIMONY_SCREENS,
    VOICE_PURPOSES as VOICE_PURPOSES,
    VOICE_TRANSPORTS as VOICE_TRANSPORTS,
)

USER_ROLES = ("MASTER_ADMIN", "PROFESSOR", "RESEARCHER", "STUDENT", "ADMIN", "ARTISAN")
AUTH_PROVIDERS = ("LOCAL", "GOOGLE", "MICROSOFT", "YAHOO")
ACCESS_STATUSES = ("ACTIVE", "PENDING", "REJECTED", "SUSPENDED")
CREDENTIAL_LINK_PURPOSES = ("INVITE", "RESET")
ROLE_REQUEST_STATUSES = ("PENDING", "APPROVED", "REJECTED")
CONSENT_KINDS = ("PRIVACY_NOTICE", "VOICE_NOTICE", "ARTISAN_RECORDING", "GUARDIAN_CONSENT")
DATA_REQUEST_KINDS = ("EXPORT", "DELETE")
DATA_REQUEST_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED")
ACTOR_KINDS = ("USER", "SYSTEM")
AUTH_NONCE_PURPOSES = ("GOOGLE_SIGN_IN", "GOOGLE_LINK", "OIDC_SIGN_IN", "FIRST_PASSWORD")

AI_PROVIDERS = ("OPENAI", "GEMINI", "ANTHROPIC", "DEEPSEEK", "ELEVENLABS", "VOYAGE")
AI_TASKS = (
    "PROOFREAD",
    "EXPAND",
    "SUMMARISE",
    "TRANSLATE",
    "TRANSCRIBE",
    "CAPTION",
    "PLAN",
    "COMPOSE",
    "WEB_READ",
    "EXTRACT",
    "EMBED",
    "IMAGE",
    "VIDEO",
    "VOICE_TURN",
    "EVAL_JUDGE",
    "MUSIC",
    "SOUND_EFFECT",
    "INTERVIEW",
    "TESTIMONY",
    "RERANK",
)
PROVIDER_DATA_CLASSES = ("PUBLIC_TEXT_ONLY", "ANY")
USAGE_OUTCOMES = (
    "RESERVED",
    "OK",
    "ERROR",
    "REFUSED_CEILING",
    "REFUSED_QUOTA",
    "REFUSED_PROVIDER",
    "CANCELLED",
)
QUOTA_RESOURCES = ("TEXT_Q", "DEEP_Q", "VOICE_SECONDS", "IMAGE", "VIDEO", "ENRICHMENT_USD", "USD_DAY")

CRAFT_STATUSES = ("ACTIVE", "LEGACY", "MERGED")
GI_STATUSES = ("GI", "NON_GI")
ALIAS_SOURCES = (
    "MASTER",
    "CROSS_PORTAL_CODE",
    "CURATED",
    "IMMERSIVE",
    "CXA",
    "DR_SYNC",
    "PROPOSED",
    "WIKIDATA",
    "TRANSLITERATION",
    "FR_SYNC",
)
ALIAS_STATUSES = ("PROPOSED", "ACTIVE", "REJECTED")
LOCATION_PRECISIONS = ("STATE", "DISTRICT", "POINT")
PLACE_ROLES = (
    "PRACTISED",
    "ORIGIN",
    "HISTORIC_CENTRE",
    "MATERIAL_SOURCE",
    "MARKET",
    "MIGRATED_FROM",
    "MIGRATED_TO",
)
COVERAGE_CLASSES = ("FULL", "THIN")
ENVIRONMENT_FACTORS = ("WATER", "SOIL", "CLIMATE", "LANDFORM", "VEGETATION", "OTHER")
BOUNDARY_SOURCES = ("SOI_1M", "KAGGLE_INDICATIVE")
EVIDENCE_LEVELS = ("VERIFIED", "REVIEWED", "PROVISIONAL", "HYPOTHESIS")
ENV_STATS = (
    "DISTRICT_MEAN",
    "DISTRICT_P10",
    "DISTRICT_P90",
    "UNCERTAINTY_Q05_MEAN",
    "UNCERTAINTY_Q95_MEAN",
    "SHARE",
    "CLASS",
    "NORMAL",
    "DISTRICT_MIN",
    "DISTRICT_MAX",
    "TOTAL",
    "DENSITY",
    "DISTANCE",
    "COUNT",
    "TREND_PER_DECADE",
    "TREND_P_VALUE",
)

SOURCE_KINDS = (
    "PAPER",
    "BOOK",
    "BOOK_CHAPTER",
    "WEB_PAGE",
    "ENCYCLOPEDIA",
    "DATASET",
    "GI_JOURNAL",
    "GOVERNMENT_REPORT",
    "COMPOUND_RECORD",
    "FIELD_TESTIMONY",
    "OTHER",
)
RELIABILITIES = ("A", "B", "C", "D")
SOURCE_STORAGES = ("FULL_TEXT", "EXCERPT", "LINK_ONLY")
SOURCE_ORIGINS = ("IMPORT", "ENRICHMENT", "LIVE_RESEARCH", "CONTRIBUTION")
SENSITIVITIES = ("OPEN", "ATTRIBUTE_REQUIRED", "RESTRICTED")
CHUNK_ACLS = ("PUBLIC", "RESEARCHER", "SIGNED_IN")
CONCEPT_TYPES = (
    "MATERIAL",
    "TOOL",
    "PROCESS_STAGE",
    "MECHANISM",
    "ENVIRONMENTAL_CONDITION",
    "ARTISAN_DECISION",
    "OUTCOME",
    "OPEN_QUESTION",
    "TRADITION",
    "DESIGN_PRINCIPLE",
    "HISTORICAL_CONTEXT",
    "COMPARISON",
    "EXPLANATION",
    "ARTISAN_ACTION",
    "SENSORY_CUE",
    "PROPERTY",
    "CHANGE",
    "CONCEPT",
)
CONCEPT_RELATIONS = (
    "PRECEDES",
    "USES",
    "PRODUCES",
    "SCIENTIFICALLY_EXPLAINED_BY",
    "AFFECTED_BY",
    "PART_OF",
    "DEPENDS_ON",
    "CAUSES",
    "ENABLES",
    "EXPLAINS",
    "REQUIRES",
    "PRACTITIONER_EXPLAINS",
    "HAS_PROPERTY",
    "CONTRASTS_WITH",
    "ASSOCIATED_WITH",
    "SIMILAR_TO",
    "USED_FOR",
    "PREVENTS",
    "MODIFIES",
)
STAGE_TYPES = (
    "PREP",
    "SCOUR",
    "MORDANT",
    "DYE",
    "RESIST",
    "PRINT",
    "WASH",
    "DRY",
    "SHAPE",
    "CARVE",
    "FIRE",
    "CAST",
    "FINISH",
    "OTHER",
)
MATERIAL_KINDS = (
    "FIBRE",
    "DYE",
    "MORDANT",
    "MINERAL",
    "CLAY",
    "METAL",
    "WOOD",
    "RESIN",
    "FUEL",
    "WATER",
    "OTHER",
)
MATERIAL_ROLES = ("INPUT", "MORDANT", "DYE", "RESIST", "BINDER", "FLUX", "FUEL", "TOOL", "PRODUCT", "OTHER")
REACTION_KINDS = (
    "REDOX",
    "ACID_BASE",
    "COMPLEXATION",
    "PRECIPITATION",
    "DEHYDRATION",
    "DEHYDROXYLATION",
    "PHASE_CHANGE",
    "POLYMERISATION",
    "HYDROLYSIS",
    "OTHER",
)
CLAIM_ORIGINS = ("IMPORT", "RESEARCHER", "ENRICHMENT", "MODEL", "LIVE_RESEARCH", "ARTISAN", "CONTRIBUTION")
CLAIM_STATUSES = (
    "DRAFT",
    "PROPOSED",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "RETRACTED",
    "SUPERSEDED",
    "WITHDRAWN",
)
QUOTE_CHECKS = ("PASS", "FAIL", "NA")
SOURCE_RELATIONS = ("DIRECT", "CONTEXTUAL", "ANALOGOUS", "GENERAL_PRINCIPLE")
LIVE_TIERS = ("T3", "T4")
JOB_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED")
OBJECTION_KINDS = ("FACTUAL", "ATTRIBUTION", "SACRED_OR_RESTRICTED", "DEPICTION", "OTHER")
OBJECTION_STATUSES = ("OPEN", "ACKNOWLEDGED", "UPHELD", "DISMISSED")
ANSWER_MODES = ("VERIFIED", "HYBRID", "DEEP")
CHANNELS = ("TEXT", "VOICE")
MESSAGE_ROLES = ("USER", "ASSISTANT", "SYSTEM")
MEDIA_KINDS = ("IMAGE", "VIDEO")
MEDIA_VISIBILITIES = ("PRIVATE", "CRAFT_SHARED")
MEDIA_DISPLAYS = ("INLINE", "LINK_CARD")
IMAGE_RELEVANCE = ("TEXT", "VISION")
IMAGE_ORIGINS = ("PHOTOGRAPH", "DRAWING", "AI_GENERATED")
IMAGE_CONTRIBUTION_STATUSES = ("AWAITING_FILE", "PENDING", "APPROVED", "REJECTED", "WITHDRAWN")
TERM_BASES = ("STORED", "WIKIPEDIA", "WEB_SEARCH")
EVAL_RUN_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED")
EXPLAINER_DEPTHS = ("BASIC", "DETAILED", "EXPERT")
NOTIFICATION_KINDS = ("ANSWER_IMPROVED",)
ENGLISH_SOURCES = ("ORIGINAL", "MACHINE", "EDITED")
DISCIPLINES = (
    "OVERVIEW",
    "PROCESS",
    "CHEMISTRY",
    "PHYSICS",
    "MATERIALS",
    "GEOGRAPHY",
    "GEOLOGY",
    "CLIMATE",
    "ECOLOGY",
    "BOTANY",
    "HISTORY",
    "ECONOMICS",
    "DESIGN",
    "HEALTH",
    "SOCIETY",
    "POLICY",
)
SECTION_STATUSES = ("PROPOSED", "PUBLISHED", "SUPERSEDED", "RETRACTED")
PIECE_SUBJECT_KINDS = ("CRAFT", "CONCEPT", "PLACE", "COMPOUND")
DISTRICT_PLACE_PREFIX = "lgd"
BASIN_PLACE_PREFIX = "basin"
PLACE_KEY_PREFIXES = (DISTRICT_PLACE_PREFIX, BASIN_PLACE_PREFIX)

UserRole = pg_enum("UserRole", USER_ROLES)
AuthProvider = pg_enum("AuthProvider", AUTH_PROVIDERS)
AccessStatus = pg_enum("AccessStatus", ACCESS_STATUSES)
CredentialLinkPurpose = pg_enum("CredentialLinkPurpose", CREDENTIAL_LINK_PURPOSES)
RoleRequestStatus = pg_enum("RoleRequestStatus", ROLE_REQUEST_STATUSES)
ConsentKind = pg_enum("ConsentKind", CONSENT_KINDS)
DataRequestKind = pg_enum("DataRequestKind", DATA_REQUEST_KINDS)
DataRequestStatus = pg_enum("DataRequestStatus", DATA_REQUEST_STATUSES)
ActorKind = pg_enum("ActorKind", ACTOR_KINDS)
AuthNoncePurpose = pg_enum("AuthNoncePurpose", AUTH_NONCE_PURPOSES)
AiProvider = pg_enum("AiProvider", AI_PROVIDERS)
AiTask = pg_enum("AiTask", AI_TASKS)
ProviderDataClass = pg_enum("ProviderDataClass", PROVIDER_DATA_CLASSES)
UsageOutcome = pg_enum("UsageOutcome", USAGE_OUTCOMES)
QuotaResource = pg_enum("QuotaResource", QUOTA_RESOURCES)
CraftStatus = pg_enum("CraftStatus", CRAFT_STATUSES)
GiStatus = pg_enum("GiStatus", GI_STATUSES)
AliasSource = pg_enum("AliasSource", ALIAS_SOURCES)
AliasStatus = pg_enum("AliasStatus", ALIAS_STATUSES)
LocationPrecision = pg_enum("LocationPrecision", LOCATION_PRECISIONS)
BoundarySource = pg_enum("BoundarySource", BOUNDARY_SOURCES)
EvidenceLevel = pg_enum("EvidenceLevel", EVIDENCE_LEVELS)
EnvStat = pg_enum("EnvStat", ENV_STATS)
SourceKind = pg_enum("SourceKind", SOURCE_KINDS)
Reliability = pg_enum("Reliability", RELIABILITIES)
SourceStorage = pg_enum("SourceStorage", SOURCE_STORAGES)
SourceOrigin = pg_enum("SourceOrigin", SOURCE_ORIGINS)
Sensitivity = pg_enum("Sensitivity", SENSITIVITIES)
ChunkAcl = pg_enum("ChunkAcl", CHUNK_ACLS)
ConceptType = pg_enum("ConceptType", CONCEPT_TYPES)
ConceptRelation = pg_enum("ConceptRelation", CONCEPT_RELATIONS)
StageType = pg_enum("StageType", STAGE_TYPES)
MaterialKind = pg_enum("MaterialKind", MATERIAL_KINDS)
MaterialRole = pg_enum("MaterialRole", MATERIAL_ROLES)
ReactionKind = pg_enum("ReactionKind", REACTION_KINDS)
ClaimOrigin = pg_enum("ClaimOrigin", CLAIM_ORIGINS)
ClaimStatus = pg_enum("ClaimStatus", CLAIM_STATUSES)
QuoteCheck = pg_enum("QuoteCheck", QUOTE_CHECKS)
SourceRelation = pg_enum("SourceRelation", SOURCE_RELATIONS)
LiveTier = pg_enum("LiveTier", LIVE_TIERS)
JobStatus = pg_enum("JobStatus", JOB_STATUSES)
ObjectionKind = pg_enum("ObjectionKind", OBJECTION_KINDS)
ObjectionStatus = pg_enum("ObjectionStatus", OBJECTION_STATUSES)
AnswerMode = pg_enum("AnswerMode", ANSWER_MODES)
Channel = pg_enum("Channel", CHANNELS)
MessageRole = pg_enum("MessageRole", MESSAGE_ROLES)
MediaKind = pg_enum("MediaKind", MEDIA_KINDS)
MediaVisibility = pg_enum("MediaVisibility", MEDIA_VISIBILITIES)
EvalRunStatus = pg_enum("EvalRunStatus", EVAL_RUN_STATUSES)

ALL_ENUMS = (
    UserRole,
    AuthProvider,
    AccessStatus,
    CredentialLinkPurpose,
    RoleRequestStatus,
    ConsentKind,
    DataRequestKind,
    DataRequestStatus,
    ActorKind,
    AuthNoncePurpose,
    AiProvider,
    AiTask,
    ProviderDataClass,
    UsageOutcome,
    QuotaResource,
    CraftStatus,
    GiStatus,
    AliasSource,
    AliasStatus,
    LocationPrecision,
    BoundarySource,
    EvidenceLevel,
    EnvStat,
    SourceKind,
    Reliability,
    SourceStorage,
    SourceOrigin,
    Sensitivity,
    ChunkAcl,
    ConceptType,
    ConceptRelation,
    StageType,
    MaterialKind,
    MaterialRole,
    ReactionKind,
    ClaimOrigin,
    ClaimStatus,
    QuoteCheck,
    SourceRelation,
    LiveTier,
    JobStatus,
    ObjectionKind,
    ObjectionStatus,
    AnswerMode,
    Channel,
    MessageRole,
    MediaKind,
    MediaVisibility,
    EvalRunStatus,
)
