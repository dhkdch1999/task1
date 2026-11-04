"""샘플 2(공작기계 제어개발 엔지니어)로 개발 직군 데이터에서도 업무가 제대로 잡히는지 확인한다."""
from app.analyzer import analyze, clean_title, is_automated
from app.parsers import SourceFile, parse_file_list, parse_mail_source
from app.privacy import Filters, apply_filters
from app.sample_cnc import OWNER, build_files_csv, build_mbox

PERSONAL = ["sungmin.choi88@gmail.com", "ad@tool-market.example", "noreply@quick-parcel.example"]


def cards():
    mails = parse_mail_source(SourceFile("c.mbox", build_mbox()))
    files = parse_file_list(SourceFile("c.csv", build_files_csv()))
    assert len(mails) == 50 and len(files) == 90
    mails, files, _ = apply_filters(mails, files, Filters(exclude_senders=PERSONAL, exclude_folders=["D:/개인", "D:/다운로드"]))
    return analyze(mails, files, OWNER[1]).cards


def card(cs, word):
    found = [c for c in cs if word in c["title"]]
    assert found, [c["title"] for c in cs]
    return found[0]


def test_engineering_duties():
    cs = cards()
    assert card(cs, "주간 진척")["cycle"] == "매주"
    release = card(cs, "정기 배포")
    assert release["cycle"] == "매월" and release["category"] == "개발·릴리스"
    assert any(p.endswith(".bin") for p in release["related_files"])  # 같은 폴더의 펌웨어 이미지도 함께
    field = card(cs, "필드 불량")
    assert field["cycle"] == "매월" and field["category"] == "품질·불량"
    assert card(cs, "기능안전")["cycle"] == "분기"


def test_customer_issue_in_progress():
    c = card(card_list := cards(), "채터링")
    assert c["title"].startswith("대성오토텍 HX-500")  # 모델명 하이픈 유지
    assert c["status"] == "진행 중" and c["needs_reply"] and c["category"] == "고객 대응"
    assert c["related_files"][0].endswith("서보튜닝파라미터_v3.xlsx")  # 최신 버전이 맨 앞
    assert "010-****-****" in c["description"]
    assert card(card_list, "EtherCAT")["status"] == "진행 중"


def test_build_alerts_are_not_unanswered_mail():
    c = card(cards(), "야간 빌드")
    assert c["title"] == "cnc-fw-main 야간 빌드 실패"
    assert c["cycle"] == "매일" and not c["needs_reply"]
    assert "자동 알림" in c["description"]
    assert is_automated("jenkins@hangyeol-mt.example") and is_automated("no-reply@x.example")
    assert not is_automated(OWNER[1]) and not is_automated("minseok.choi@hangyeol-mt.example")


def test_vendor_folder_linked_by_sender_org():
    c = card(cards(), "호환성")
    assert c["status"] == "완료"
    assert any("세진모션" in p for p in c["related_files"])


def test_title_cleanup():
    assert clean_title("[Jenkins] cnc-fw-main 야간 빌드 실패 (10/29)") == "cnc-fw-main 야간 빌드 실패"
    assert clean_title("RE: 대성오토텍 HX-500 고속 가공 채터링 발생 건") == "대성오토텍 HX-500 고속 가공 채터링 발생"
