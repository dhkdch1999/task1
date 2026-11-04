import os
import tempfile

os.environ["HANDOVER_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
PERSONAL = ["minji.kim1990@gmail.com", "deal@shopping-mall.example", "noreply@quick-parcel.example"]


def create():
    sample = client.get("/api/sample").json()
    body = {**sample, "filters": {"exclude_senders": PERSONAL, "exclude_folders": ["D:/개인", "D:/다운로드"]}}
    r = client.post("/api/handovers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_preview_suggests_personal_exclusions():
    sample = client.get("/api/sample").json()
    r = client.post("/api/preview", json={"mails": sample["mails"], "files": sample["files"]})
    data = r.json()
    assert data["mail_count"] == 50 and data["file_count"] == 80
    assert data["owner_email"] == "jihoon.park@danbi-corp.example"
    suggested = {s["email"] for s in data["senders"] if s["suggest_exclude"]}
    assert set(PERSONAL) <= suggested
    assert not any(s["email"].endswith("@danbi-corp.example") for s in data["senders"] if s["suggest_exclude"])
    folders = {f["path"]: f["suggest_exclude"] for f in data["folders"]}
    assert folders["D:/개인"] and folders["D:/개인/사진"] and folders["D:/다운로드"]
    assert not folders["D:/업무/01_주간보고"] and not folders["D:/업무/04_프로젝트"]


def test_full_flow_draft_edit_confirm_share():
    h = create()
    hid = h["id"]
    assert h["status"] == "draft" and len(h["cards"]) >= 8
    assert h["stats"]["excluded"] == {"mails": 4, "files": 6}

    # 수정
    first = h["cards"][0]
    r = client.patch(f"/api/handovers/{hid}/cards/{first['id']}",
                     json={"caution": "11월 15일까지 날인 필수", "title": "하늘물류 계약 갱신"})
    assert r.json()["cards"][0]["caution"] == "11월 15일까지 날인 필수"

    # 추가
    r = client.post(f"/api/handovers/{hid}/cards", json={"title": "비품 창고 열쇠 관리", "status": "참고"})
    added = [c for c in r.json()["cards"] if c["title"] == "비품 창고 열쇠 관리"][0]
    assert added["confidence"] == "manual"

    # 병합
    ids = [c["id"] for c in r.json()["cards"]]
    before = len(ids)
    r = client.post(f"/api/handovers/{hid}/cards/merge", json={"card_ids": [ids[-1], ids[-2]], "title": "총무 기타"})
    assert len(r.json()["cards"]) == before - 1

    # 삭제
    r = client.delete(f"/api/handovers/{hid}/cards/{ids[-1]}")
    assert len(r.json()["cards"]) == before - 2

    # 확정 전에는 공유 링크가 열리지 않는다
    assert client.get("/api/share/whatever").status_code == 404

    r = client.post(f"/api/handovers/{hid}/confirm")
    token = r.json()["share_token"]
    assert r.json()["status"] == "confirmed" and token

    # 확정 후에는 수정 불가
    assert client.patch(f"/api/handovers/{hid}/cards/{first['id']}", json={"caution": "x"}).status_code == 409

    # 후임자: 확인·질문
    shared = client.get(f"/api/share/{token}").json()
    cid = shared["cards"][0]["id"]
    r = client.put(f"/api/share/{token}/cards/{cid}/check", json={"state": "confirmed"})
    assert r.json()["progress"]["confirmed"] == 1
    cid2 = shared["cards"][1]["id"]
    r = client.post(f"/api/share/{token}/cards/{cid2}/comments", json={"body": "견적 비교표 최종본이 어느 건가요?"})
    data = r.json()
    assert data["progress"]["question"] == 1 and data["progress"]["unanswered"] == 1

    # 전임자 답변
    r = client.post(f"/api/handovers/{hid}/cards/{cid2}/comments", json={"body": "이사업체_견적비교.xlsx가 최종입니다."})
    assert r.json()["progress"]["unanswered"] == 0

    # 확정 취소 후 다시 수정 가능, 공유 링크는 닫힘
    client.post(f"/api/handovers/{hid}/unconfirm")
    assert client.get(f"/api/share/{token}").status_code == 404
    assert client.patch(f"/api/handovers/{hid}/cards/{first['id']}", json={"caution": "y"}).status_code == 200


def test_raw_mail_is_not_stored():
    create()
    import sqlite3
    conn = sqlite3.connect(os.environ["HANDOVER_DB"])
    dump = "\n".join(conn.iterdump())
    assert "드림" not in dump  # 메일 본문 서명
    assert "010-9876-5432" not in dump
    assert "동창" not in dump


def test_empty_upload_rejected():
    r = client.post("/api/handovers", json={"owner_name": "a", "mails": [], "files": []})
    assert r.status_code == 400
