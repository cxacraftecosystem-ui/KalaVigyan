# Repository facts

Every count that changes with the code, generated from the working tree by `tools/repo_facts_build.py`; never edit this file by hand. Other documents link here instead of restating a number, so a new table, route, tool or test makes exactly one file stale and one command makes it right. The figures describe the tree, not production: the deployed API lags the tree by the commits not yet released.

## Data model

| What | Count |
| --- | ---: |
| Tables (`__tablename__` in `backend/app/models/`) | 139 |
| Migrations (`backend/migrations/versions/`) | 56 |

Newest migration: `0057_open_data_releases`.

Tables: `AccessRoster`, `AdminDistrict`, `AdminState`, `AlertDigestSend`, `AllowanceBucket`, `Answer`, `AnswerCitation`, `AnswerGap`, `AnswerSentence`, `AnswerTrace`, `AnswerVerdict`, `AppSetting`, `ArticleSection`, `ArtisanContribution`, `ArtisanConversation`, `ArtisanConversationAudio`, `ArtisanCraft`, `ArtisanProfile`, `AuditLog`, `AuthNonce`, `CandidateCheck`, `Chunk`, `Claim`, `ClaimSource`, `ClaimTranslation`, `ComponentProposal`, `Compound`, `Concept`, `ConceptEdge`, `ConditionReading`, `ConsentRecord`, `Conversation`, `Craft`, `CraftAlias`, `CraftCategory`, `CraftCode`, `CraftGiRecord`, `CraftLocation`, `CraftPageArchive`, `CraftPageSnapshot`, `CraftPrice`, `CraftSpelling`, `CraftSteward`, `CraftSubCategory`, `CraftWorkforce`, `CuratedCategory`, `CuratedCategoryClaim`, `CuratedClaim`, `CuratedCraft`, `CxaCraftMap`, `DataRequest`, `DatasetTable`, `DatasetUpload`, `DistrictEnvValue`, `DistrictGeology`, `EnrichmentJob`, `EnrichmentProposal`, `EnvDataset`, `EvalCase`, `EvalResult`, `EvalRun`, `FieldImage`, `FieldImageCraft`, `FieldPhotoReview`, `FieldPhotoScreen`, `FieldRecording`, `FieldRecordingCraft`, `FieldSegment`, `FieldVoiceStream`, `GiRegistration`, `ImageContribution`, `ImageFingerprint`, `ImageScreen`, `Invite`, `Job`, `KnowledgePiece`, `KnowledgePieceSubject`, `LayoutProposal`, `LessonPack`, `LiveCandidate`, `ManagedSecret`, `Material`, `McpTermsAcceptance`, `McpToolCall`, `MediaAsset`, `MediaJob`, `MediaRef`, `MediaRefClaim`, `Message`, `MonographDocument`, `Notification`, `OAuthClient`, `OAuthCode`, `OAuthGrant`, `OAuthToken`, `Objection`, `OpenDataRelease`, `PageDraft`, `PageLayout`, `PagePreview`, `PasswordResetRequest`, `PasswordResetToken`, `PictureDeclaration`, `Process`, `ProcessCondition`, `ProcessStage`, `Provider`, `QueuedProposal`, `QuotaLedger`, `QuotaPolicy`, `Reaction`, `ReactionCitation`, `ReviewEvent`, `RiverBasin`, `RiverReach`, `RoleRequest`, `RoutePolicy`, `SavedItem`, `SecretTestResult`, `Source`, `SourceUpkeep`, `StageMaterial`, `StructureProposal`, `StudentProfile`, `SuppliedSource`, `TaskReservation`, `Term`, `TermConcept`, `TermCraft`, `TermSummary`, `TrustTierOverride`, `TwoFactorChallenge`, `UploadLink`, `UsageEvent`, `User`, `UserPreference`, `VoiceSession`, `WebFetch`, `WikidataPoint`.

## HTTP API

**235 operations** in `backend/app/api/routes/` and `backend/app/main.py`: 119 GET, 79 POST, 23 PUT, 2 PATCH, 12 DELETE.

| Module | Operations |
| --- | ---: |
| `auth.py` | 16 |
| `contribution_streams.py` | 12 |
| `users.py` | 9 |
| `image_contributions.py` | 8 |
| `lessons.py` | 8 |
| `crafts.py` | 7 |
| `own_proposals.py` | 7 |
| `profile.py` | 7 |
| `settings.py` | 7 |
| `two_factor.py` | 7 |
| `voice.py` | 7 |
| `access.py` | 6 |
| `artisan_contributions.py` | 6 |
| `explainers.py` | 6 |
| `oauth_consent.py` | 6 |
| `shared.py` | 6 |
| `testimony_review.py` | 6 |
| `artisan_conversations.py` | 5 |
| `review_queue.py` | 5 |
| `knowledge.py` | 4 |
| `knowledge_writes.py` | 4 |
| `learning_views.py` | 4 |
| `page_documents.py` | 4 |
| `page_proposals.py` | 4 |
| `secrets.py` | 4 |
| `upload_links.py` | 4 |
| `explainer_exports.py` | 3 |
| `field_photo_reviews.py` | 3 |
| `field_voices.py` | 3 |
| `media.py` | 3 |
| `notifications.py` | 3 |
| `oauth.py` | 3 |
| `oauth_well_known.py` | 3 |
| `open_work.py` | 3 |
| `saved_explainers.py` | 3 |
| `site_build.py` | 3 |
| `usage.py` | 3 |
| `categories.py` | 2 |
| `coverage.py` | 2 |
| `field_voices_held.py` | 2 |
| `main.py` | 2 |
| `map_layers.py` | 2 |
| `me.py` | 2 |
| `password_change.py` | 2 |
| `place_ground.py` | 2 |
| `supplied_sources.py` | 2 |
| `contributed_pictures.py` | 1 |
| `craft_monograph.py` | 1 |
| `dataset_uploads.py` | 1 |
| `film.py` | 1 |
| `knowledge_export.py` | 1 |
| `listen.py` | 1 |
| `map_districts.py` | 1 |
| `mcp.py` | 1 |
| `molecules.py` | 1 |
| `open_data.py` | 1 |
| `public.py` | 1 |
| `rivers.py` | 1 |
| `simulations.py` | 1 |
| `structure_proposals.py` | 1 |
| `terms.py` | 1 |

## MCP server

**22 tools**, each a `Tool(...)` declared in `backend/app/api/`.

| Module | Tools |
| --- | ---: |
| `mcp_ask_tools.py` | 1 |
| `mcp_dataset_tools.py` | 1 |
| `mcp_fact_tools.py` | 2 |
| `mcp_lookup_tools.py` | 3 |
| `mcp_page_read.py` | 1 |
| `mcp_page_tools.py` | 3 |
| `mcp_picture_tools.py` | 1 |
| `mcp_read_tools.py` | 3 |
| `mcp_source_tools.py` | 1 |
| `mcp_structure_tools.py` | 1 |
| `mcp_studio_sources.py` | 1 |
| `mcp_work_tools.py` | 4 |

## Tests

| Python suite | Files | Tests |
| --- | ---: | ---: |
| Backend, without a database | 518 | 4085 |
| Backend, on Postgres | 124 | 650 |
| Tools | 21 | 183 |
| Craft data ETL | 5 | 46 |
| Geo ETL | 16 | 151 |

| Frontend (`frontend/e2e/`) | Files | Tests |
| --- | ---: | ---: |
| Unit specs (`*-unit.spec.ts`) | 146 | 1126 |
| Browser and release specs | 13 | 46 |

A Python test is a `test_` function in a `test_` file; a frontend test is a `test(` call at the start of a line. Every suite runs on GitHub Actions, never on a development machine.

## Records

| What | Count |
| --- | ---: |
| Decision records (`docs/decisions/`) | 114 |
| Contracts (`docs/contracts/`) | 40 |
| Workflows (`.github/workflows/`) | 24 |
| Curated craft dossiers | 32 |
| Curated category dossiers | 9 |

## Code volume

| Area | Files | Lines |
| --- | ---: | ---: |
| `backend/app` | 1141 | 163,610 |
| `backend/tests` | 779 | 105,529 |
| `backend/migrations` | 57 | 9,087 |
| `frontend/app` | 96 | 9,414 |
| `frontend/components` | 580 | 40,111 |
| `frontend/lib` | 232 | 24,420 |
| `frontend/e2e` | 238 | 27,440 |
| `etl` | 52 | 8,442 |
| `tools` | 93 | 8,099 |
| `infra` | 15 | 1,923 |

Code files are `.py`, `.ts`, `.tsx`, `.mjs`, `.css`, `.sh`, `.tf` and `.sql`; lines are newlines.

## How this document is kept true

| What | How |
|---|---|
| Regenerate | `backend/.venv/Scripts/python.exe tools/repo_facts_build.py` from the repository root (`backend/.venv/bin/python` off Windows) |
| Diff against | `--check`, which exits 1 when this file differs from a fresh count and writes nothing |
| Counted from | the files `git ls-files` lists and the untracked files that are not ignored, the list the hygiene check reads, so regenerate on a clean tree after a round's last merge |
| Rules | `tools/repo_facts/counts.py`, tested by `tools/tests/test_repo_facts.py` on a small tree whose counts are worked out by hand |

Re-read the counting rules when a new kind of table, route, MCP tool or test layout appears: a count is only as true as the pattern that finds it.
