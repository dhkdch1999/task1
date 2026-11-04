"""데모용 샘플 데이터 생성기.

가상의 직원 '박지훈 대리(경영지원팀)'의 업무 메일 50건과 D드라이브 파일 목록 80개를 만든다.
샘플에는 정기 보고, 정산, 거래처 대응, 진행 중인 프로젝트, 개인 메일이 섞여 있다.
모든 회사·사람·도메인은 가상이며 도메인은 .example 을 쓴다.

python -m app.sample_data  을 실행하면 sample/ 폴더에 업로드용 파일도 만든다.
"""
from __future__ import annotations

import csv
import io
import mailbox
import os
import tempfile
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, formataddr

from .parsers import KST

D = "danbi-corp.example"
OWNER = ("박지훈 (경영지원팀)", f"jihoon.park@{D}")
LEADER = ("김현우 (경영지원팀)", f"hyunwoo.kim@{D}")
FIN = ("이서연 (재무팀)", f"seoyeon.lee@{D}")
FIN2 = ("정민호 (재무팀)", f"minho.jung@{D}")
TEAM = [("최유나 (경영지원팀)", f"yuna.choi@{D}"), ("한도윤 (경영지원팀)", f"doyoon.han@{D}"),
        ("오승현 (경영지원팀)", f"seunghyun.oh@{D}")]
FAC = ("윤재석 (시설팀)", f"jaeseok.yoon@{D}")
IT = ("강하늘 (IT지원팀)", f"haneul.kang@{D}")
HR = ("서지민 (인사팀)", f"jimin.seo@{D}")
ALL = ("전사공지", f"notice@{D}")
VENDOR_OFFICE = ("최다은 (그린오피스)", "daeun.choi@greenoffice.example")
VENDOR_LOGI = ("문태준 (하늘물류)", "taejun.moon@haneul-logistics.example")
VENDOR_TAX = ("배수진 (미래세무법인)", "sujin.bae@mirae-tax.example")
FRIEND = ("김민지", "minji.kim1990@gmail.com")
SHOP = ("오늘의특가", "deal@shopping-mall.example")
PARCEL = ("빠른택배", "noreply@quick-parcel.example")

BASE = datetime(2026, 10, 30, 18, 0, tzinfo=KST)


def _d(y: int, m: int, d: int, h: int = 10, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=KST)


def _mails() -> list[dict]:
    m: list[dict] = []

    def add(frm, to, date, subject, body, cc=(), att=(), reply_to=None):
        m.append(dict(frm=frm, to=list(to), cc=list(cc), date=date, subject=subject,
                      body=body, att=list(att), reply_to=reply_to))
        return len(m) - 1

    # 1. 주간 업무보고 취합 (매주 월요일, 팀장에게) — 8건 + 팀장 회신 2건
    for i in range(8):
        week = 36 + i
        day = _d(2026, 9, 7, 9, 30) + timedelta(weeks=i)
        idx = add(OWNER, [LEADER], day, f"[주간보고] 경영지원팀 주간업무보고 ({day.month}월 {((day.day - 1) // 7) + 1}주차)",
                  "팀장님, 팀원들 주간업무 취합한 보고서 첨부드립니다. 금주 주요 일정도 함께 정리했습니다.",
                  cc=TEAM[:1], att=[f"주간업무보고_2026_W{week}.xlsx"])
        if i in (3, 6):
            add(LEADER, [OWNER], day + timedelta(hours=3), f"RE: [주간보고] 경영지원팀 주간업무보고 ({day.month}월 {((day.day - 1) // 7) + 1}주차)",
                "확인했습니다. 다음 주부터는 이슈 항목을 맨 위로 올려 주세요.", reply_to=idx)

    # 2. 월간 비용 정산 (매월 초, 재무팀) — 5건
    for i, mo in enumerate([6, 7, 8, 9, 10]):
        add(OWNER, [FIN], _d(2026, mo, 3 + (i % 2), 14), f"{mo - 1 if mo > 1 else 12}월 경영지원팀 비용 정산 자료 송부",
            "지난달 부서 비용 정산 자료 송부드립니다. 증빙은 공유폴더에 올려두었습니다.",
            cc=[FIN2], att=[f"월간비용정산_2026_{mo - 1:02d}.xlsx"])

    # 3. 법인카드 사용내역 취합 요청 (매월 말, 팀원에게) — 5건
    for mo, day in [(6, 25), (7, 25), (8, 26), (9, 25), (10, 26)]:
        idx = add(OWNER, TEAM, _d(2026, mo, day, 11), f"[요청] {mo}월 법인카드 사용내역 제출",
                  f"{mo}월 법인카드 사용내역을 이번 주 금요일까지 양식에 맞춰 제출 부탁드립니다. 영수증 사진도 첨부해 주세요.",
                  att=["법인카드_사용내역_양식.xlsx"])
        if mo == 10:
            add(TEAM[1], [OWNER], _d(2026, mo, 28, 15), f"RE: [요청] {mo}월 법인카드 사용내역 제출",
                "10월 사용내역 제출합니다. 택시비 영수증 1건은 분실해서 사유서 같이 붙였습니다.", reply_to=idx)

    # 4. 사무용품 발주 (매월, 그린오피스) — 발주 4건 + 회신 2건
    for i, (mo, day) in enumerate([(7, 10), (8, 11), (9, 10), (10, 12)]):
        idx = add(OWNER, [VENDOR_OFFICE], _d(2026, mo, day, 15), f"단비코퍼레이션 {mo}월 사무용품 발주서",
                  "이번 달 사무용품 발주서 보내드립니다. 납품은 다음 주 화요일 오전에 부탁드립니다.",
                  att=[f"사무용품_발주서_2026_{mo:02d}.xlsx"])
        if i in (1, 3):
            add(VENDOR_OFFICE, [OWNER], _d(2026, mo, day + 1, 10), f"RE: 단비코퍼레이션 {mo}월 사무용품 발주서",
                "발주서 확인했습니다. 복사용지 A4는 재고 부족으로 하루 늦게 들어갑니다. 문의는 010-2345-6789로 주세요.",
                reply_to=idx)

    # 5. 하늘물류 계약 갱신 (진행 중, 마지막 메일에 미회신) — 5건
    t = add(VENDOR_LOGI, [OWNER], _d(2026, 10, 8, 10), "하늘물류 2027년 물류 계약 갱신 건",
            "내년도 계약 갱신 관련해 단가 조정안을 보내드립니다. 검토 후 의견 부탁드립니다.", att=["2027_계약갱신안_v1.pdf"])
    add(OWNER, [VENDOR_LOGI], _d(2026, 10, 13, 16), "RE: 하늘물류 2027년 물류 계약 갱신 건",
        "보내주신 안 검토했습니다. 기본 운임 인상률 5%는 내부 기준을 넘어서 재조정이 필요합니다.", cc=[LEADER], reply_to=t)
    add(VENDOR_LOGI, [OWNER], _d(2026, 10, 20, 11), "RE: RE: 하늘물류 2027년 물류 계약 갱신 건",
        "인상률 3.5%로 조정한 수정안 보내드립니다.", att=["2027_계약갱신안_v2.pdf"], reply_to=t)
    add(OWNER, [LEADER], _d(2026, 10, 21, 9), "FW: 하늘물류 2027년 물류 계약 갱신 건",
        "팀장님, 하늘물류 수정안 공유드립니다. 3.5%면 내부 기준 안이라 진행해도 될 것 같습니다.", reply_to=t)
    add(VENDOR_LOGI, [OWNER], _d(2026, 10, 28, 17), "RE: 하늘물류 2027년 물류 계약 갱신 건",
        "수정안 검토 결과 회신 부탁드립니다. 11월 15일까지 날인이 되어야 내년 1월 1일부터 적용됩니다. 담당 문태준 010-9876-5432",
        reply_to=t)

    # 6. 사무실 이전 레이아웃 프로젝트 (진행 중, 시설팀) — 4건
    t = add(FAC, [OWNER], _d(2026, 10, 5, 14), "사무실 이전 레이아웃 검토 요청",
            "12월 3층 이전 건으로 레이아웃 초안 공유드립니다. 경영지원팀 좌석 배치 의견 부탁드립니다.", att=["사무실이전_레이아웃_v1.pptx"])
    add(OWNER, [FAC], _d(2026, 10, 7, 11), "RE: 사무실 이전 레이아웃 검토 요청",
        "회의실 위치를 창가 쪽으로 옮기는 안으로 수정해서 보내드립니다.", cc=[LEADER], att=["사무실이전_레이아웃_v2.pptx"], reply_to=t)
    add(FAC, [OWNER], _d(2026, 10, 22, 15), "RE: 사무실 이전 레이아웃 검토 요청",
        "수정안 반영했고, 이사업체 견적 3곳 받았습니다. 비교표 같이 봐주세요.", att=["사무실이전_레이아웃_v3.pptx", "이사업체_견적비교.xlsx"], reply_to=t)
    add(OWNER, [FAC], _d(2026, 10, 27, 10), "RE: 사무실 이전 레이아웃 검토 요청",
        "견적 비교 검토 중입니다. 이번 주 안에 업체 선정 의견 드리겠습니다.", reply_to=t)

    # 7. 분기 세무 자료 (미래세무법인) — 2건
    for mo, q in [(7, 2), (10, 3)]:
        add(OWNER, [VENDOR_TAX], _d(2026, mo, 15, 10), f"{q}분기 부가세 신고 자료 전달",
            f"{q}분기 부가세 신고용 매입매출 자료 전달드립니다.", cc=[FIN], att=[f"부가세신고자료_2026_Q{q}.xlsx"])
    add(VENDOR_TAX, [OWNER], _d(2026, 10, 24, 10), "RE: 3분기 부가세 신고 자료 전달",
        "자료 확인했습니다. 매입 세금계산서 2건이 누락되어 있어 이번 주 안에 보내주셔야 신고 기한에 맞출 수 있습니다.")

    # 8. 신입 입사자 장비 세팅 (완료, IT지원팀) — 3건
    t = add(HR, [OWNER, IT], _d(2026, 8, 18, 10), "9월 신규 입사자 장비 준비 요청",
            "9월 1일 입사자 2명 노트북과 계정 준비 부탁드립니다.")
    add(OWNER, [IT], _d(2026, 8, 19, 9), "RE: 9월 신규 입사자 장비 준비 요청",
        "노트북 2대 신청서 첨부합니다. 자산번호 등록까지 부탁드립니다.", att=["신규입사자_장비체크리스트.xlsx"], reply_to=t)
    add(IT, [OWNER, HR], _d(2026, 8, 28, 16), "RE: 9월 신규 입사자 장비 준비 요청",
        "노트북 2대 세팅 완료했습니다. 계정 정보는 입사 당일 전달하겠습니다.", reply_to=t)

    # 9. 개인 메일 — 4건 (분석 제외 대상)
    add(FRIEND, [OWNER], _d(2026, 10, 16, 20), "이번 달 동창 모임 장소 정해졌어", "토요일 7시 강남역 근처로 정했어! 올 수 있어?")
    add(SHOP, [OWNER], _d(2026, 10, 19, 8), "[광고] 회원님만을 위한 주말 특가", "최대 70% 할인 쿠폰이 도착했습니다.")
    add(SHOP, [OWNER], _d(2026, 10, 26, 8), "[광고] 적립금 소멸 예정 안내", "보유 적립금이 이번 달 말 소멸됩니다.")
    add(PARCEL, [OWNER], _d(2026, 10, 24, 13), "주문하신 상품이 배송 출발했습니다", "운송장번호 1234-5678-9012")

    # 10. 단발성 메일 (카드가 되면 안 됨)
    add(ALL, [OWNER], _d(2026, 9, 30, 9), "[전사공지] 추석 연휴 사무실 운영 안내", "연휴 기간 출입 통제 안내드립니다.")
    add(ALL, [OWNER], _d(2026, 10, 14, 9), "[전사공지] 정보보안 교육 이수 안내", "이번 달 말까지 온라인 교육을 이수해 주세요.")
    add(LEADER, TEAM + [OWNER], _d(2026, 10, 23, 17), "다음 주 팀 회식 장소 투표", "목요일 저녁 회식 장소 투표 부탁드립니다.")
    add(FIN2, [OWNER], _d(2026, 10, 29, 11), "법인카드 한도 상향 문의 답변",
        "요청하신 한도 상향은 다음 달 1일부터 적용됩니다. 확인 부탁드립니다.")

    assert len(m) == 50, len(m)
    return m


def _files() -> list[tuple[str, datetime, int]]:
    f: list[tuple[str, datetime, int]] = []

    def add(path, date, size=48_000):
        f.append((path, date, size))

    root = "D:/업무"
    # 주간보고 14개 (W30~W43)
    for i in range(14):
        week = 30 + i
        add(f"{root}/01_주간보고/주간업무보고_2026_W{week}.xlsx", _d(2026, 7, 27, 9) + timedelta(weeks=i), 61_000 + i * 900)
    # 월간 비용정산 5개 + 증빙 묶음 5개
    for mo in range(5, 10):
        add(f"{root}/02_정산/월간비용정산_2026_{mo:02d}.xlsx", _d(2026, mo + 1, 2, 17), 84_000)
        add(f"{root}/02_정산/증빙/증빙자료_2026_{mo:02d}.zip", _d(2026, mo + 1, 2, 18), 2_400_000)
    # 법인카드 취합 결과 5개
    for mo in range(6, 11):
        add(f"{root}/02_정산/법인카드/법인카드_취합_2026_{mo:02d}.xlsx", _d(2026, mo, 30 if mo != 10 else 29, 16), 52_000)
    # 사무용품 발주서 4개 + 재고현황 1개
    for mo in (7, 8, 9, 10):
        add(f"{root}/03_거래처/그린오피스/사무용품_발주서_2026_{mo:02d}.xlsx", _d(2026, mo, 10, 14), 31_000)
    add(f"{root}/03_거래처/그린오피스/사무용품_재고현황.xlsx", _d(2026, 10, 12, 13), 27_000)
    # 하늘물류 계약 5개
    add(f"{root}/03_거래처/하늘물류/2026_물류계약서_날인본.pdf", _d(2025, 12, 20, 10), 1_300_000)
    add(f"{root}/03_거래처/하늘물류/2027_계약갱신안_v1.pdf", _d(2026, 10, 8, 10), 820_000)
    add(f"{root}/03_거래처/하늘물류/2027_계약갱신안_v2.pdf", _d(2026, 10, 20, 11), 830_000)
    add(f"{root}/03_거래처/하늘물류/운임_비교검토.xlsx", _d(2026, 10, 21, 8), 45_000)
    add(f"{root}/03_거래처/하늘물류/내부기준_인상률.docx", _d(2026, 3, 4, 10), 22_000)
    # 사무실 이전 프로젝트 9개
    pj = f"{root}/04_프로젝트/사무실이전"
    add(f"{pj}/사무실이전_레이아웃_v1.pptx", _d(2026, 10, 5, 14), 3_200_000)
    add(f"{pj}/사무실이전_레이아웃_v2.pptx", _d(2026, 10, 7, 11), 3_300_000)
    add(f"{pj}/사무실이전_레이아웃_v3.pptx", _d(2026, 10, 22, 15), 3_350_000)
    add(f"{pj}/이사업체_견적비교.xlsx", _d(2026, 10, 27, 10), 38_000)
    add(f"{pj}/견적서_A이사.pdf", _d(2026, 10, 22, 15), 410_000)
    add(f"{pj}/견적서_B이사.pdf", _d(2026, 10, 22, 15), 395_000)
    add(f"{pj}/견적서_C이사.pdf", _d(2026, 10, 22, 15), 402_000)
    add(f"{pj}/이전일정표.xlsx", _d(2026, 10, 28, 9), 29_000)
    add(f"{pj}/좌석배치_희망조사.xlsx", _d(2026, 10, 9, 16), 33_000)
    # 세무 6개
    for q, mo in [(1, 4), (2, 7), (3, 10)]:
        add(f"{root}/05_세무/부가세신고자료_2026_Q{q}.xlsx", _d(2026, mo, 14, 17), 120_000)
        add(f"{root}/05_세무/세무법인_회신_2026_Q{q}.pdf", _d(2026, mo, 25, 10), 210_000)
    # 양식 5개
    for name in ["법인카드_사용내역_양식.xlsx", "주간업무보고_양식.xlsx", "출장비_정산서_양식.xlsx",
                 "품의서_양식.docx", "회의록_양식.docx"]:
        add(f"{root}/00_양식/{name}", _d(2026, 2, 3, 10), 25_000)
    # 장비 세팅 2개
    add(f"{root}/06_총무/신규입사자_장비체크리스트.xlsx", _d(2026, 8, 19, 9), 19_000)
    add(f"{root}/06_총무/자산대장_노트북.xlsx", _d(2026, 8, 28, 16), 66_000)
    # 지난 해 보관 자료 (분석에는 영향이 적어야 함)
    for name in ["2025_연간업무계획.pptx", "2025_예산안_최종.xlsx", "2025_조직도.pdf", "2025_워크숍_결과보고.docx",
                 "2025_연말정산_안내.pdf", "2025_사무용품_연간집계.xlsx"]:
        add(f"{root}/99_보관/2025/{name}", _d(2025, 12, 28, 10), 150_000)
    # 개인 폴더 (분석 제외 대상)
    for name in ["가족여행_일정.xlsx", "이력서_박지훈.docx", "사진/IMG_2041.jpg", "사진/IMG_2042.jpg"]:
        add(f"D:/개인/{name}", _d(2026, 10, 18, 21), 1_800_000)
    # 기타 바탕 파일
    add("D:/다운로드/정보보안교육_수료증.pdf", _d(2026, 10, 15, 10), 200_000)
    add("D:/다운로드/회식장소_후보.png", _d(2026, 10, 23, 18), 450_000)

    n = len(f)
    # 개수를 80개로 맞추기 위한 과거 주간보고 회의 메모
    for i in range(80 - n):
        add(f"{root}/01_주간보고/회의메모/팀회의메모_{i + 1:02d}.txt", _d(2026, 6, 1, 18) + timedelta(days=3 * i), 3_000)
    assert len(f) == 80, len(f)
    return f


def build_mbox() -> str:
    return build_mbox_from(_mails(), D)


def build_mbox_from(items: list[dict], domain: str) -> str:
    """add()로 만든 메일 목록을 .mbox 텍스트로 바꾼다. 다른 샘플(sample_cnc)도 이 함수를 쓴다."""
    fd, path = tempfile.mkstemp(suffix=".mbox")
    os.close(fd)
    box = mailbox.mbox(path)
    ids: list[str] = []
    for i, item in enumerate(items):
        msg = EmailMessage()
        msg["From"] = formataddr(item["frm"])
        msg["To"] = ", ".join(formataddr(x) for x in item["to"])
        if item["cc"]:
            msg["Cc"] = ", ".join(formataddr(x) for x in item["cc"])
        msg["Date"] = format_datetime(item["date"])
        msg["Subject"] = item["subject"]
        mid = f"<sample-{i:03d}@{domain}>"
        msg["Message-ID"] = mid
        if item["reply_to"] is not None:
            msg["In-Reply-To"] = ids[item["reply_to"]]
        ids.append(mid)
        msg.set_content(item["body"] + "\n\n" + item["frm"][0].split(" (")[0] + " 드림\n")
        for a in item["att"]:
            msg.add_attachment(b"sample attachment", maintype="application",
                               subtype="octet-stream", filename=a)
        box.add(msg)
    box.flush()
    box.close()
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        text = fh.read()
    os.remove(path)
    return text


def build_files_csv() -> str:
    return build_files_csv_from(_files())


def build_files_csv_from(files: list[tuple[str, datetime, int]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["FullName", "LastWriteTime", "Length"])
    for path, date, size in files:
        w.writerow([path.replace("/", "\\"), date.strftime("%Y-%m-%d %H:%M:%S"), size])
    return buf.getvalue()


SAMPLE_OWNER = {"owner_name": "박지훈", "owner_email": OWNER[1], "successor_name": "최유나",
                "title": "박지훈 대리 인수인계 (경영지원팀)"}


def sample_payload() -> dict:
    return {
        **SAMPLE_OWNER,
        "mails": [{"name": "sample_mails.mbox", "content": build_mbox()}],
        "files": [{"name": "sample_files.csv", "content": build_files_csv()}],
    }


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "..", "sample")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "sample_mails.mbox"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_mbox())
    with open(os.path.join(out, "sample_files.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(build_files_csv())
    print("sample/ 폴더에 sample_mails.mbox, sample_files.csv 를 만들었습니다.")
