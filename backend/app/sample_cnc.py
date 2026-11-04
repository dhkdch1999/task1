"""데모용 샘플 데이터 2: 공작기계 제어 개발 엔지니어.

가상의 '한결정밀기계 제어개발팀 정우진 책임연구원'의 업무 메일 50건과 D드라이브 업무 폴더를 만든다.
CNC 컨트롤러 펌웨어 개발, 정기 릴리스, 필드 불량 대응, 고객사 채터링 이슈, EtherCAT 전환 프로젝트,
기능안전 인증 문서, 서보드라이브 협력사, 야간 빌드 알림이 섞여 있다.
모든 회사·사람·도메인은 가상이며 도메인은 .example 을 쓴다.

    python -m app.sample_cnc     # sample/cnc/ 에 mbox, 파일 목록 CSV, 업무 폴더 zip 을 만든다
"""
from __future__ import annotations

import os
import zipfile
from datetime import datetime, timedelta

from .parsers import KST
from .sample_data import build_files_csv_from, build_mbox_from

D = "hangyeol-mt.example"
OWNER = ("정우진 (제어개발팀)", f"woojin.jung@{D}")
LEADER = ("이준혁 (제어개발팀)", f"junhyuk.lee@{D}")
TEAM = [("김소연 (제어개발팀)", f"soyeon.kim@{D}"), ("박태현 (제어개발팀)", f"taehyun.park@{D}")]
QA = ("오하린 (품질보증팀)", f"harin.oh@{D}")
CS = ("박서준 (CS팀)", f"seojun.park@{D}")
CS2 = ("송민규 (CS팀)", f"mingyu.song@{D}")
HW = ("최민석 (HW개발팀)", f"minseok.choi@{D}")
BUY = ("강예린 (구매팀)", f"yerin.kang@{D}")
HR = ("문지아 (인사팀)", f"jia.moon@{D}")
ALL = ("전사공지", f"notice@{D}")
CI = ("Jenkins 빌드서버", f"jenkins@{D}")
CUST = ("한지훈 (대성오토텍)", "jihoon.han@daesung-autotech.example")
SERVO = ("임도경 (세진모션)", "dokyung.lim@sejin-motion.example")
CERT = ("윤가은 (세이프텍인증)", "gaeun.yoon@safetec-cert.example")
FRIEND = ("최성민", "sungmin.choi88@gmail.com")
SHOP = ("공구마켓", "ad@tool-market.example")
PARCEL = ("빠른택배", "noreply@quick-parcel.example")

SAMPLE_OWNER = {"owner_name": "정우진", "owner_email": OWNER[1], "successor_name": "김소연",
                "title": "정우진 책임 인수인계 (제어개발팀)"}


def _d(y: int, m: int, d: int, h: int = 10, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=KST)


def _week_of_month(day: datetime) -> int:
    return (day.day - 1) // 7 + 1


def _mails() -> list[dict]:
    m: list[dict] = []

    def add(frm, to, date, subject, body, cc=(), att=(), reply_to=None):
        m.append(dict(frm=frm, to=list(to), cc=list(cc), date=date, subject=subject,
                      body=body, att=list(att), reply_to=reply_to))
        return len(m) - 1

    # 1. 주간 개발 진척 보고 (매주 월요일, 팀장에게) — 8건 + 팀장 회신 2건
    for i in range(8):
        day = _d(2026, 9, 7, 9, 10) + timedelta(weeks=i)
        subj = f"[주간진척] 제어개발팀 CNC 펌웨어 주간 진척 보고 ({day.month}월 {_week_of_month(day)}주차)"
        idx = add(OWNER, [LEADER], day, subj,
                  "팀장님, 이번 주 펌웨어 개발 진척과 이슈를 정리해 보냅니다. 버그 트래커 미해결 건수와 다음 주 일정도 포함했습니다.",
                  cc=TEAM, att=[f"제어개발팀_주간진척_2026_W{36 + i}.xlsx"])
        if i in (2, 6):
            add(LEADER, [OWNER], day + timedelta(hours=4), "RE: " + subj,
                "확인했습니다. 대성오토텍 건은 다음 주 회의 첫 안건으로 올려 주세요." if i == 6 else
                "확인했습니다. 릴리스 일정 지연 사유는 품질팀과 먼저 공유해 주세요.", reply_to=idx)

    # 2. 월간 펌웨어 정기 릴리스 (매월 둘째 주 화요일, 품질·CS팀) — 5건 + 품질팀 회신 1건
    for mo, day, ver in [(6, 9, "3.4.0"), (7, 14, "3.5.0"), (8, 11, "3.6.0"), (9, 8, "3.7.0"), (10, 13, "3.8.0")]:
        idx = add(OWNER, [QA, CS], _d(2026, mo, day, 14), f"[릴리스] {mo}월 CNC 컨트롤러 펌웨어 정기 배포 안내",
                  f"이번 달 정기 배포 버전은 v{ver}입니다. 변경 내역과 알려진 문제는 첨부한 릴리스 노트를 참고해 주세요. "
                  "현장 업데이트는 서비스 툴 2.3 이상에서만 가능합니다.",
                  cc=[LEADER], att=[f"릴리스노트_CNC-FW_2026_{mo:02d}.pdf"])
        if mo == 9:
            add(QA, [OWNER], _d(2026, 9, 10, 11), f"RE: [릴리스] {mo}월 CNC 컨트롤러 펌웨어 정기 배포 안내",
                "v3.7.0 회귀 시험 완료했습니다. 원점 복귀 시험 1건은 지그 문제로 재시험 예정입니다.", reply_to=idx)

    # 3. 월간 필드 불량 이슈 리스트 (매월 초, CS팀이 보냄) — 5건 + 회신 1건
    for mo, day in [(6, 3), (7, 2), (8, 4), (9, 2), (10, 6)]:
        idx = add(CS, [OWNER], _d(2026, mo, day, 9, 40), f"{mo}월 필드 불량 이슈 리스트 공유",
                  "지난달 현장에서 접수된 컨트롤러 알람·불량 이슈 목록입니다. 펌웨어 원인으로 보이는 건은 빨간색으로 표시했습니다.",
                  cc=[CS2], att=[f"필드이슈_2026_{mo:02d}.xlsx"])
        if mo == 10:
            add(OWNER, [CS], _d(2026, 10, 7, 16), f"RE: {mo}월 필드 불량 이슈 리스트 공유",
                "알람 1043(주축 오리엔테이션 타임아웃)은 v3.8.1에서 수정 예정입니다. 나머지 2건은 파라미터 설정 문제로 보입니다.",
                reply_to=idx)

    # 4. 야간 빌드 실패 알림 (자동 메일, 매일) — 6건
    for day in [22, 23, 26, 27, 28, 29]:
        add(CI, [OWNER, TEAM[1]], _d(2026, 10, day, 6, 5), f"[Jenkins] cnc-fw-main 야간 빌드 실패 (10/{day})",
            "단위 시험 3건 실패: test_servo_loop_gain, test_ethercat_dc_sync, test_lookahead_buffer. 로그는 빌드서버에서 확인하세요.")

    # 5. 대성오토텍 5축 가공기 채터링 (진행 중, 고객이 마지막에 보냄) — 5건
    t = add(CUST, [OWNER], _d(2026, 10, 12, 10), "대성오토텍 HX-500 고속 가공 채터링 발생 건",
            "HX-500 5축 가공기에서 이송속도 F8000 이상일 때 가공면에 떨림 자국이 생깁니다. 가공면 사진 첨부합니다.",
            cc=[CS], att=["가공면_사진_1012.zip"])
    add(OWNER, [CUST], _d(2026, 10, 13, 15), "RE: 대성오토텍 HX-500 고속 가공 채터링 발생 건",
        "15일에 방문해서 서보 트레이스를 받겠습니다. 당일 장비 1시간 정도 사용할 수 있게 부탁드립니다.", cc=[CS, LEADER], reply_to=t)
    add(OWNER, [CUST], _d(2026, 10, 19, 17), "RE: 대성오토텍 HX-500 고속 가공 채터링 발생 건",
        "속도 루프 게인과 노치 필터를 조정한 1차 파라미터안을 보냅니다. 적용 후 같은 프로그램으로 가공해 봐 주세요.",
        att=["서보튜닝파라미터_v2.xlsx"], reply_to=t)
    add(CUST, [OWNER], _d(2026, 10, 23, 11), "RE: 대성오토텍 HX-500 고속 가공 채터링 발생 건",
        "저속 구간은 좋아졌는데 F10000 이상에서는 여전히 떨림이 있습니다. 새로 받은 트레이스 첨부합니다.",
        att=["servo_trace_1023.csv"], reply_to=t)
    add(CUST, [OWNER], _d(2026, 10, 29, 18), "RE: 대성오토텍 HX-500 고속 가공 채터링 발생 건",
        "11월 7일 양산 재개 전까지 해결이 꼭 필요합니다. 일정 회신 부탁드립니다. 생산기술팀 한지훈 010-4567-8910",
        reply_to=t)

    # 6. EtherCAT 전환 프로젝트 (진행 중, HW개발팀) — 4건
    t = add(OWNER, [HW], _d(2026, 10, 5, 13), "EtherCAT 전환 1차 동기화 지터 측정 결과",
            "분산 클럭 1ms 주기에서 최대 지터 38us가 나왔습니다. 목표 10us까지는 개선이 필요합니다.",
            cc=[LEADER], att=["지터측정결과_v1.xlsx"])
    add(HW, [OWNER], _d(2026, 10, 8, 10), "RE: EtherCAT 전환 1차 동기화 지터 측정 결과",
        "마스터 쪽 인터럽트 우선순위를 바꾼 보드로 다시 측정해 보죠. 시제품 보드 2장 더 드리겠습니다.", reply_to=t)
    add(OWNER, [HW], _d(2026, 10, 21, 16), "RE: EtherCAT 전환 1차 동기화 지터 측정 결과",
        "우선순위 변경 후 최대 지터 12us로 줄었습니다. 2차 결과 첨부합니다.", cc=[LEADER], att=["지터측정결과_v2.xlsx"], reply_to=t)
    add(HW, [OWNER], _d(2026, 10, 27, 14), "RE: EtherCAT 전환 1차 동기화 지터 측정 결과",
        "12월 시제품 일정에 맞추려면 11월 셋째 주까지 통신 사양을 확정해야 합니다. 사양서 초안 검토 부탁드립니다.",
        reply_to=t)

    # 7. 분기 기능안전 문서 개정 (세이프텍인증) — 2건
    for mo, q in [(7, 2), (10, 3)]:
        add(OWNER, [CERT], _d(2026, mo, 15, 10), f"{q}분기 기능안전 문서 개정본 송부",
            f"{q}분기 변경 사항을 반영한 안전 요구사항 명세와 FMEA 개정본을 보냅니다.", cc=[QA],
            att=[f"기능안전문서_2026_Q{q}.docx"])

    # 8. 세진모션 서보드라이브 호환성 (완료) — 3건
    t = add(SERVO, [OWNER], _d(2026, 8, 3, 11), "SJ-D200 서보드라이브 펌웨어 2.1 호환성 확인 요청",
            "드라이브 펌웨어 2.1이 9월 출하분부터 적용됩니다. 컨트롤러 쪽 호환성 확인 부탁드립니다.")
    add(OWNER, [SERVO], _d(2026, 8, 6, 15), "RE: SJ-D200 서보드라이브 펌웨어 2.1 호환성 확인 요청",
        "시험 장비에서 확인하겠습니다. 시험용 드라이브 1대 보내 주세요.", reply_to=t)
    add(SERVO, [OWNER], _d(2026, 8, 20, 10), "RE: SJ-D200 서보드라이브 펌웨어 2.1 호환성 확인 요청",
        "보내 주신 호환성 시험 결과 확인했습니다. 문제없이 출하하겠습니다.", reply_to=t)

    # 9. 개인 메일 — 3건 (분석 제외 대상)
    add(FRIEND, [OWNER], _d(2026, 10, 17, 21), "이번 주 토요일 등산 동호회 모임", "북한산 7시 집결이야. 늦지 마!")
    add(SHOP, [OWNER], _d(2026, 10, 20, 8), "[광고] 엔드밀·드릴 가을 특가 쿠폰", "회원님께만 드리는 최대 40% 할인 쿠폰입니다.")
    add(PARCEL, [OWNER], _d(2026, 10, 25, 13), "주문하신 상품이 배송 출발했습니다", "운송장번호 5521-0987-3345")

    # 10. 단발성 메일 (카드가 되면 안 됨)
    add(ALL, [OWNER], _d(2026, 10, 2, 9), "[전사공지] 연말 정보보안 점검 일정 안내", "11월 둘째 주에 부서별 PC 보안 점검을 합니다.")
    add(ALL, [OWNER], _d(2026, 10, 16, 9), "[전사공지] 사내 기술세미나 발표자 모집", "12월 기술세미나 발표 신청을 받습니다.")
    add(LEADER, TEAM + [OWNER], _d(2026, 10, 22, 17), "다음 주 팀 회식 날짜 투표", "목요일과 금요일 중 골라 주세요.")
    add(BUY, [OWNER], _d(2026, 10, 28, 11), "엔코더 케이블 단가 문의 답변",
        "문의하신 엔코더 케이블 10m 단가는 개당 8만 원이며 납기는 3주입니다.")
    add(HR, [OWNER], _d(2026, 9, 24, 15), "하반기 직무교육 수강 신청 안내", "PLC 고급 과정과 기능안전 기초 과정 중 하나를 골라 신청해 주세요.")

    assert len(m) == 50, len(m)
    return m


def _files() -> list[tuple[str, datetime, int]]:
    f: list[tuple[str, datetime, int]] = []

    def add(path, date, size=52_000):
        f.append((path, date, size))

    r = "D:/개발"
    # 주간 진척 14개 (W30~W43)
    for i in range(14):
        add(f"{r}/01_주간진척/제어개발팀_주간진척_2026_W{30 + i}.xlsx", _d(2026, 7, 27, 9) + timedelta(weeks=i), 58_000 + i * 700)
    # 릴리스 노트 5개 + 펌웨어 이미지 5개
    for mo in range(6, 11):
        day = {6: 9, 7: 14, 8: 11, 9: 8, 10: 13}[mo]
        add(f"{r}/02_릴리스/릴리스노트_CNC-FW_2026_{mo:02d}.pdf", _d(2026, mo, day, 13), 340_000)
        add(f"{r}/02_릴리스/펌웨어이미지/cnc_fw_2026_{mo:02d}.bin", _d(2026, mo, day, 12), 6_200_000)
    # 필드 이슈 5개
    for mo in range(6, 11):
        add(f"{r}/03_필드이슈/필드이슈_2026_{mo:02d}.xlsx", _d(2026, mo, 3 if mo != 10 else 7, 10), 96_000)
    # 대성오토텍 채터링 (최근 수정 다수, 버전 파일)
    cu = f"{r}/04_고객이슈/대성오토텍"
    add(f"{cu}/서보튜닝파라미터_v1.xlsx", _d(2026, 10, 16, 18), 24_000)
    add(f"{cu}/서보튜닝파라미터_v2.xlsx", _d(2026, 10, 19, 17), 24_500)
    add(f"{cu}/서보튜닝파라미터_v3.xlsx", _d(2026, 10, 28, 20), 25_100)
    add(f"{cu}/servo_trace_1015.csv", _d(2026, 10, 15, 14), 4_800_000)
    add(f"{cu}/servo_trace_1023.csv", _d(2026, 10, 23, 11), 5_100_000)
    add(f"{cu}/채터링_원인분석_초안.docx", _d(2026, 10, 27, 19), 410_000)
    add(f"{cu}/가공면_사진_1012.zip", _d(2026, 10, 12, 10), 18_000_000)
    # EtherCAT 전환 프로젝트
    pj = f"{r}/05_프로젝트/EtherCAT전환"
    add(f"{pj}/지터측정결과_v1.xlsx", _d(2026, 10, 5, 13), 88_000)
    add(f"{pj}/지터측정결과_v2.xlsx", _d(2026, 10, 21, 16), 91_000)
    add(f"{pj}/EtherCAT_통신사양서_초안.docx", _d(2026, 10, 28, 17), 620_000)
    add(f"{pj}/분산클럭_타이밍도.pptx", _d(2026, 10, 9, 15), 2_100_000)
    add(f"{pj}/PDO매핑표.xlsx", _d(2026, 10, 26, 11), 44_000)
    add(f"{pj}/일정표_시제품.xlsx", _d(2026, 9, 30, 9), 31_000)
    # 기능안전 문서 3개 + FMEA 3개
    for q, mo in [(1, 4), (2, 7), (3, 10)]:
        add(f"{r}/06_인증/기능안전문서_2026_Q{q}.docx", _d(2026, mo, 14, 18), 1_400_000)
        add(f"{r}/06_인증/FMEA_컨트롤러_2026_Q{q}.xlsx", _d(2026, mo, 14, 17), 230_000)
    # 협력사
    add(f"{r}/07_협력사/세진모션/SJ-D200_호환성시험성적서.pdf", _d(2026, 8, 19, 16), 520_000)
    add(f"{r}/07_협력사/세진모션/SJ-D200_통신매뉴얼.pdf", _d(2026, 3, 2, 10), 3_400_000)
    # 양식
    for name in ["시험성적서_양식.docx", "설계변경요청서_ECR_양식.xlsx", "릴리스노트_양식.docx",
                 "회의록_양식.docx", "출장보고서_양식.docx"]:
        add(f"{r}/00_양식/{name}", _d(2026, 1, 12, 10), 28_000)
    # 소스 문서·시험 G코드 (오래된 참고 자료)
    for name in ["서보제어_구조설명.pptx", "보간알고리즘_설계노트.docx", "파라미터_목록_전체.xlsx", "알람코드표.xlsx"]:
        add(f"{r}/08_설계문서/{name}", _d(2026, 2, 20, 10), 900_000)
    for i in range(1, 7):
        add(f"{r}/09_시험/G코드/test_circle_{i:02d}.nc", _d(2026, 5, 10 + i, 15), 6_000)
    # 지난해 보관
    for name in ["2025_연간개발계획.pptx", "2025_펌웨어_릴리스이력.xlsx", "2025_필드이슈_연간집계.xlsx", "2025_특허출원_명세서.docx"]:
        add(f"{r}/99_보관/2025/{name}", _d(2025, 12, 26, 10), 700_000)
    # 개인·다운로드 (분석 제외 대상)
    for name in ["등산_사진/IMG_3301.jpg", "등산_사진/IMG_3302.jpg", "연말정산_서류.pdf", "자동차보험_갱신.pdf"]:
        add(f"D:/개인/{name}", _d(2026, 10, 18, 22), 2_100_000)
    add("D:/다운로드/TwinCAT_설치파일.zip", _d(2026, 10, 3, 9), 850_000_000)
    add("D:/다운로드/정보보안교육_수료증.pdf", _d(2026, 10, 14, 10), 210_000)

    n = len(f)
    # 개수를 90개로 맞추는 오래된 회의 메모
    for i in range(90 - n):
        add(f"{r}/01_주간진척/회의메모/팀회의메모_{i + 1:02d}.txt", _d(2026, 5, 4, 18) + timedelta(days=4 * i), 3_500)
    assert len(f) == 90, len(f)
    return f


def build_mbox() -> str:
    return build_mbox_from(_mails(), D)


def build_files_csv() -> str:
    return build_files_csv_from(_files())


def build_folder_zip(path: str, root: str = "D드라이브_샘플") -> None:
    """업무 폴더를 실제 폴더 구조로 압축한다. 압축을 풀면 수정일까지 그대로 남는다."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p, date, _size in _files():
            rel = p.split(":/", 1)[1]
            info = zipfile.ZipInfo(f"{root}/{rel}", date_time=date.astimezone(KST).timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800  # 파일명 UTF-8 (윈도우에서 한글이 깨지지 않게)
            z.writestr(info, f"샘플 파일입니다 (내용 없음): {rel}\n")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "..", "sample", "cnc")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "제어개발_메일.mbox"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_mbox())
    with open(os.path.join(out, "제어개발_파일목록.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(build_files_csv())
    build_folder_zip(os.path.join(out, "제어개발_업무폴더.zip"))
    print("sample/cnc/ 에 메일, 파일 목록, 업무 폴더 zip 을 만들었습니다.")
