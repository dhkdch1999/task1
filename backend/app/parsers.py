"""메일(.eml / .mbox / CSV)과 파일 목록(CSV / 경로 목록) 파서.

업로드된 원본은 이 모듈에서 메모리 위의 Mail / FileEntry 객체로만 바뀌고,
어디에도 저장되지 않는다.
"""
from __future__ import annotations

import csv
import io
import mailbox
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

KST = timezone(timedelta(hours=9))


@dataclass
class Mail:
    id: str
    sender_name: str
    sender_email: str
    to: list[tuple[str, str]]
    cc: list[tuple[str, str]]
    date: datetime | None
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)

    def participants(self) -> list[tuple[str, str]]:
        return [(self.sender_name, self.sender_email), *self.to, *self.cc]


@dataclass
class FileEntry:
    path: str  # 슬래시(/)로 통일한 전체 경로
    modified: datetime | None
    size: int | None

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def folder(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""


@dataclass
class SourceFile:
    name: str
    content: str


# ---------------------------------------------------------------- 날짜

_DT_RE = re.compile(
    r"(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})\.?"
    r"(?:[ T]+(오전|오후|AM|PM)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?",
    re.IGNORECASE,
)


def parse_datetime(value: str | None) -> datetime | None:
    """ISO, RFC 2822, 'YYYY-MM-DD 오후 3:12:00', 'YYYY. M. D. 오후 3:12' 등을 읽는다."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=KST)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=KST)
    except (TypeError, ValueError, IndexError):
        pass
    m = _DT_RE.search(value)
    if not m:
        return None
    y, mo, d, ampm1, hh, mm, ss, ampm2 = m.groups()
    hour = int(hh) if hh else 0
    ampm = (ampm1 or ampm2 or "").upper()
    if ampm in ("오후", "PM") and hour < 12:
        hour += 12
    if ampm in ("오전", "AM") and hour == 12:
        hour = 0
    try:
        return datetime(int(y), int(mo), int(d), hour, int(mm or 0), int(ss or 0), tzinfo=KST)
    except ValueError:
        return None


# ---------------------------------------------------------------- 메일


def _addr_list(value: str | None) -> list[tuple[str, str]]:
    if not value:
        return []
    out = []
    for name, addr in getaddresses([value]):
        if addr:
            out.append((name.strip() or addr.split("@")[0], addr.strip().lower()))
    return out


def _body_text(msg: EmailMessage) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:  # noqa: BLE001 - 깨진 메일은 본문 없이 진행
        part = None
    if part is None:
        return ""
    try:
        text = part.get_content()
    except Exception:  # noqa: BLE001
        return ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _from_message(msg: EmailMessage, fallback_id: str) -> Mail | None:
    senders = _addr_list(str(msg.get("From", "")))
    if not senders:
        return None
    name, addr = senders[0]
    attachments = []
    for part in msg.iter_attachments():
        fn = part.get_filename()
        if fn:
            attachments.append(fn)
    return Mail(
        id=str(msg.get("Message-ID", "") or fallback_id).strip("<> "),
        sender_name=name,
        sender_email=addr,
        to=_addr_list(str(msg.get("To", ""))),
        cc=_addr_list(str(msg.get("Cc", ""))),
        date=parse_datetime(str(msg.get("Date", ""))),
        subject=str(msg.get("Subject", "") or "").strip(),
        body=_body_text(msg),
        attachments=attachments,
    )


def parse_eml(content: str, name: str = "mail.eml") -> list[Mail]:
    msg = BytesParser(policy=policy.default).parsebytes(content.encode("utf-8", "surrogateescape"))
    mail = _from_message(msg, name)  # type: ignore[arg-type]
    return [mail] if mail else []


def parse_mbox(content: str) -> list[Mail]:
    # mailbox 모듈은 파일 경로가 필요하므로 임시 파일을 쓰고 곧바로 지운다.
    fd, path = tempfile.mkstemp(suffix=".mbox")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        box = mailbox.mbox(path, factory=lambda f: BytesParser(policy=policy.default).parse(f))
        mails = []
        for i, msg in enumerate(box):
            mail = _from_message(msg, f"mbox-{i}")  # type: ignore[arg-type]
            if mail:
                mails.append(mail)
        box.close()
        return mails
    finally:
        os.remove(path)


_CSV_MAIL_FIELDS = {
    "subject": ["subject", "제목"],
    "from_addr": ["from: (address)", "보낸 사람: (주소)", "from address", "보낸사람주소", "sender email"],
    "from_name": ["from: (name)", "보낸 사람: (이름)", "from name", "보낸사람"],
    "from": ["from", "보낸 사람", "sender"],
    "to": ["to: (address)", "받는 사람: (주소)", "to", "받는 사람", "받는사람"],
    "cc": ["cc: (address)", "참조: (주소)", "cc", "참조"],
    "date": ["date", "날짜", "보낸 날짜", "받은 날짜", "sent", "received"],
    "body": ["body", "본문", "내용"],
    "attachments": ["attachments", "첨부", "첨부파일"],
}


def _match_headers(headers: list[str], spec: dict[str, list[str]]) -> dict[str, str]:
    low = {h.strip().lower(): h for h in headers}
    found: dict[str, str] = {}
    for key, cands in spec.items():
        for c in cands:
            if c in low and low[c] not in found.values():
                found[key] = low[c]
                break
    return found


def parse_mail_csv(content: str) -> list[Mail]:
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    cols = _match_headers(reader.fieldnames or [], _CSV_MAIL_FIELDS)
    mails = []
    for i, row in enumerate(reader):
        def g(key: str) -> str:
            col = cols.get(key)
            return (row.get(col) or "").strip() if col else ""

        sender_raw = g("from_addr") or g("from")
        senders = _addr_list(sender_raw.replace(";", ","))
        if not senders:
            continue
        s_name, s_addr = senders[0]
        if g("from_name"):
            s_name = g("from_name")
        mails.append(
            Mail(
                id=f"csv-{i}",
                sender_name=s_name,
                sender_email=s_addr,
                to=_addr_list(g("to").replace(";", ",")),
                cc=_addr_list(g("cc").replace(";", ",")),
                date=parse_datetime(g("date")),
                subject=g("subject"),
                body=g("body"),
                attachments=[a.strip() for a in re.split(r"[;|]", g("attachments")) if a.strip()],
            )
        )
    return mails


def parse_mail_source(src: SourceFile) -> list[Mail]:
    lower = src.name.lower()
    if lower.endswith(".csv"):
        return parse_mail_csv(src.content)
    if lower.endswith(".mbox") or src.content.startswith("From "):
        return parse_mbox(src.content)
    return parse_eml(src.content, src.name)


# ---------------------------------------------------------------- 파일 목록

_CSV_FILE_FIELDS = {
    "path": ["path", "fullname", "경로", "전체 경로", "파일 경로", "file"],
    "modified": ["modified", "lastwritetime", "수정일", "수정한 날짜", "수정 날짜", "date"],
    "size": ["size", "length", "크기"],
}


def normalize_path(p: str) -> str:
    return p.strip().strip('"').replace("\\", "/")


def parse_file_list(src: SourceFile) -> list[FileEntry]:
    text = src.content.lstrip("﻿")
    first = text.splitlines()[0] if text.strip() else ""
    entries: list[FileEntry] = []
    if "," in first and any(
        h in first.lower() for h in ("path", "fullname", "경로", "file")
    ):
        reader = csv.DictReader(io.StringIO(text))
        cols = _match_headers(reader.fieldnames or [], _CSV_FILE_FIELDS)
        for row in reader:
            path = normalize_path(row.get(cols.get("path", ""), "") or "")
            if not path:
                continue
            size_raw = (row.get(cols.get("size", ""), "") or "").replace(",", "").strip()
            entries.append(
                FileEntry(
                    path=path,
                    modified=parse_datetime(row.get(cols.get("modified", ""), "")),
                    size=int(size_raw) if size_raw.isdigit() else None,
                )
            )
    else:
        # 한 줄에 경로 하나씩 있는 단순 목록
        for line in text.splitlines():
            path = normalize_path(line)
            if path and "." in path.rsplit("/", 1)[-1]:
                entries.append(FileEntry(path=path, modified=None, size=None))
    return entries
