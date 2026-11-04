"""업무 흔적 분석기 (규칙 기반).

메일과 파일 목록에서 업무 단위를 찾아 인수인계 카드 초안을 만든다.
모든 카드는 '왜 이렇게 판단했는지' 근거(evidence)를 함께 가진다.

분석 순서
1. 메일 분석: 주제별 묶음 → 반복 주기 / 진행 중 스레드 / 연락처
2. 폴더 분석: 파일명 날짜 패턴 → 반복 산출물, 최근 수정 → 진행 중, 버전 파일 → 핵심 문서
3. 교차 분석: 첨부파일 이름 ↔ 폴더 파일, 스레드 제목 ↔ 폴더 이름
4. 카드 조립, 분류, 신뢰도 계산

'기준일'은 오늘이 아니라 데이터 안에서 가장 늦은 날짜다.
(퇴사 직전에 내보낸 데이터를 나중에 분석해도 결과가 같도록)
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .parsers import KST, FileEntry, Mail
from .privacy import mask_pii

RECENT_DAYS = 14

# ---------------------------------------------------------------- 정규화

_PREFIX_RE = re.compile(r"^\s*(?:(?:re|fw|fwd|회신|답장|전달)\s*[:：]\s*|\[(?:re|fw|fwd)\]\s*)", re.I)
_TAG_RE = re.compile(r"\[[^\]]{1,10}\]|\([^)]{0,10}(?:주차|월|분기)[^)]{0,6}\)")
_DATE_TOKEN_RES = [
    re.compile(r"\d{4}\s*[년._\-/]\s*\d{1,2}\s*[월._\-/]?\s*(?:\d{1,2}\s*일?)?"),
    re.compile(r"\d{4}\s*[_\-]?\s*(?:w|wk)\s*\d{1,2}", re.I),
    re.compile(r"\d{4}\s*[_\-]?\s*q[1-4]", re.I),
    re.compile(r"\d{1,2}\s*월\s*(?:\d{1,2}\s*주차|\d{1,2}\s*일)?"),
    re.compile(r"\d{1,2}\s*주차"),
    re.compile(r"[1-4]\s*분기|q[1-4]\b", re.I),
    re.compile(r"\b\d{1,2}/\d{1,2}\b"),
    re.compile(r"\b(?:19|20)\d{2}(?:\d{4})?\b"),
]
_VERSION_RE = re.compile(r"(?:[_\-\s(]*)(?:v\d+(?:\.\d+)?|ver\s?\d+|최종(?:본)?|수정(?:본)?|final|draft|초안|\d차)\)?", re.I)


def strip_prefixes(subject: str) -> str:
    prev = None
    s = subject
    while prev != s:
        prev = s
        s = _PREFIX_RE.sub("", s)
    return s.strip()


def strip_dates(text: str) -> str:
    for r in _DATE_TOKEN_RES:
        text = r.sub(" ", text)
    return text


def clean_title(subject: str) -> str:
    s = strip_prefixes(subject)
    s = _TAG_RE.sub(" ", s)
    s = strip_dates(s)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .,:-")
    s = re.sub(r"\s*(?:건|송부|공유드립니다|보내드립니다)$", "", s).strip()
    return s or strip_prefixes(subject)


def topic_key(subject: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", clean_title(subject).lower())


def thread_key(subject: str) -> str:
    return re.sub(r"\s+", " ", strip_prefixes(subject)).strip().lower()


def file_base(name: str) -> str:
    """파일명에서 확장자, 날짜, 버전 표시를 떼고 비교용 키를 만든다."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = strip_dates(stem)
    stem = _VERSION_RE.sub(" ", stem)
    return re.sub(r"[^0-9a-z가-힣]", "", stem.lower())


def file_display_base(name: str) -> str:
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = _VERSION_RE.sub(" ", strip_dates(stem))
    return re.sub(r"[_\-\s]+", " ", stem).strip() or stem


def folder_label(folder: str) -> str:
    leaf = folder.rsplit("/", 1)[-1]
    return re.sub(r"^\d+[_.\-\s]*", "", leaf).strip() or leaf


_QUOTE_SPLIT_RE = re.compile(r"-{2,}\s*(?:original message|원본 메시지)|^\s*>|^\s*20\d\d.*(?:wrote|작성):", re.I | re.M)
_SIGN_RE = re.compile(r"^\s*\S{1,10}\s*(?:드림|올림|배상)\.?\s*$", re.M)


def snippet(body: str, limit: int = 90) -> str:
    """메일 본문에서 인용·서명을 떼고 앞부분만 짧게 남긴다 (개인정보는 가린다)."""
    text = _QUOTE_SPLIT_RE.split(body, maxsplit=1)[0]
    text = _SIGN_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    cut = text[:limit] + ("…" if len(text) > limit else "")
    return mask_pii(cut)


def _compact(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


# ---------------------------------------------------------------- 주기 판단


def cycle_from_intervals(dates: list[datetime]) -> str:
    days = sorted({d.date() for d in dates})
    if len(days) < 2:
        return "비정기"
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    if statistics.median(gaps) > 2:
        # 요청 메일과 2~3일 뒤 회신처럼 붙어 있는 날짜는 한 번의 발생으로 본다
        clustered = [days[0]]
        for d in days[1:]:
            if (d - clustered[-1]).days > 3:
                clustered.append(d)
        if len(clustered) < 2:
            return "비정기"
        gaps = [(b - a).days for a, b in zip(clustered, clustered[1:])]
    med = statistics.median(gaps)
    spread = (max(gaps) - min(gaps)) if gaps else 0
    if med <= 2:
        return "매일"
    if 5 <= med <= 9 and spread <= 10:
        return "매주"
    if 24 <= med <= 38 and spread <= 25:
        return "매월"
    if 75 <= med <= 105:
        return "분기"
    return "비정기"


def cycle_from_file_tokens(names: list[str]) -> str | None:
    joined = " ".join(names)
    if len(re.findall(r"(?:w|wk)\s*\d{1,2}|\d{1,2}\s*주차", joined, re.I)) >= 2:
        return "매주"
    if len(re.findall(r"q[1-4]|[1-4]\s*분기", joined, re.I)) >= 2:
        return "분기"
    if len(re.findall(r"\d{4}\s*[년._\-]\s*\d{1,2}(?!\d)|\d{1,2}\s*월", joined)) >= 2:
        return "매월"
    return None


CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("세무", ["세무", "부가세", "원천세", "세금", "신고"]),
    ("정산·회계", ["정산", "비용", "법인카드", "경비", "회계", "결산", "증빙"]),
    ("보고", ["보고", "주간", "월간", "실적", "회의록"]),
    ("구매·발주", ["발주", "구매", "견적", "사무용품", "주문서"]),
    ("계약·거래처", ["계약", "갱신", "거래처", "협력사", "물류"]),
    ("IT·장비", ["노트북", "장비", "계정", "pc", "세팅", "it"]),
    ("인사·총무", ["입사", "퇴사", "교육", "채용", "총무", "복리후생"]),
    ("프로젝트", ["프로젝트", "이전", "레이아웃", "구축", "도입"]),
]


def categorize(text: str) -> str:
    low = text.lower()
    best, score = "기타", 0
    for cat, words in CATEGORY_RULES:
        s = sum(1 for w in words if w in low)
        if s > score:
            best, score = cat, s
    return best


# ---------------------------------------------------------------- 결과 구조


@dataclass
class Evidence:
    kind: str  # mail | file
    label: str
    date: str | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "label": mask_pii(self.label, keep_emails=False), "date": self.date}


@dataclass
class DraftCard:
    title: str
    description: str
    cycle: str
    status: str  # 정기 | 진행 중 | 완료 | 참고
    category: str
    related_files: list[str] = field(default_factory=list)
    related_people: list[dict] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    evidence_total: int = 0
    confidence: str = "low"
    needs_reply: bool = False
    caution: str = ""
    sort_date: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "title": mask_pii(self.title),
            "description": mask_pii(self.description),
            "cycle": self.cycle,
            "status": self.status,
            "category": self.category,
            "related_files": self.related_files,
            "related_people": self.related_people,
            "evidence": [e.to_dict() for e in self.evidence[:8]],
            "evidence_total": self.evidence_total,
            "confidence": self.confidence,
            "needs_reply": self.needs_reply,
            "caution": self.caution,
        }


def _fmt(d: datetime | None) -> str | None:
    return d.astimezone(KST).strftime("%Y-%m-%d") if d else None


# ---------------------------------------------------------------- 메인 분석


@dataclass
class AnalysisResult:
    cards: list[dict]
    contacts: list[dict]
    stats: dict


def _detect_owner(mails: list[Mail], owner_email: str | None) -> str | None:
    if owner_email:
        return owner_email.strip().lower()
    counter: Counter[str] = Counter()
    for m in mails:
        counter[m.sender_email] += 1
        for _, a in m.to:
            counter[a] += 1
    return counter.most_common(1)[0][0] if counter else None


def _split_name(name: str) -> tuple[str, str | None]:
    """'김현우 (재무팀)' → ('김현우', '재무팀')"""
    m = re.match(r"^\s*(.+?)\s*[\(\[](.+?)[\)\]]\s*$", name)
    if m:
        return m.group(1), m.group(2)
    return name.strip(), None


def analyze(
    mails: list[Mail],
    files: list[FileEntry],
    owner_email: str | None = None,
) -> AnalysisResult:
    owner = _detect_owner(mails, owner_email)
    owner_domain = owner.split("@")[-1] if owner else None

    all_dates = [m.date for m in mails if m.date] + [f.modified for f in files if f.modified]
    base_date = max(all_dates) if all_dates else datetime.now(KST)
    recent_from = base_date - timedelta(days=RECENT_DAYS)

    # ---------- 연락처
    people: dict[str, dict] = {}

    def touch(name: str, addr: str) -> None:
        if not addr or addr == owner:
            return
        disp, org = _split_name(name)
        p = people.setdefault(
            addr,
            {"name": disp, "email": addr, "org": org, "count": 0,
             "internal": bool(owner_domain and addr.endswith("@" + owner_domain))},
        )
        p["count"] += 1
        if org and not p["org"]:
            p["org"] = org

    for m in mails:
        if m.sender_email == owner:
            for n, a in [*m.to, *m.cc]:
                touch(n, a)
        else:
            touch(m.sender_name, m.sender_email)
    for p in people.values():
        if not p["org"]:
            p["org"] = "사내" if p["internal"] else p["email"].split("@")[-1]

    def people_of(group: list[Mail], limit: int = 4) -> list[dict]:
        c: Counter[str] = Counter()
        for m in group:
            for _, a in m.participants():
                if a in people:
                    c[a] += 1
        return [
            {"name": people[a]["name"], "email": a, "org": people[a]["org"]}
            for a, _ in c.most_common(limit)
        ]

    # ---------- 메일 주제별 묶음
    topics: dict[str, list[Mail]] = defaultdict(list)
    for m in mails:
        k = topic_key(m.subject)
        if k:
            topics[k].append(m)

    # ---------- 파일 그룹
    file_groups: dict[tuple[str, str], list[FileEntry]] = defaultdict(list)
    for f in files:
        b = file_base(f.name)
        if b:
            file_groups[(f.folder, b)].append(f)
    files_by_base: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in file_groups:
        files_by_base[key[1]].append(key)

    used_file_groups: set[tuple[str, str]] = set()
    used_files: set[str] = set()
    cards: list[DraftCard] = []

    def match_files_for_attachments(group: list[Mail]) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for m in group:
            for a in m.attachments:
                ab = file_base(a)
                if not ab:
                    continue
                for key in files_by_base.get(ab, []):
                    if key not in found:
                        found.append(key)
        return found

    def match_folder_for_subject(subject: str) -> list[str]:
        sc = _compact(clean_title(subject))
        folders = {f.folder for f in files}
        hits = []
        for fo in folders:
            label = _compact(folder_label(fo))
            if len(label) >= 3 and label in sc:
                hits.append(fo)
        return hits

    # 1) 메일 기반 반복 업무
    recurring_topics: set[str] = set()
    for k, group in topics.items():
        dated = [m for m in group if m.date]
        # 반복 업무는 '새로 시작한 메일'(RE/FW가 아닌 메일)이 여러 번 있어야 한다.
        # 한 스레드 안에서 답장이 자주 오간 것은 반복 업무가 아니다.
        starts = [m for m in dated if strip_prefixes(m.subject) == m.subject.strip()]
        distinct_days = {m.date.date() for m in starts}
        matched = match_files_for_attachments(group)
        file_count = sum(len(file_groups[g]) for g in matched)
        if len(distinct_days) < 3 and not (len(distinct_days) >= 2 and file_count >= 3):
            continue
        cycle = cycle_from_intervals([m.date for m in starts])
        if cycle == "비정기" and matched:
            cycle = cycle_from_file_tokens([f.name for g in matched for f in file_groups[g]]) or cycle
        if cycle == "비정기":
            continue
        recurring_topics.add(k)
        latest = max(dated, key=lambda m: m.date)
        rec_needs_reply = latest.date >= recent_from and latest.sender_email != owner
        sent = [m for m in group if m.sender_email == owner]
        direction = "보내는" if len(sent) >= len(group) / 2 else "받는"
        counterpart = people_of(sent if direction == "보내는" else group, 3)
        who = ", ".join(p["name"] for p in counterpart) or "관련 담당자"
        related_files = sorted(
            {f.path for g in matched for f in file_groups[g]}, reverse=True
        )
        for g in matched:
            used_file_groups.add(g)
            used_files.update(f.path for f in file_groups[g])
        desc = f"{cycle} {who}에게 {'메일을 보내는' if direction == '보내는' else '메일을 받아 처리하는'} 업무로 보입니다."
        if related_files:
            desc += f" 관련 파일 {len(related_files)}개가 같은 이름 규칙으로 쌓여 있습니다."
        if rec_needs_reply:
            last_text = snippet(latest.body)
            who_last = _split_name(latest.sender_name)[0]
            desc += f" 최근 {who_last}님이 보낸 메일에 아직 답장하지 않았습니다."
            if last_text:
                desc += ' 마지막 내용: "' + last_text + '"'
        ev = [Evidence("mail", f"{strip_prefixes(m.subject)} — {_split_name(m.sender_name)[0]}", _fmt(m.date))
              for m in sorted(dated, key=lambda m: m.date, reverse=True)]
        ev += [Evidence("file", f"{p} (첨부파일과 같은 이름)", None) for p in related_files[:2]]
        score = 1 + (len(distinct_days) >= 3) + bool(related_files)
        cards.append(DraftCard(
            title=clean_title(latest.subject),
            description=desc,
            cycle=cycle,
            status="정기",
            category=categorize(" ".join(m.subject for m in group) + " " + latest.body[:200]),
            related_files=related_files[:6],
            related_people=counterpart,
            evidence=ev,
            evidence_total=len(group) + len(related_files),
            confidence=["low", "low", "medium", "high"][score],
            needs_reply=rec_needs_reply,
            sort_date=latest.date,
        ))

    # 2) 메일 스레드 기반 진행 중 / 완료 업무
    threads: dict[str, list[Mail]] = defaultdict(list)
    for m in mails:
        if topic_key(m.subject) in recurring_topics:
            continue
        threads[thread_key(m.subject)].append(m)
    for tk, group in threads.items():
        dated = sorted([m for m in group if m.date], key=lambda m: m.date)
        if len(group) < 2 or not dated:
            continue
        last = dated[-1]
        is_recent = last.date >= recent_from
        needs_reply = is_recent and last.sender_email != owner
        folders = match_folder_for_subject(last.subject)
        folder_files = sorted(
            [f for f in files if f.folder in folders],
            key=lambda f: f.modified or base_date - timedelta(days=9999),
            reverse=True,
        )
        matched = match_files_for_attachments(group)
        rel = []
        for f in folder_files:
            rel.append(f.path)
        for g in matched:
            rel.extend(f.path for f in file_groups[g])
        rel = list(dict.fromkeys(rel))
        used_files.update(rel)
        for fo in folders:
            for key in file_groups:
                if key[0] == fo:
                    used_file_groups.add(key)
        recent_files = [f for f in folder_files if f.modified and f.modified >= recent_from]
        status = "진행 중" if (is_recent or recent_files) else "완료"
        last_text = snippet(last.body)
        desc = (
            f"메일 {len(group)}건이 오간 업무입니다. 마지막 메일은 {_fmt(last.date)}에 "
            f"{_split_name(last.sender_name)[0]}님이 보냈습니다."
        )
        if needs_reply:
            desc += " 아직 답장하지 않은 것으로 보입니다."
        if last_text:
            desc += ' 마지막 내용: "' + last_text + '"'
        if recent_files:
            desc += f" 관련 폴더에서 최근 {RECENT_DAYS}일 안에 수정된 파일이 {len(recent_files)}개 있습니다."
        ev = [Evidence("mail", f"{strip_prefixes(m.subject)} — {_split_name(m.sender_name)[0]}", _fmt(m.date))
              for m in reversed(dated)]
        ev += [Evidence("file", f"{f.path} (최근 수정)", _fmt(f.modified)) for f in recent_files[:3]]
        score = 1 + (len(group) >= 3) + bool(rel)
        cards.append(DraftCard(
            title=clean_title(last.subject),
            description=desc,
            cycle="비정기",
            status=status,
            category=categorize(" ".join(m.subject for m in group) + " " + " ".join(folders)),
            related_files=rel[:6],
            related_people=people_of(group, 4),
            evidence=ev,
            evidence_total=len(group) + len(rel),
            confidence=["low", "low", "medium", "high"][score],
            needs_reply=needs_reply,
            sort_date=last.date,
        ))

    # 3) 파일만으로 보이는 반복 산출물
    templates: list[FileEntry] = []
    for key, group in file_groups.items():
        if key in used_file_groups:
            continue
        folder, _ = key
        if re.search(r"양식|템플릿|template|서식", folder, re.I):
            templates.extend(group)
            continue
        names = [f.name for f in group]
        cyc = cycle_from_file_tokens(names) if len(group) >= 3 else None
        if not cyc:
            continue
        used_file_groups.add(key)
        used_files.update(f.path for f in group)
        latest = max(group, key=lambda f: f.modified or base_date - timedelta(days=9999))
        disp = file_display_base(latest.name)
        # 같은 주기의 업무 카드가 같은(또는 상위) 폴더를 쓰고 있으면 그 카드의 부속 파일로 붙인다
        host = None
        head = _compact(disp)[:4]
        same_cycle = [c for c in cards if c.cycle == cyc and c.status == "정기"]
        for c in same_cycle:  # 1순위: 업무명이 겹치는 카드
            if len(head) >= 3 and head in _compact(c.title):
                host = c
                break
        if host is None:  # 2순위: 같은(또는 상위) 폴더를 쓰는 카드
            for c in same_cycle:
                card_folders = {p.rsplit("/", 1)[0] for p in c.related_files}
                if any(folder == cf or folder.startswith(cf + "/") for cf in card_folders):
                    host = c
                    break
        if host:
            newest = sorted((f.path for f in group), reverse=True)
            host.related_files.extend(newest[:2])
            host.evidence.append(Evidence(
                "file", f"'{disp}' 파일도 {cyc} 같은 폴더에 함께 쌓임 ({len(group)}개)", _fmt(latest.modified)))
            host.evidence_total += len(group)
            continue
        cards.append(DraftCard(
            title=disp,
            description=(
                f"'{folder_label(folder)}' 폴더에 {cyc} 단위로 '{disp}' 파일이 만들어지고 있습니다. "
                "메일로 보낸 흔적은 찾지 못했으니 누구에게 전달하는지 직접 적어 주세요."
            ),
            cycle=cyc,
            status="정기",
            category=categorize(disp + " " + folder),
            related_files=sorted((f.path for f in group), reverse=True)[:6],
            evidence=[Evidence("file", f.path, _fmt(f.modified))
                      for f in sorted(group, key=lambda f: f.name, reverse=True)],
            evidence_total=len(group),
            confidence="medium" if len(group) >= 4 else "low",
            sort_date=latest.modified,
        ))

    # 4) 메일과 연결되지 않은 최근 작업 폴더
    recent_by_folder: dict[str, list[FileEntry]] = defaultdict(list)
    for f in files:
        if f.path in used_files or f in templates:
            continue
        if f.modified and f.modified >= recent_from:
            recent_by_folder[f.folder].append(f)
    for folder, group in recent_by_folder.items():
        if len(group) < 2:
            continue
        used_files.update(f.path for f in group)
        label = folder_label(folder)
        cards.append(DraftCard(
            title=f"{label} 폴더 작업",
            description=(
                f"최근 {RECENT_DAYS}일 안에 '{label}' 폴더의 파일 {len(group)}개가 수정되었습니다. "
                "관련 메일은 찾지 못했습니다. 어떤 업무인지 설명을 보완해 주세요."
            ),
            cycle="비정기",
            status="진행 중",
            category=categorize(folder),
            related_files=[f.path for f in sorted(group, key=lambda f: f.modified, reverse=True)][:6],
            evidence=[Evidence("file", f"{f.path} (최근 수정)", _fmt(f.modified)) for f in group],
            evidence_total=len(group),
            confidence="low",
            sort_date=max(f.modified for f in group),
        ))

    # 5) 핵심 문서(여러 버전으로 고친 파일) → 해당 카드에 연결, 양식 파일 → 관련 카드나 별도 카드
    versioned: dict[str, list[FileEntry]] = defaultdict(list)
    for f in files:
        if _VERSION_RE.search(f.name.rsplit(".", 1)[0]):
            versioned[f.folder + "/" + file_base(f.name)].append(f)
    for vfiles in versioned.values():
        if len(vfiles) < 2:
            continue
        paths = {f.path for f in vfiles}
        for c in cards:
            if paths & set(c.related_files):
                latest = max(vfiles, key=lambda f: f.modified or base_date - timedelta(days=9999))
                c.evidence.append(Evidence(
                    "file", f"{file_display_base(latest.name)} — {len(vfiles)}개 버전으로 수정됨 (핵심 문서)",
                    _fmt(latest.modified)))
                if latest.path not in c.related_files[:1]:
                    c.related_files = [latest.path] + [p for p in c.related_files if p != latest.path]
                break

    leftover_templates = []
    for t in templates:
        tb = _compact(file_display_base(t.name))
        attached = False
        for c in cards:
            ct = _compact(c.title)
            if len(tb) >= 3 and (tb in ct or ct in tb or tb[:4] in ct):
                c.related_files.append(t.path)
                c.evidence.append(Evidence("file", f"{t.path} (양식 파일)", _fmt(t.modified)))
                attached = True
                break
        if not attached:
            leftover_templates.append(t)
    if leftover_templates:
        cards.append(DraftCard(
            title="자주 쓰는 양식 파일",
            description="양식·템플릿 폴더에 있는 파일입니다. 각 양식을 어떤 업무에 쓰는지 적어 두면 후임자가 헤매지 않습니다.",
            cycle="비정기",
            status="참고",
            category="기타",
            related_files=[t.path for t in leftover_templates],
            evidence=[Evidence("file", t.path, _fmt(t.modified)) for t in leftover_templates],
            evidence_total=len(leftover_templates),
            confidence="medium",
        ))

    # ---------- 정렬: 진행 중 → 정기 → 참고 → 완료, 같은 상태는 최근 순
    order = {"진행 중": 0, "정기": 1, "참고": 2, "완료": 3}
    far = datetime(1970, 1, 1, tzinfo=KST)
    cards.sort(key=lambda c: (order.get(c.status, 9), -(c.sort_date or far).timestamp()))

    contacts = sorted(people.values(), key=lambda p: -p["count"])
    stats = {
        "mails": len(mails),
        "files": len(files),
        "owner_email": owner,
        "base_date": _fmt(base_date),
        "cards": len(cards),
        "needs_reply": sum(1 for c in cards if c.needs_reply),
    }
    return AnalysisResult(cards=[c.to_dict() for c in cards], contacts=contacts, stats=stats)
