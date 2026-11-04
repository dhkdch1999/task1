"""개인정보 보호: 마스킹과 분석 제외 필터.

원칙
- 분석 결과(카드, 근거 문구)에 남는 텍스트는 저장 전에 mask_pii()를 거친다.
- 외부 AI API를 붙이게 되면, 전송 직전에 반드시 mask_pii()를 거쳐야 한다.
- 분석 제외 필터는 분석이 시작되기 전에 적용되어, 제외된 메일·파일은
  어떤 통계에도 쓰이지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parsers import FileEntry, Mail

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 주민등록번호 / 외국인등록번호
    (re.compile(r"\b\d{6}\s?-\s?[1-8]\d{6}\b"), "******-*******"),
    # 카드번호 (4-4-4-4)
    (re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"), "****-****-****-****"),
    # 휴대폰 번호
    (re.compile(r"\b01[016789][- .]?\d{3,4}[- .]?\d{4}\b"), "010-****-****"),
    # 일반 전화번호 (02-123-4567, 031-1234-5678)
    (re.compile(r"\b0\d{1,2}[- .]\d{3,4}[- .]\d{4}\b"), "0**-****-****"),
    # 이메일 주소
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "***@***"),
]


def mask_pii(text: str, keep_emails: bool = False) -> str:
    """전화번호·주민번호·카드번호·이메일 주소를 가린다."""
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        if keep_emails and repl == "***@***":
            continue
        out = pattern.sub(repl, out)
    return out


@dataclass
class Filters:
    exclude_senders: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    exclude_folders: list[str] = field(default_factory=list)


def _norm_path(p: str) -> str:
    return p.replace("\\", "/").rstrip("/").lower()


def apply_filters(
    mails: list[Mail], files: list[FileEntry], filters: Filters
) -> tuple[list[Mail], list[FileEntry], dict[str, int]]:
    senders = {s.strip().lower() for s in filters.exclude_senders if s.strip()}
    keywords = [k.strip().lower() for k in filters.exclude_keywords if k.strip()]
    folders = [_norm_path(f) for f in filters.exclude_folders if f.strip()]

    kept_mails: list[Mail] = []
    for m in mails:
        if m.sender_email.lower() in senders:
            continue
        text = f"{m.subject}\n{m.body}".lower()
        if any(k in text for k in keywords):
            continue
        kept_mails.append(m)

    kept_files: list[FileEntry] = []
    for f in files:
        p = _norm_path(f.path)
        if any(p == fo or p.startswith(fo + "/") for fo in folders):
            continue
        if any(k in f.path.lower() for k in keywords):
            continue
        kept_files.append(f)

    excluded = {
        "mails": len(mails) - len(kept_mails),
        "files": len(files) - len(kept_files),
    }
    return kept_mails, kept_files, excluded


FREE_MAIL_DOMAINS = {
    "gmail.com", "naver.com", "daum.net", "hanmail.net", "kakao.com",
    "nate.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com",
}
PERSONAL_KEYWORDS = [
    "택배", "배송", "광고", "할인", "쿠폰", "이벤트", "특가", "동창", "모임",
    "결혼", "청첩", "개인", "적립", "주문하신", "회원님",
]
PERSONAL_FOLDER_HINTS = ["개인", "personal", "private", "사진", "photo", "다운로드", "downloads"]


def looks_personal_mail(sender_email: str, subjects: list[str], owner_domain: str | None) -> bool:
    domain = sender_email.split("@")[-1].lower()
    if owner_domain and domain == owner_domain:
        return False
    if domain in FREE_MAIL_DOMAINS:
        return True
    joined = " ".join(subjects)
    return any(k in joined for k in PERSONAL_KEYWORDS)


def looks_personal_folder(folder: str) -> bool:
    low = folder.lower()
    return any(h in low for h in PERSONAL_FOLDER_HINTS)
