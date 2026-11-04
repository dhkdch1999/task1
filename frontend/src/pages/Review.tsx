import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import CardEditor, { EMPTY_DRAFT } from "../CardEditor";
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
import { go } from "../router";
import { STATUSES } from "../types";
import type { Card, CardDraft, Handover } from "../types";

const SUCCESSOR_TEXT = { none: "아직 안 봄", confirmed: "확인함", question: "질문 있음" } as const;

function toDraft(c: Card): CardDraft {
  const { title, description, cycle, status, category, related_files, related_people, caution } = c;
  return { title, description, cycle, status, category, related_files, related_people, caution };
}

export default function Review({ id }: { id: number }) {
  const [h, setH] = useState<Handover | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get(id).then(setH).catch((e: Error) => setError(e.message));
  }, [id]);

  /** API 호출 후 화면을 갱신한다. 실패하면 오류 문구를 보여 주고 false를 돌려준다. */
  const run = useCallback(async (fn: () => Promise<Handover>): Promise<boolean> => {
    setError(null);
    try {
      setH(await fn());
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    }
  }, []);

  if (!h) {
    return (
      <main className="page">
        <ErrorNote message={error} />
        {!error && <p className="muted">불러오는 중…</p>}
      </main>
    );
  }

  const draft = h.status === "draft";
  const shareUrl = h.share_token ? `${window.location.origin}${window.location.pathname}#/s/${h.share_token}` : "";
  const groups = STATUSES.map((s) => ({ status: s, cards: h.cards.filter((c) => c.status === s) })).filter(
    (g) => g.cards.length,
  );

  const toggleSelect = (cid: number) => {
    const next = new Set(selected);
    if (next.has(cid)) next.delete(cid);
    else next.add(cid);
    setSelected(next);
  };

  const merge = async () => {
    const ids = h.cards.filter((c) => selected.has(c.id)).map((c) => c.id);
    if (await run(() => api.mergeCards(h.id, ids))) setSelected(new Set());
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 클립보드 권한이 없으면 사용자가 직접 복사한다 */
    }
  };

  return (
    <main className="page review">
      <header className="review-head">
        <div>
          <h1 className="page-title">{h.title}</h1>
          <p className="muted">
            {h.owner_name}님이 작성
            {h.successor_name && `, 후임자 ${h.successor_name}님`}
          </p>
        </div>
        <span className={`doc-status ${h.status}`}>{draft ? "검토 중" : "확정됨"}</span>
      </header>

      <section className="stat-strip" aria-label="분석 요약">
        <div>
          <strong>{h.cards.length}</strong>
          <span>찾은 업무</span>
        </div>
        <div>
          <strong>{h.stats.mails}</strong>
          <span>분석한 메일</span>
        </div>
        <div>
          <strong>{h.stats.files}</strong>
          <span>분석한 파일</span>
        </div>
        <div className={h.stats.needs_reply ? "attn" : ""}>
          <strong>{h.cards.filter((c) => c.needs_reply).length}</strong>
          <span>답장 안 한 메일이 있는 업무</span>
        </div>
        <p className="strip-note">
          기준일 {h.stats.base_date} (데이터 안의 가장 최근 날짜)
          {h.stats.excluded &&
            (h.stats.excluded.mails > 0 || h.stats.excluded.files > 0) &&
            `. 메일 ${h.stats.excluded.mails}건과 파일 ${h.stats.excluded.files}개는 제외하고 분석했습니다.`}
        </p>
      </section>

      <ErrorNote message={error} />

      {draft ? (
        <div className="action-bar">
          <p>
            자동으로 만든 초안입니다. 틀린 내용은 고치고, 빠진 업무는 추가하고, 같은 업무는 합친 뒤 확정해 주세요.
          </p>
          <div className="action-buttons">
            <button type="button" className="btn" onClick={() => setEditing("new")}>
              업무 추가
            </button>
            <button type="button" className="btn" disabled={selected.size < 2} onClick={merge}>
              {selected.size >= 2 ? `선택한 ${selected.size}개 합치기` : "합칠 카드를 2개 이상 선택"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => run(() => api.confirm(h.id))}
              disabled={!h.cards.length}
            >
              확정하고 공유 링크 만들기
            </button>
          </div>
        </div>
      ) : (
        <div className="action-bar confirmed">
          <div className="share">
            <span className="field-label">후임자에게 보낼 링크</span>
            <div className="share-row">
              <input readOnly value={shareUrl} onFocus={(e) => e.target.select()} aria-label="공유 링크" />
              <button type="button" className="btn btn-primary" onClick={copy}>
                {copied ? "복사했습니다" : "링크 복사"}
              </button>
              <a className="btn" href={`#/s/${h.share_token}`} target="_blank" rel="noreferrer">
                후임자 화면 열기
              </a>
            </div>
          </div>
          <div className="progress-box">
            <ProgressBar total={h.progress.total} done={h.progress.confirmed} />
            <p>
              후임자가 {h.progress.total}개 중 {h.progress.confirmed}개를 확인했습니다.
              {h.progress.unanswered > 0 && <strong className="attn-text"> 답하지 않은 질문 {h.progress.unanswered}개</strong>}
            </p>
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                if (confirm("확정을 취소하면 공유 링크가 닫히고 다시 수정할 수 있습니다. 취소할까요?"))
                  run(() => api.unconfirm(h.id));
              }}
            >
              확정 취소하고 다시 수정하기
            </button>
          </div>
        </div>
      )}

      <div className="ledger">
        <nav className="index" aria-label="업무 목록">
          {groups.map((g) => (
            <div key={g.status} className={`index-group ${STATUS_CLASS[g.status]}`}>
              <div className="index-head">
                {g.status} <span>{g.cards.length}</span>
              </div>
              <ul>
                {g.cards.map((c) => (
                  <li key={c.id}>
                    <a href={`#/h/${h.id}`} onClick={(e) => {
                      e.preventDefault();
                      document.getElementById(`card-${c.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}>
                      {c.title}
                      {c.needs_reply && <span className="dot" aria-label="답장 안 한 메일 있음" />}
                      {!draft && c.successor_state !== "none" && (
                        <span className={`succ succ-${c.successor_state}`}>{SUCCESSOR_TEXT[c.successor_state]}</span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <a className="index-contacts" href={`#/h/${h.id}`} onClick={(e) => {
            e.preventDefault();
            document.getElementById("contacts")?.scrollIntoView({ behavior: "smooth" });
          }}>
            업무 연락처 {h.contacts.length}명
          </a>
        </nav>

        <div className="cards">
          {editing === "new" && (
            <article className="card sheet editing">
              <h2 className="editor-title">새 업무 추가</h2>
              <CardEditor
                initial={EMPTY_DRAFT}
                saveLabel="업무 추가하기"
                onCancel={() => setEditing(null)}
                onSave={async (d) => {
                  if (await run(() => api.addCard(h.id, d))) setEditing(null);
                }}
              />
            </article>
          )}

          {h.cards.length === 0 && editing !== "new" && (
            <div className="sheet empty">
              <p>찾은 업무가 없습니다. 제외 필터를 너무 많이 걸었거나 메일 날짜가 없을 수 있어요.</p>
              <button type="button" className="btn" onClick={() => setEditing("new")}>
                업무 직접 추가하기
              </button>
            </div>
          )}

          {h.cards.map((c) => (
            <article key={c.id} id={`card-${c.id}`} className={`card sheet ${STATUS_CLASS[c.status]}`}>
              {editing === c.id ? (
                <CardEditor
                  initial={toDraft(c)}
                  onCancel={() => setEditing(null)}
                  onSave={async (d) => {
                    if (await run(() => api.updateCard(h.id, c.id, d))) setEditing(null);
                  }}
                />
              ) : (
                <>
                  <div className="card-top">
                    {draft && (
                      <input
                        type="checkbox"
                        className="select"
                        aria-label={`${c.title} 선택`}
                        checked={selected.has(c.id)}
                        onChange={() => toggleSelect(c.id)}
                      />
                    )}
                    <div className="card-titles">
                      <h2>{c.title}</h2>
                      <CardMeta card={c} />
                    </div>
                    {draft && (
                      <div className="card-actions">
                        <button type="button" className="btn btn-small" onClick={() => setEditing(c.id)}>
                          수정
                        </button>
                        <button
                          type="button"
                          className="btn btn-small btn-quiet"
                          onClick={() => {
                            if (confirm(`'${c.title}' 카드를 지울까요?`)) run(() => api.deleteCard(h.id, c.id));
                          }}
                        >
                          삭제
                        </button>
                      </div>
                    )}
                    {!draft && (
                      <span className={`succ succ-${c.successor_state}`}>{SUCCESSOR_TEXT[c.successor_state]}</span>
                    )}
                  </div>

                  {c.description && <p className="desc">{c.description}</p>}

                  {c.caution ? (
                    <div className="caution">
                      <div className="field-label">주의사항</div>
                      <p>{c.caution}</p>
                    </div>
                  ) : (
                    draft && (
                      <button type="button" className="caution-empty" onClick={() => setEditing(c.id)}>
                        주의사항을 적어 두면 후임자가 실수를 덜 합니다. 적으러 가기
                      </button>
                    )
                  )}

                  <div className="card-cols">
                    <div>
                      <div className="field-label">관련 파일</div>
                      <FileList files={c.related_files} />
                    </div>
                    <div>
                      <div className="field-label">관련 담당자</div>
                      <PeopleList people={c.related_people} />
                    </div>
                  </div>

                  <EvidenceList evidence={c.evidence} total={c.evidence_total} />

                  {!draft && (c.comments.length > 0 || c.successor_state === "question") && (
                    <div className="qa">
                      <div className="field-label">후임자 질문</div>
                      <CommentThread
                        comments={c.comments}
                        me="predecessor"
                        ownerName={h.owner_name}
                        successorName={h.successor_name ?? "후임자"}
                        placeholder="질문에 답해 주세요"
                        onSend={async (body) => {
                          await run(() => api.reply(h.id, c.id, body));
                        }}
                      />
                    </div>
                  )}
                </>
              )}
            </article>
          ))}

          <ContactsTable contacts={h.contacts} />

          {draft && (
            <p className="danger-zone">
              <button
                type="button"
                className="link-btn danger"
                onClick={async () => {
                  if (!confirm("이 인수인계 초안을 완전히 지울까요? 되돌릴 수 없습니다.")) return;
                  await api.remove(h.id);
                  go("/");
                }}
              >
                이 초안 지우기
              </button>
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

export function ProgressBar({ total, done }: { total: number; done: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
