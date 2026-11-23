export type UserRole = "MASTER_ADMIN" | "ADMIN" | "PROFESSOR" | "RESEARCHER" | "ARTISAN" | "STUDENT";

export type RecordStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "NEEDS_REVISION";

export type PageResult<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
};

export type User = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatarUrl?: string | null;
  authProvider?: string;
  affiliation?: string | null;
  mustChangePassword?: boolean;
  passwordSetAt?: string | null;
  hasPassword?: boolean;
  twoFactorEnabled?: boolean;
  twoFactorEnabledAt?: string | null;
  twoFactorRequired?: boolean;
  emailVerifiedAt?: string | null;
  firstLoginAt?: string | null;
  lastLoginAt?: string | null;
  isActive?: boolean;
  suspendedAt?: string | null;
  capabilities?: string[];
  guardianConsent?: "CONFIRMED" | "NOT_CONFIRMED";
  profileRequired?: boolean;
  guardianConsentRequired?: boolean;
};

export type EvidenceLevel = "VERIFIED" | "REVIEWED" | "PROVISIONAL" | "HYPOTHESIS" | "UNAVAILABLE";

export type EvidenceKind = "QUOTED" | "INFERRED";

export type AnswerMode = "VERIFIED" | "HYBRID" | "DEEP";

export type AnswerStatusStep = "PLANNING" | "SEARCHING_STORED" | "RESEARCHING" | "READING" | "COMPOSING" | "WRITING_BACK" | "TRANSLATING";

export type AnswerStatus = { step: AnswerStatusStep; message: string };

export type SourceReliability = "A" | "B" | "C" | "D";

export type SourceRef = {
  id: string;
  kind: string;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  url: string | null;
  publisher: string | null;
  containerTitle?: string;
  licence: string | null;
  attribution: string | null;
  reliability: SourceReliability | null;
};

export type Citation = {
  id: string;
  claimId: string;
  sourceId: string;
  quote: string | null;
  locator: string | null;
  context: string | null;
  evidence: EvidenceKind;
  level: EvidenceLevel;
};

export type AnswerSentence = {
  id: string;
  text: string;
  level: EvidenceLevel;
  citations: Citation[];
  translated?: boolean;
  original?: string;
};

export type AnswerSection = {
  id: string;
  heading: string;
  original?: string;
  sentences: AnswerSentence[];
};

export type CraftRef = {
  slug: string;
  name: string;
  path?: string | null;
};

export type CraftMapPoint = {
  key: string;
  name: string;
  latitude: number;
  longitude: number;
  total: number;
  crafts: CraftRef[];
};
