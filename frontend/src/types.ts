export type Cycle = "매일" | "매주" | "매월" | "분기" | "비정기";
export type Status = "진행 중" | "정기" | "참고" | "완료";
export type SuccessorState = "none" | "confirmed" | "question";
export type Confidence = "high" | "medium" | "low" | "manual";

export interface Person {
  name: string;
  email: string;
  org: string | null;
}

export interface Evidence {
  kind: "mail" | "file";
  label: string;
  date: string | null;
}

export interface Comment {
  id: number;
  card_id: number;
  author: "predecessor" | "successor";
  body: string;
  created_at: string;
}

export interface Card {
  id: number;
  position: number;
  title: string;
  description: string;
  cycle: Cycle;
  status: Status;
  category: string;
  related_files: string[];
  related_people: Person[];
  caution: string;
  evidence: Evidence[];
  evidence_total: number;
  confidence: Confidence;
  needs_reply: boolean;
  successor_state: SuccessorState;
  comments: Comment[];
}

export interface Contact {
  id: number;
  name: string;
  email: string;
  org: string | null;
  internal: boolean;
  count: number;
}

export interface Stats {
  mails: number;
  files: number;
  owner_email: string | null;
  base_date: string | null;
  cards: number;
  needs_reply: number;
  excluded?: { mails: number; files: number };
  warnings?: string[];
}

export interface Progress {
  total: number;
  confirmed: number;
  question: number;
  unanswered: number;
}

export interface Handover {
  id: number;
  title: string;
  owner_name: string;
  owner_email: string | null;
  successor_name: string | null;
  status: "draft" | "confirmed";
  share_token: string | null;
  stats: Stats;
  created_at: string;
  confirmed_at: string | null;
  cards: Card[];
  contacts: Contact[];
  progress: Progress;
}

export interface HandoverSummary {
  id: number;
  title: string;
  owner_name: string;
  successor_name: string | null;
  status: "draft" | "confirmed";
  created_at: string;
  card_count: number;
}

export interface SourceFile {
  name: string;
  content: string;
}

export interface Preview {
  owner_email: string | null;
  mail_count: number;
  file_count: number;
  date_range: [string, string] | null;
  senders: { email: string; name: string; count: number; sample_subject: string; suggest_exclude: boolean }[];
  folders: { path: string; count: number; suggest_exclude: boolean }[];
  warnings: string[];
}

export interface CardDraft {
  title: string;
  description: string;
  cycle: Cycle;
  status: Status;
  category: string;
  related_files: string[];
  related_people: Person[];
  caution: string;
}

export const CYCLES: Cycle[] = ["매일", "매주", "매월", "분기", "비정기"];
export const STATUSES: Status[] = ["진행 중", "정기", "참고", "완료"];
