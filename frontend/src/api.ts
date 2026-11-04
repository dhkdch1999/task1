import type {
  CardDraft,
  Handover,
  HandoverSummary,
  Preview,
  SourceFile,
  SuccessorState,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = `요청에 실패했습니다 (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* 본문이 JSON이 아니면 기본 문구를 쓴다 */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export interface SamplePayload {
  owner_name: string;
  owner_email: string;
  successor_name: string;
  title: string;
  mails: SourceFile[];
  files: SourceFile[];
}

export interface AnalyzePayload {
  title?: string;
  owner_name: string;
  owner_email?: string;
  successor_name?: string;
  mails: SourceFile[];
  files: SourceFile[];
  filters: { exclude_senders: string[]; exclude_keywords: string[]; exclude_folders: string[] };
}

export const api = {
  sample: () => request<SamplePayload>("/api/sample"),
  preview: (body: { owner_email?: string; mails: SourceFile[]; files: SourceFile[] }) =>
    request<Preview>("/api/preview", { method: "POST", body: json(body) }),
  create: (body: AnalyzePayload) =>
    request<Handover>("/api/handovers", { method: "POST", body: json(body) }),
  list: () => request<HandoverSummary[]>("/api/handovers"),
  get: (id: number) => request<Handover>(`/api/handovers/${id}`),
  remove: (id: number) => request<void>(`/api/handovers/${id}`, { method: "DELETE" }),
  addCard: (id: number, card: CardDraft) =>
    request<Handover>(`/api/handovers/${id}/cards`, { method: "POST", body: json(card) }),
  updateCard: (id: number, cid: number, patch: Partial<CardDraft>) =>
    request<Handover>(`/api/handovers/${id}/cards/${cid}`, { method: "PATCH", body: json(patch) }),
  deleteCard: (id: number, cid: number) =>
    request<Handover>(`/api/handovers/${id}/cards/${cid}`, { method: "DELETE" }),
  mergeCards: (id: number, cardIds: number[], title?: string) =>
    request<Handover>(`/api/handovers/${id}/cards/merge`, {
      method: "POST",
      body: json({ card_ids: cardIds, title }),
    }),
  confirm: (id: number) => request<Handover>(`/api/handovers/${id}/confirm`, { method: "POST" }),
  unconfirm: (id: number) => request<Handover>(`/api/handovers/${id}/unconfirm`, { method: "POST" }),
  reply: (id: number, cid: number, body: string) =>
    request<Handover>(`/api/handovers/${id}/cards/${cid}/comments`, {
      method: "POST",
      body: json({ body }),
    }),
  shared: (token: string) => request<Handover>(`/api/share/${token}`),
  check: (token: string, cid: number, state: SuccessorState) =>
    request<Handover>(`/api/share/${token}/cards/${cid}/check`, {
      method: "PUT",
      body: json({ state }),
    }),
  ask: (token: string, cid: number, body: string) =>
    request<Handover>(`/api/share/${token}/cards/${cid}/comments`, {
      method: "POST",
      body: json({ body }),
    }),
};

export function readFiles(list: FileList | null): Promise<SourceFile[]> {
  if (!list) return Promise.resolve([]);
  return Promise.all(
    Array.from(list).map(
      (file) =>
        new Promise<SourceFile>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve({ name: file.name, content: String(reader.result ?? "") });
          reader.onerror = () => reject(new Error(`'${file.name}' 파일을 읽지 못했습니다.`));
          reader.readAsText(file, "utf-8");
        }),
    ),
  );
}
