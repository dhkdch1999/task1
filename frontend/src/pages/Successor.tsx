import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import {
  CardMeta,
  CommentThread,
  ContactsTable,
  ErrorNote,
  EvidenceList,
  FileList,
  PeopleList,
  STATUS_CLASS,
} from "../components";
import type { Handover, SuccessorState } from "../types";
import { ProgressBar } from "./Review";

export default function Successor({ token }: { token: string }) {
  const [h, setH] = useState<Handover | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<number | null>(null);

  useEffect(() => {
    api.shared(token).then(setH).catch((e: Error) => setError(e.message));
  }, [token]);

  const run = useCallback(async (fn: () => Promise<Handover>) => {
    setError(null);
    try {
      setH(await fn());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  if (!h) {
    return (
      <div className="shell">
        <main className="page narrow">
          <ErrorNote message={error} />
          {!error && <p className="muted">불러오는 중…</p>}
        </main>
      </div>
    );
  }

  const setState = (cid: number, current: SuccessorState, next: SuccessorState) =>
    run(() => api.check(token, cid, current === next ? "none" : next));

  const p = h.progress;

  return (
    <div className="shell successor-view">
      <header className="topbar">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true" />
          인수인계 장부
        </span>
      </header>
      <main className="page narrow">
        <h1 className="page-title">{h.owner_name}님이 넘겨준 업무</h1>
        <p className="lede">
          {h.successor_name ? `${h.successor_name}님, ` : ""}업무마다 내용을 읽고 이해했으면 '확인함'을, 궁금한 점이
          있으면 '질문 있음'을 눌러 질문을 남겨 주세요. {h.owner_name}님이 떠나기 전에 질문이 모두 풀리는 게
          목표입니다.
        </p>

        <section className="sheet progress-sheet">
          <ProgressBar total={p.total} done={p.confirmed} />
          <p>
            {p.total}개 중 <strong>{p.confirmed}개 확인</strong>
            {p.question > 0 && `, 질문 있음 ${p.question}개`}
            {p.unanswered > 0 && `, 답변 기다리는 중 ${p.unanswered}개`}
          </p>
        </section>

        <ErrorNote message={error} />

        <div className="cards">
          {h.cards.map((c) => (
            <article key={c.id} className={`card sheet ${STATUS_CLASS[c.status]} succ-card-${c.successor_state}`}>
              <div className="card-top">
                <div className="card-titles">
                  <h2>{c.title}</h2>
                  <CardMeta card={c} />
                </div>
              </div>
              {c.description && <p className="desc">{c.description}</p>}
              {c.caution && (
                <div className="caution">
                  <div className="field-label">주의사항</div>
                  <p>{c.caution}</p>
                </div>
              )}
              <div className="card-cols">
                <div>
                  <div className="field-label">관련 파일</div>
                  <FileList files={c.related_files} />
                </div>
                <div>
                  <div className="field-label">물어볼 사람</div>
                  <PeopleList people={c.related_people} />
                </div>
              </div>
              <EvidenceList evidence={c.evidence} total={c.evidence_total} />

              <div className="check-row">
                <button
                  type="button"
                  className={`check-btn ${c.successor_state === "confirmed" ? "on ok" : ""}`}
                  aria-pressed={c.successor_state === "confirmed"}
                  onClick={() => setState(c.id, c.successor_state, "confirmed")}
                >
                  확인함
                </button>
                <button
                  type="button"
                  className={`check-btn ${c.successor_state === "question" ? "on ask" : ""}`}
                  aria-pressed={c.successor_state === "question"}
                  onClick={() => {
                    if (c.successor_state !== "question") setAsking(c.id);
                    setState(c.id, c.successor_state, "question");
                  }}
                >
                  질문 있음
                </button>
              </div>

              {(c.comments.length > 0 || c.successor_state === "question" || asking === c.id) && (
                <div className="qa">
                  <CommentThread
                    comments={c.comments}
                    me="successor"
                    ownerName={h.owner_name}
                    successorName={h.successor_name ?? "나"}
                    placeholder={`${h.owner_name}님에게 물어볼 내용을 적어 주세요`}
                    onSend={(body) => run(() => api.ask(token, c.id, body))}
                  />
                </div>
              )}
            </article>
          ))}
          <ContactsTable contacts={h.contacts} />
        </div>
      </main>
    </div>
  );
}
