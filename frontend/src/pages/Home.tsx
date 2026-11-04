import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNote } from "../components";
import type { HandoverSummary } from "../types";

export default function Home() {
  const [items, setItems] = useState<HandoverSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.list().then(setItems).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="page home">
      <section className="hero">
        <h1>
          메일과 업무 폴더에 남은 흔적으로
          <br />
          인수인계서 초안을 만듭니다
        </h1>
        <p className="lede">
          본인의 업무 메일과 D드라이브 파일 목록을 넣으면, 반복 업무와 진행 중인 일, 연락할 사람을
          찾아 정리해 드립니다. 검토하고 확정하면 후임자에게 링크로 넘길 수 있어요.
        </p>
        <div className="hero-actions">
          <a href="#/new" className="btn btn-primary">
            인수인계 시작하기
          </a>
          <a href="#/new?sample=1" className="btn">
            샘플 데이터로 먼저 보기
          </a>
        </div>
        <ul className="promise">
          <li>분석은 본인이 직접 실행하고, 결과도 본인이 먼저 검토합니다.</li>
          <li>메일 원문은 저장하지 않고 정리된 결과만 남깁니다.</li>
          <li>개인 메일과 개인 폴더는 분석 전에 뺄 수 있습니다.</li>
        </ul>
      </section>

      <section className="sheet">
        <h2>내 인수인계</h2>
        <ErrorNote message={error} />
        {items === null && !error && <p className="muted">불러오는 중…</p>}
        {items?.length === 0 && (
          <p className="muted">아직 만든 인수인계가 없습니다. 위에서 시작해 보세요.</p>
        )}
        {!!items?.length && (
          <ul className="handover-list">
            {items.map((h) => (
              <li key={h.id}>
                <a href={`#/h/${h.id}`}>
                  <span className="hl-title">{h.title}</span>
                  <span className="hl-meta">
                    업무 {h.card_count}개
                    {h.successor_name && `, 후임 ${h.successor_name}`}
                  </span>
                  <span className={`hl-status ${h.status}`}>
                    {h.status === "confirmed" ? "확정됨" : "검토 중"}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
