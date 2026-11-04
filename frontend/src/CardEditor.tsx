import { useState } from "react";
import { CYCLES, STATUSES } from "./types";
import type { CardDraft, Person } from "./types";

function peopleToText(people: Person[]) {
  return people.map((p) => [p.name, p.org ?? "", p.email].join(", ")).join("\n");
}

function textToPeople(text: string): Person[] {
  return text
    .split("\n")
    .map((line) => line.split(",").map((s) => s.trim()))
    .filter((parts) => parts[0])
    .map(([name, org, email]) => ({ name, org: org || null, email: email || "" }));
}

export const EMPTY_DRAFT: CardDraft = {
  title: "",
  description: "",
  cycle: "비정기",
  status: "정기",
  category: "기타",
  related_files: [],
  related_people: [],
  caution: "",
};

export default function CardEditor({
  initial,
  onSave,
  onCancel,
  saveLabel = "저장하기",
}: {
  initial: CardDraft;
  onSave: (draft: CardDraft) => Promise<void>;
  onCancel: () => void;
  saveLabel?: string;
}) {
  const [d, setD] = useState<CardDraft>(initial);
  const [filesText, setFilesText] = useState(initial.related_files.join("\n"));
  const [peopleText, setPeopleText] = useState(peopleToText(initial.related_people));
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof CardDraft>(key: K, value: CardDraft[K]) => setD({ ...d, [key]: value });

  const save = async () => {
    setBusy(true);
    try {
      await onSave({
        ...d,
        title: d.title.trim(),
        related_files: filesText.split("\n").map((s) => s.trim()).filter(Boolean),
        related_people: textToPeople(peopleText),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="editor"
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <label className="full">
        <span>업무명</span>
        <input value={d.title} onChange={(e) => set("title", e.target.value)} required autoFocus />
      </label>
      <label>
        <span>상태</span>
        <select value={d.status} onChange={(e) => set("status", e.target.value as CardDraft["status"])}>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label>
        <span>주기</span>
        <select value={d.cycle} onChange={(e) => set("cycle", e.target.value as CardDraft["cycle"])}>
          {CYCLES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </label>
      <label>
        <span>분류</span>
        <input value={d.category} onChange={(e) => set("category", e.target.value)} />
      </label>
      <label className="full">
        <span>업무 설명</span>
        <textarea rows={4} value={d.description} onChange={(e) => set("description", e.target.value)} />
      </label>
      <label className="full marker-field">
        <span>주의사항</span>
        <textarea
          rows={3}
          value={d.caution}
          placeholder="실수하기 쉬운 부분, 마감, 꼭 확인할 사람 등을 적어 주세요"
          onChange={(e) => set("caution", e.target.value)}
        />
      </label>
      <label className="full">
        <span>관련 파일 (한 줄에 하나)</span>
        <textarea rows={3} value={filesText} onChange={(e) => setFilesText(e.target.value)} />
      </label>
      <label className="full">
        <span>관련 담당자 (한 줄에 "이름, 소속, 메일")</span>
        <textarea rows={3} value={peopleText} onChange={(e) => setPeopleText(e.target.value)} />
      </label>
      <div className="editor-actions full">
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          취소
        </button>
        <button type="submit" className="btn btn-primary" disabled={busy || !d.title.trim()}>
          {busy ? "저장하는 중…" : saveLabel}
        </button>
      </div>
    </form>
  );
}
