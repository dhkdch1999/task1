import { useEffect, useMemo, useState } from "react";
import { api, readFiles } from "../api";
import { ErrorNote } from "../components";
import { go } from "../router";
import type { Preview, SourceFile } from "../types";

const POWERSHELL =
  'Get-ChildItem D:\\업무 -Recurse -File | Select-Object FullName, LastWriteTime, Length | Export-Csv files.csv -Encoding UTF8 -NoTypeInformation';

export default function NewHandover() {
  const [title, setTitle] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [successorName, setSuccessorName] = useState("");
  const [mails, setMails] = useState<SourceFile[]>([]);
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [usingSample, setUsingSample] = useState(false);

  const [preview, setPreview] = useState<Preview | null>(null);
  const [excludedSenders, setExcludedSenders] = useState<Set<string>>(new Set());
  const [excludedFolders, setExcludedFolders] = useState<Set<string>>(new Set());
  const [keywords, setKeywords] = useState("");

  const [busy, setBusy] = useState<"" | "sample" | "preview" | "analyze">("");
  const [error, setError] = useState<string | null>(null);

  const loadSample = async () => {
    setBusy("sample");
    setError(null);
    try {
      const s = await api.sample();
      setTitle(s.title);
      setOwnerName(s.owner_name);
      setOwnerEmail(s.owner_email);
      setSuccessorName(s.successor_name);
      setMails(s.mails);
      setFiles(s.files);
      setUsingSample(true);
      setPreview(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  useEffect(() => {
    if (window.location.hash.includes("sample=1")) loadSample();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 데이터가 바뀌면 미리보기를 다시 해야 한다
  useEffect(() => setPreview(null), [mails, files]);

  const runPreview = async () => {
    setBusy("preview");
    setError(null);
    try {
      const p = await api.preview({ owner_email: ownerEmail || undefined, mails, files });
      setPreview(p);
      setExcludedSenders(new Set(p.senders.filter((s) => s.suggest_exclude).map((s) => s.email)));
      setExcludedFolders(new Set(p.folders.filter((f) => f.suggest_exclude).map((f) => f.path)));
      if (!ownerEmail && p.owner_email) setOwnerEmail(p.owner_email);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const analyze = async () => {
    setBusy("analyze");
    setError(null);
    try {
      const h = await api.create({
        title: title || undefined,
        owner_name: ownerName,
        owner_email: ownerEmail || undefined,
        successor_name: successorName || undefined,
        mails,
        files,
        filters: {
          exclude_senders: [...excludedSenders],
          exclude_folders: [...excludedFolders],
          exclude_keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
        },
      });
      go(`/h/${h.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy("");
    }
  };

  const toggle = (set: Set<string>, value: string, update: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    update(next);
  };

  const keptMails = useMemo(() => {
    if (!preview) return 0;
    const excluded = preview.senders
      .filter((s) => excludedSenders.has(s.email))
      .reduce((n, s) => n + s.count, 0);
    return preview.mail_count - excluded;
  }, [preview, excludedSenders]);

  const keptFiles = useMemo(() => {
    if (!preview) return 0;
    const excluded = preview.folders
      .filter((f) => excludedFolders.has(f.path))
      .reduce((n, f) => n + f.count, 0);
    return preview.file_count - excluded;
  }, [preview, excludedFolders]);

  const hasData = mails.length > 0 || files.length > 0;

  return (
    <main className="page narrow">
      <h1 className="page-title">새 인수인계 만들기</h1>
      <p className="lede">
        업로드한 메일과 파일 목록은 분석에만 쓰고 저장하지 않습니다. 결과는 확정하기 전까지 본인만
        볼 수 있습니다.
      </p>

      <div className="sample-banner">
        <div>
          <strong>처음이라면 샘플로 흐름을 먼저 보세요.</strong>
          <p>가상의 경영지원팀 직원 박지훈 대리의 메일 50건과 파일 80개가 들어 있습니다.</p>
        </div>
        <button type="button" className="btn" onClick={loadSample} disabled={busy !== ""}>
          {busy === "sample" ? "불러오는 중…" : usingSample ? "샘플 다시 불러오기" : "샘플 데이터 불러오기"}
        </button>
      </div>

      <ol className="steps">
        <li className="step">
          <h2>기본 정보</h2>
          <div className="form-grid">
            <label>
              <span>인수인계 제목</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="예: 홍길동 대리 인수인계 (경영지원팀)" />
            </label>
            <label>
              <span>내 이름</span>
              <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required />
            </label>
            <label>
              <span>내 업무 메일 주소</span>
              <input
                type="email"
                value={ownerEmail}
                onChange={(e) => setOwnerEmail(e.target.value)}
                placeholder="비워 두면 가장 많이 쓴 주소로 찾습니다"
              />
            </label>
            <label>
              <span>후임자 이름</span>
              <input value={successorName} onChange={(e) => setSuccessorName(e.target.value)} placeholder="정해지지 않았다면 비워 두세요" />
            </label>
          </div>
        </li>

        <li className="step">
          <h2>메일과 파일 목록 넣기</h2>
          <div className="upload-grid">
            <div className="upload">
              <label className="upload-label">
                <span>업무 메일</span>
                <input
                  type="file"
                  multiple
                  accept=".eml,.mbox,.csv"
                  onChange={async (e) => {
                    setMails(await readFiles(e.target.files));
                    setUsingSample(false);
                  }}
                />
              </label>
              <p className="hint">.eml 여러 개, .mbox, 또는 메일 목록 CSV(제목, 보낸 사람, 받는 사람, 날짜, 첨부 열)</p>
              {mails.length > 0 && <p className="loaded">{mails.map((m) => m.name).join(", ")}</p>}
            </div>
            <div className="upload">
              <label className="upload-label">
                <span>업무 폴더 파일 목록</span>
                <input
                  type="file"
                  multiple
                  accept=".csv,.txt"
                  onChange={async (e) => {
                    setFiles(await readFiles(e.target.files));
                    setUsingSample(false);
                  }}
                />
              </label>
              <p className="hint">파일 내용은 필요 없고 경로·수정일·크기 목록만 씁니다. Windows PowerShell에서 만들 수 있어요.</p>
              <code className="cmd">{POWERSHELL}</code>
              {files.length > 0 && <p className="loaded">{files.map((f) => f.name).join(", ")}</p>}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!hasData || busy !== ""}
            onClick={runPreview}
          >
            {busy === "preview" ? "확인하는 중…" : "불러온 내용 확인하기"}
          </button>
        </li>

        <li className={`step ${preview ? "" : "step-locked"}`}>
          <h2>분석에서 뺄 것 고르기</h2>
          {!preview ? (
            <p className="muted">내용을 확인하면 개인 메일로 보이는 보낸 사람과 개인 폴더를 미리 골라 드립니다.</p>
          ) : (
            <>
              <p className="summary-line">
                메일 {preview.mail_count}건
                {preview.date_range && ` (${preview.date_range[0]} ~ ${preview.date_range[1]})`}, 파일 {preview.file_count}개를
                읽었습니다. 내 주소는 <strong>{preview.owner_email ?? "찾지 못함"}</strong>로 보고 분석합니다.
              </p>
              {preview.warnings.map((w) => (
                <p key={w} className="warn">
                  {w}
                </p>
              ))}
              <div className="exclude-grid">
                <fieldset>
                  <legend>보낸 사람</legend>
                  <p className="hint">체크한 사람이 보낸 메일은 분석하지 않습니다.</p>
                  <ul className="check-list">
                    {preview.senders.map((s) => (
                      <li key={s.email}>
                        <label>
                          <input
                            type="checkbox"
                            checked={excludedSenders.has(s.email)}
                            onChange={() => toggle(excludedSenders, s.email, setExcludedSenders)}
                          />
                          <span className="cl-main">
                            {s.name} <span className="muted">{s.email}</span>
                          </span>
                          <span className="cl-sub">
                            {s.count}건, 예: {s.sample_subject}
                          </span>
                          {s.suggest_exclude && <span className="suggest">개인 메일로 보임</span>}
                        </label>
                      </li>
                    ))}
                  </ul>
                </fieldset>
                <fieldset>
                  <legend>폴더</legend>
                  <p className="hint">체크한 폴더 아래 파일은 분석하지 않습니다.</p>
                  <ul className="check-list">
                    {preview.folders.map((f) => (
                      <li key={f.path}>
                        <label>
                          <input
                            type="checkbox"
                            checked={excludedFolders.has(f.path)}
                            onChange={() => toggle(excludedFolders, f.path, setExcludedFolders)}
                          />
                          <span className="cl-main">{f.path}</span>
                          <span className="cl-sub">{f.count}개</span>
                          {f.suggest_exclude && <span className="suggest">개인 폴더로 보임</span>}
                        </label>
                      </li>
                    ))}
                  </ul>
                  <label className="kw">
                    <span>제외할 단어</span>
                    <input
                      value={keywords}
                      onChange={(e) => setKeywords(e.target.value)}
                      placeholder="쉼표로 구분, 예: 연봉, 건강검진"
                    />
                  </label>
                  <p className="hint">제목·본문·파일 경로에 이 단어가 들어 있으면 뺍니다.</p>
                </fieldset>
              </div>
            </>
          )}
        </li>

        <li className={`step ${preview ? "" : "step-locked"}`}>
          <h2>분석하기</h2>
          {preview && (
            <p className="summary-line">
              메일 약 {keptMails}건과 파일 약 {keptFiles}개로 인수인계 초안을 만듭니다.
            </p>
          )}
          <ErrorNote message={error} />
          <button
            type="button"
            className="btn btn-primary btn-big"
            disabled={!preview || !ownerName.trim() || busy !== ""}
            onClick={analyze}
          >
            {busy === "analyze" ? "분석하는 중…" : "인수인계 초안 만들기"}
          </button>
          {preview && !ownerName.trim() && <p className="hint">기본 정보에 내 이름을 적어 주세요.</p>}
        </li>
      </ol>
    </main>
  );
}
