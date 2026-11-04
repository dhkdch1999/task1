import { useState } from "react";
import type { Card, Comment, Confidence, Contact, Evidence, Person, Status } from "./types";

export const STATUS_CLASS: Record<Status, string> = {
  "진행 중": "st-active",
  정기: "st-routine",
  참고: "st-ref",
  완료: "st-done",
};

const CONFIDENCE_TEXT: Record<Confidence, string> = {
  high: "근거 충분",
  medium: "근거 보통",
  low: "근거 적음, 확인 필요",
  manual: "직접 추가",
};

export function StatusLabel({ status }: { status: Status }) {
  return <span className={`status ${STATUS_CLASS[status]}`}>{status}</span>;
}

export function CardMeta({ card }: { card: Card }) {
  return (
    <div className="card-meta">
      <StatusLabel status={card.status} />
      {card.cycle !== "비정기" && <span className="meta-item">{card.cycle}</span>}
      <span className="meta-item">{card.category}</span>
      <span className={`meta-item conf conf-${card.confidence}`}>{CONFIDENCE_TEXT[card.confidence]}</span>
      {card.needs_reply && <span className="reply-flag">답장 안 한 메일 있음</span>}
    </div>
  );
}

function fileName(path: string) {
  return path.split("/").pop() ?? path;
}
function fileFolder(path: string) {
  const i = path.lastIndexOf("/");
  return i > 0 ? path.slice(0, i) : "";
}

export function FileList({ files }: { files: string[] }) {
  if (!files.length) return <p className="muted small">연결된 파일이 없습니다.</p>;
  return (
    <ul className="file-list">
      {files.map((f) => (
        <li key={f}>
          <span className="file-name">{fileName(f)}</span>
          <span className="file-folder">{fileFolder(f)}</span>
        </li>
      ))}
    </ul>
  );
}

export function PeopleList({ people }: { people: Person[] }) {
  if (!people.length) return <p className="muted small">연결된 담당자가 없습니다.</p>;
  return (
    <ul className="people-list">
      {people.map((p) => (
        <li key={p.email || p.name}>
          <span className="person-name">{p.name}</span>
          {p.org && <span className="person-org">{p.org}</span>}
          {p.email && (
            <a className="person-mail" href={`mailto:${p.email}`}>
              {p.email}
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

export function EvidenceList({ evidence, total }: { evidence: Evidence[]; total: number }) {
  const [open, setOpen] = useState(false);
  if (!evidence.length) return null;
  const shown = open ? evidence : evidence.slice(0, 2);
  return (
    <div className="evidence">
      <div className="field-label">이렇게 판단한 근거</div>
      <ul>
        {shown.map((e, i) => (
          <li key={i} className={`ev ev-${e.kind}`}>
            <span className="ev-kind">{e.kind === "mail" ? "메일" : "파일"}</span>
            <span className="ev-label">{e.label}</span>
            {e.date && <span className="ev-date">{e.date}</span>}
          </li>
        ))}
      </ul>
      {evidence.length > 2 && (
        <button type="button" className="link-btn" onClick={() => setOpen(!open)}>
          {open ? "근거 접기" : `근거 ${evidence.length - 2}개 더 보기`}
        </button>
      )}
      {total > evidence.length && open && (
        <p className="muted small">전체 {total}개 흔적 중 일부만 표시합니다.</p>
      )}
    </div>
  );
}

export function ContactsTable({ contacts }: { contacts: Contact[] }) {
  if (!contacts.length) return null;
  return (
    <section className="sheet contacts" id="contacts">
      <h2>업무 연락처</h2>
      <p className="muted">메일을 주고받은 횟수가 많은 순서입니다.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">이름</th>
              <th scope="col">소속</th>
              <th scope="col">메일</th>
              <th scope="col" className="num">
                주고받은 메일
              </th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>
                  {c.org}
                  {!c.internal && <span className="ext-tag">외부</span>}
                </td>
                <td>
                  <a href={`mailto:${c.email}`}>{c.email}</a>
                </td>
                <td className="num">{c.count}건</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CommentThread({
  comments,
  me,
  ownerName,
  successorName,
  onSend,
  placeholder,
}: {
  comments: Comment[];
  me: "predecessor" | "successor";
  ownerName: string;
  successorName: string;
  onSend: (body: string) => Promise<void>;
  placeholder: string;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await onSend(text.trim());
      setText("");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="thread">
      {comments.map((c) => (
        <div key={c.id} className={`bubble ${c.author === me ? "mine" : "theirs"}`}>
          <span className="bubble-who">{c.author === "predecessor" ? ownerName : successorName}</span>
          <p>{c.body}</p>
        </div>
      ))}
      <div className="thread-input">
        <textarea
          rows={2}
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
        />
        <button type="button" className="btn" disabled={busy || !text.trim()} onClick={send}>
          {me === "predecessor" ? "답변 보내기" : "질문 보내기"}
        </button>
      </div>
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="error" role="alert">
      {message}
    </p>
  );
}
