from datetime import datetime, timedelta

from app.analyzer import analyze, clean_title, cycle_from_intervals, file_base, topic_key
from app.parsers import KST, SourceFile, parse_datetime, parse_file_list, parse_mail_source
from app.privacy import Filters, apply_filters, mask_pii
from app.sample_data import build_files_csv, build_mbox, sample_payload

OWNER = "jihoon.park@danbi-corp.example"
PERSONAL = ["minji.kim1990@gmail.com", "deal@shopping-mall.example", "noreply@quick-parcel.example"]


def load_sample():
    mails = parse_mail_source(SourceFile("s.mbox", build_mbox()))
    files = parse_file_list(SourceFile("s.csv", build_files_csv()))
    return mails, files


def by_title(cards, word):
    found = [c for c in cards if word in c["title"]]
    assert found, f"'{word}' 카드가 없습니다: {[c['title'] for c in cards]}"
    return found[0]


# ---------------------------------------------------------------- 파서


def test_sample_counts():
    mails, files = load_sample()
    assert len(mails) == 50
    assert len(files) == 80
    assert mails[0].attachments == ["주간업무보고_2026_W36.xlsx"]
    assert all(f.path.startswith("D:/") for f in files)


def test_parse_korean_powershell_dates():
    assert parse_datetime("2026-10-30 오후 3:12:00") == datetime(2026, 10, 30, 15, 12, tzinfo=KST)
    assert parse_datetime("2026. 10. 30. 오전 12:05") == datetime(2026, 10, 30, 0, 5, tzinfo=KST)
    assert parse_datetime("2026-10-30T09:00:00") == datetime(2026, 10, 30, 9, 0, tzinfo=KST)


def test_mail_csv_and_path_list():
    csv_text = "제목,보낸 사람,받는 사람,날짜,첨부\n주간보고,a@x.example,b@x.example,2026-10-01 09:00,r.xlsx\n"
    mails = parse_mail_source(SourceFile("m.csv", csv_text))
    assert mails[0].subject == "주간보고" and mails[0].attachments == ["r.xlsx"]
    files = parse_file_list(SourceFile("f.txt", "D:\\업무\\a.xlsx\nD:\\업무\\b.docx\n"))
    assert [f.path for f in files] == ["D:/업무/a.xlsx", "D:/업무/b.docx"]


# ---------------------------------------------------------------- 정규화·주기


def test_subject_normalization():
    assert clean_title("RE: [요청] 10월 법인카드 사용내역 제출") == "법인카드 사용내역 제출"
    assert topic_key("[주간보고] 주간업무보고 (10월 4주차)") == topic_key("[주간보고] 주간업무보고 (9월 1주차)")
    assert file_base("주간업무보고_2026_W43.xlsx") == file_base("주간업무보고_2026_W30.xlsx")
    assert file_base("사무실이전_레이아웃_v3.pptx") == file_base("사무실이전_레이아웃_v1.pptx")


def test_cycle_detection():
    start = datetime(2026, 1, 5, tzinfo=KST)
    assert cycle_from_intervals([start + timedelta(weeks=i) for i in range(5)]) == "매주"
    assert cycle_from_intervals([start + timedelta(days=30 * i) for i in range(4)]) == "매월"
    # 요청 직후 회신이 섞여도 매월로 본다
    monthly = [start + timedelta(days=30 * i) for i in range(4)] + [start + timedelta(days=92)]
    assert cycle_from_intervals(monthly) == "매월"
    assert cycle_from_intervals([start, start + timedelta(days=50)]) == "비정기"


# ---------------------------------------------------------------- 전체 분석 (샘플)


def analyzed(filters=None):
    mails, files = load_sample()
    mails, files, _ = apply_filters(mails, files, filters or Filters(
        exclude_senders=PERSONAL, exclude_folders=["D:/개인", "D:/다운로드"]))
    return analyze(mails, files, OWNER)


def test_planted_duties_are_found():
    cards = analyzed().cards
    weekly = by_title(cards, "주간업무보고")
    assert weekly["cycle"] == "매주" and weekly["status"] == "정기" and weekly["confidence"] == "high"
    assert any("주간업무보고_2026_W43" in p for p in weekly["related_files"])

    assert by_title(cards, "비용 정산")["cycle"] == "매월"
    assert by_title(cards, "법인카드")["cycle"] == "매월"
    assert by_title(cards, "사무용품")["cycle"] == "매월"
    assert by_title(cards, "부가세")["cycle"] == "분기"
    assert by_title(cards, "장비")["status"] == "완료"


def test_thread_is_not_mistaken_for_recurring():
    logi = by_title(analyzed().cards, "하늘물류")
    assert logi["status"] == "진행 중"
    assert logi["cycle"] == "비정기"
    assert logi["needs_reply"] is True
    assert any("2027_계약갱신안" in p for p in logi["related_files"])


def test_project_folder_linked_by_subject():
    office = by_title(analyzed().cards, "사무실 이전")
    assert office["status"] == "진행 중"
    assert office["related_files"][0].endswith("사무실이전_레이아웃_v3.pptx")  # 최신 버전이 맨 앞
    assert any("버전" in e["label"] for e in office["evidence"])


def test_noise_and_personal_mail_never_become_cards():
    # 필터 없이 돌려도 단발성·개인 메일은 카드가 되지 않는다
    cards = analyzed(Filters()).cards
    titles = " ".join(c["title"] for c in cards)
    for word in ["동창", "특가", "배송", "추석", "회식", "보안 교육"]:
        assert word not in titles


def test_pii_is_masked_in_results():
    result = analyzed()
    text = str(result.cards)
    assert "010-9876-5432" not in text and "010-2345-6789" not in text
    assert "010-****-****" in text


def test_filters_exclude_everything_requested():
    mails, files = load_sample()
    m2, f2, ex = apply_filters(mails, files, Filters(
        exclude_senders=PERSONAL, exclude_keywords=["회식"], exclude_folders=["D:/개인"]))
    assert ex == {"mails": 5, "files": 5}  # 키워드는 파일명(회식장소_후보.png)에도 적용된다
    assert not any("회식" in m.subject for m in m2)


def test_mask_pii():
    assert mask_pii("문의 010-1234-5678, 주민 900101-1234567") == "문의 010-****-****, 주민 ******-*******"
    assert mask_pii("a@b.example 로") == "***@*** 로"


def test_sample_payload_shape():
    p = sample_payload()
    assert p["owner_email"] == OWNER and len(p["mails"]) == 1 and len(p["files"]) == 1
