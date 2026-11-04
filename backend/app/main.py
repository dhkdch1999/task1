"""FastAPI 앱.

실행:  uvicorn app.main:app --reload      (backend 폴더에서)
문서:  http://localhost:8000/docs
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import analyze
from .db import Database
from .models import (AnalyzeIn, CardIn, CardPatch, CheckIn, CommentIn, MergeIn,
                     PreviewIn, ReorderIn)
from .parsers import FileEntry, Mail, SourceFile, parse_file_list, parse_mail_source
from .privacy import Filters, apply_filters, looks_personal_folder, looks_personal_mail
from .sample_data import sample_payload

MAX_UPLOAD_CHARS = 60_000_000  # 약 60MB 텍스트

DB_PATH = os.environ.get("HANDOVER_DB", str(Path(__file__).resolve().parent.parent / "data" / "handover.db"))
db = Database(DB_PATH)

app = FastAPI(title="인수인계 초안 생성기 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ 공통


def _parse(payload: PreviewIn) -> tuple[list[Mail], list[FileEntry], list[str]]:
    total = sum(len(s.content) for s in [*payload.mails, *payload.files])
    if total > MAX_UPLOAD_CHARS:
        raise HTTPException(413, "업로드한 파일이 너무 큽니다. 60MB 이하로 나눠서 올려 주세요.")
    mails: list[Mail] = []
    files: list[FileEntry] = []
    warnings: list[str] = []
    for s in payload.mails:
        try:
            parsed = parse_mail_source(SourceFile(s.name, s.content))
        except Exception:  # noqa: BLE001
            parsed = []
        if not parsed:
            warnings.append(f"'{s.name}'에서 메일을 읽지 못했습니다. .eml, .mbox, CSV 형식인지 확인해 주세요.")
        mails.extend(parsed)
    for s in payload.files:
        parsed_f = parse_file_list(SourceFile(s.name, s.content))
        if not parsed_f:
            warnings.append(f"'{s.name}'에서 파일 목록을 읽지 못했습니다. 경로 열이 있는 CSV인지 확인해 주세요.")
        files.extend(parsed_f)
    undated = sum(1 for m in mails if m.date is None)
    if undated:
        warnings.append(f"날짜가 없는 메일 {undated}건은 반복 주기 분석에서 빠집니다.")
    return mails, files, warnings


def _owner_of(mails: list[Mail], owner_email: str | None) -> str | None:
    if owner_email:
        return owner_email.strip().lower()
    c: Counter[str] = Counter()
    for m in mails:
        c[m.sender_email] += 1
        for _, a in m.to:
            c[a] += 1
    return c.most_common(1)[0][0] if c else None


def _detail(hid: int) -> dict:
    h = db.get_handover(hid)
    if not h:
        raise HTTPException(404, "인수인계를 찾을 수 없습니다.")
    cards = db.cards(hid)
    return {**h, "cards": cards, "contacts": db.contacts(hid), "progress": _progress(cards)}


def _progress(cards: list[dict]) -> dict:
    total = len(cards)
    confirmed = sum(1 for c in cards if c["successor_state"] == "confirmed")
    question = sum(1 for c in cards if c["successor_state"] == "question")
    return {"total": total, "confirmed": confirmed, "question": question,
            "unanswered": sum(1 for c in cards if c["comments"] and c["comments"][-1]["author"] == "successor")}


def _editable(hid: int) -> dict:
    h = db.get_handover(hid)
    if not h:
        raise HTTPException(404, "인수인계를 찾을 수 없습니다.")
    if h["status"] == "confirmed":
        raise HTTPException(409, "확정된 인수인계는 수정할 수 없습니다. 확정을 취소한 뒤 수정해 주세요.")
    return h


# ------------------------------------------------------------------ 입력·분석


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/sample")
def get_sample() -> dict:
    """데모용 샘플 데이터(메일 50건 mbox, 파일 80개 CSV)."""
    return sample_payload()


@app.post("/api/preview")
def preview(payload: PreviewIn) -> dict:
    """분석 전에 무엇이 들어왔는지 보여주고, 제외할 만한 보낸 사람·폴더를 추천한다. 아무것도 저장하지 않는다."""
    mails, files, warnings = _parse(payload)
    owner = _owner_of(mails, payload.owner_email)
    owner_domain = owner.split("@")[-1] if owner else None

    by_sender: dict[str, list[Mail]] = defaultdict(list)
    for m in mails:
        if m.sender_email != owner:
            by_sender[m.sender_email].append(m)
    senders = []
    for addr, ms in by_sender.items():
        subjects = [m.subject for m in ms]
        senders.append({
            "email": addr,
            "name": ms[0].sender_name,
            "count": len(ms),
            "sample_subject": subjects[0][:60],
            "suggest_exclude": looks_personal_mail(addr, subjects, owner_domain),
        })
    senders.sort(key=lambda s: (not s["suggest_exclude"], -s["count"]))

    folder_counts: Counter[str] = Counter()
    for f in files:
        # 'D:/업무/01_주간보고' 처럼 드라이브 아래 두 단계까지 묶어서 보여 준다
        parts = f.path.split("/")[:-1]
        folder_counts["/".join(parts[:3])] += 1
    folders = [{"path": p, "count": n, "suggest_exclude": looks_personal_folder(p)}
               for p, n in sorted(folder_counts.items())]

    dates = sorted(m.date for m in mails if m.date)
    return {
        "owner_email": owner,
        "mail_count": len(mails),
        "file_count": len(files),
        "date_range": [dates[0].date().isoformat(), dates[-1].date().isoformat()] if dates else None,
        "senders": senders,
        "folders": folders,
        "warnings": warnings,
    }


@app.post("/api/handovers", status_code=201)
def create_handover(payload: AnalyzeIn) -> dict:
    """업로드 데이터를 분석해 인수인계 초안을 만든다. 원본은 분석 후 버리고 결과만 저장한다."""
    mails, files, warnings = _parse(payload)
    if not mails and not files:
        raise HTTPException(400, "분석할 메일이나 파일 목록이 없습니다.")
    f = payload.filters
    mails, files, excluded = apply_filters(
        mails, files, Filters(f.exclude_senders, f.exclude_keywords, f.exclude_folders))
    result = analyze(mails, files, payload.owner_email)
    stats = {**result.stats, "excluded": excluded, "warnings": warnings}
    title = payload.title or f"{payload.owner_name}님 인수인계"
    hid = db.create_handover(title, payload.owner_name, result.stats.get("owner_email"),
                             payload.successor_name, stats, result.cards, result.contacts)
    return _detail(hid)


# ------------------------------------------------------------------ 전임자 화면


@app.get("/api/handovers")
def list_handovers() -> list[dict]:
    return db.list_handovers()


@app.get("/api/handovers/{hid}")
def get_handover(hid: int) -> dict:
    return _detail(hid)


@app.delete("/api/handovers/{hid}", status_code=204)
def delete_handover(hid: int) -> None:
    if not db.get_handover(hid):
        raise HTTPException(404, "인수인계를 찾을 수 없습니다.")
    db.delete_handover(hid)


@app.post("/api/handovers/{hid}/cards", status_code=201)
def add_card(hid: int, card: CardIn) -> dict:
    _editable(hid)
    data = card.model_dump()
    data["evidence"] = []
    data["confidence"] = "manual"
    db.add_card(hid, data)
    return _detail(hid)


@app.patch("/api/handovers/{hid}/cards/{cid}")
def update_card(hid: int, cid: int, patch: CardPatch) -> dict:
    _editable(hid)
    if not db.get_card(hid, cid):
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    db.update_card(hid, cid, patch.model_dump(exclude_none=True))
    return _detail(hid)


@app.delete("/api/handovers/{hid}/cards/{cid}")
def delete_card(hid: int, cid: int) -> dict:
    _editable(hid)
    db.delete_cards(hid, [cid])
    return _detail(hid)


@app.post("/api/handovers/{hid}/cards/merge")
def merge_cards(hid: int, body: MergeIn) -> dict:
    """여러 카드를 하나로 합친다. 첫 번째 카드에 나머지 내용을 모은다."""
    _editable(hid)
    cards = [db.get_card(hid, cid) for cid in body.card_ids]
    if any(c is None for c in cards):
        raise HTTPException(404, "합칠 카드 중 없는 카드가 있습니다.")
    base, rest = cards[0], cards[1:]
    assert base is not None
    priority = {"진행 중": 0, "정기": 1, "참고": 2, "완료": 3}
    all_cards = [base, *rest]
    files = list(dict.fromkeys(p for c in all_cards for p in c["related_files"]))  # type: ignore[index]
    people: dict[str, dict] = {}
    for c in all_cards:
        for p in c["related_people"]:  # type: ignore[index]
            people.setdefault(p.get("email") or p["name"], p)
    db.update_card(hid, base["id"], {
        "title": body.title or base["title"],
        "description": "\n\n".join(c["description"] for c in all_cards if c["description"]),  # type: ignore[index]
        "status": min((c["status"] for c in all_cards), key=lambda s: priority.get(s, 9)),  # type: ignore[index]
        "related_files": files,
        "related_people": list(people.values()),
        "caution": "\n".join(c["caution"] for c in all_cards if c["caution"]),  # type: ignore[index]
        "evidence": [e for c in all_cards for e in c["evidence"]],  # type: ignore[index]
        "evidence_total": sum(c["evidence_total"] for c in all_cards),  # type: ignore[index]
        "needs_reply": any(c["needs_reply"] for c in all_cards),  # type: ignore[index]
    })
    db.delete_cards(hid, [c["id"] for c in rest])  # type: ignore[index]
    return _detail(hid)


@app.put("/api/handovers/{hid}/order")
def reorder(hid: int, body: ReorderIn) -> dict:
    _editable(hid)
    db.reorder(hid, body.card_ids)
    return _detail(hid)


@app.post("/api/handovers/{hid}/confirm")
def confirm(hid: int) -> dict:
    _editable(hid)
    db.set_confirmed(hid, True)
    return _detail(hid)


@app.post("/api/handovers/{hid}/unconfirm")
def unconfirm(hid: int) -> dict:
    if not db.get_handover(hid):
        raise HTTPException(404, "인수인계를 찾을 수 없습니다.")
    db.set_confirmed(hid, False)
    return _detail(hid)


@app.post("/api/handovers/{hid}/cards/{cid}/comments", status_code=201)
def predecessor_comment(hid: int, cid: int, body: CommentIn) -> dict:
    """전임자가 후임자의 질문에 답한다 (확정 후에도 가능)."""
    if not db.get_card(hid, cid):
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    db.add_comment(cid, "predecessor", body.body)
    return _detail(hid)


# ------------------------------------------------------------------ 후임자 화면 (공유 링크)


def _shared(token: str) -> dict:
    h = db.get_handover_by_token(token)
    if not h:
        raise HTTPException(404, "공유 링크가 없거나 아직 확정되지 않은 인수인계입니다.")
    return h


@app.get("/api/share/{token}")
def get_shared(token: str) -> dict:
    return _detail(_shared(token)["id"])


@app.put("/api/share/{token}/cards/{cid}/check")
def check_card(token: str, cid: int, body: CheckIn) -> dict:
    h = _shared(token)
    if not db.get_card(h["id"], cid):
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    db.update_card(h["id"], cid, {"successor_state": body.state})
    return _detail(h["id"])


@app.post("/api/share/{token}/cards/{cid}/comments", status_code=201)
def successor_comment(token: str, cid: int, body: CommentIn) -> dict:
    h = _shared(token)
    card = db.get_card(h["id"], cid)
    if not card:
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    db.add_comment(cid, "successor", body.body)
    if card["successor_state"] == "none":
        db.update_card(h["id"], cid, {"successor_state": "question"})
    return _detail(h["id"])


# ------------------------------------------------------------------ 빌드된 프론트엔드 서빙

DIST = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(404, "없는 API 경로입니다.")
        target = (DIST / full_path).resolve()
        if full_path and target.is_file() and target.is_relative_to(DIST.resolve()):
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
