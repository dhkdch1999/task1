"""SQLite 저장소.

저장하는 것: 인수인계(handover), 업무 카드, 연락처, 후임자 확인 상태, 댓글.
저장하지 않는 것: 업로드한 메일 원본, 메일 본문, 파일 목록 원본.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS handover (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    owner_name    TEXT NOT NULL,
    owner_email   TEXT,
    successor_name TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',   -- draft | confirmed
    share_token   TEXT UNIQUE,
    stats         TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    confirmed_at  TEXT
);
CREATE TABLE IF NOT EXISTS card (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    handover_id   INTEGER NOT NULL REFERENCES handover(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    cycle         TEXT NOT NULL DEFAULT '비정기',
    status        TEXT NOT NULL DEFAULT '정기',
    category      TEXT NOT NULL DEFAULT '기타',
    related_files TEXT NOT NULL DEFAULT '[]',
    related_people TEXT NOT NULL DEFAULT '[]',
    caution       TEXT NOT NULL DEFAULT '',
    evidence      TEXT NOT NULL DEFAULT '[]',
    evidence_total INTEGER NOT NULL DEFAULT 0,
    confidence    TEXT NOT NULL DEFAULT 'manual',  -- high | medium | low | manual
    needs_reply   INTEGER NOT NULL DEFAULT 0,
    successor_state TEXT NOT NULL DEFAULT 'none'   -- none | confirmed | question
);
CREATE TABLE IF NOT EXISTS contact (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    handover_id   INTEGER NOT NULL REFERENCES handover(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    org           TEXT,
    internal      INTEGER NOT NULL DEFAULT 0,
    count         INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS comment (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id       INTEGER NOT NULL REFERENCES card(id) ON DELETE CASCADE,
    author        TEXT NOT NULL,                   -- predecessor | successor
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_card_handover ON card(handover_id);
CREATE INDEX IF NOT EXISTS idx_comment_card ON comment(card_id);
"""

JSON_COLS = {"related_files", "related_people", "evidence", "stats"}

_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for k in JSON_COLS & d.keys():
            d[k] = json.loads(d[k])
        for k in ("needs_reply", "internal"):
            if k in d:
                d[k] = bool(d[k])
        return d

    # ------------------------------------------------------------ handover

    def create_handover(self, title: str, owner_name: str, owner_email: str | None,
                        successor_name: str | None, stats: dict, cards: list[dict],
                        contacts: list[dict]) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO handover(title, owner_name, owner_email, successor_name, stats, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (title, owner_name, owner_email, successor_name, json.dumps(stats, ensure_ascii=False), now_iso()),
            )
            hid = cur.lastrowid
            for i, card in enumerate(cards):
                self._insert_card(c, hid, i, card)
            for p in contacts:
                c.execute(
                    "INSERT INTO contact(handover_id, name, email, org, internal, count) VALUES (?,?,?,?,?,?)",
                    (hid, p["name"], p["email"], p.get("org"), int(p.get("internal", False)), p.get("count", 0)),
                )
            return int(hid)

    def _insert_card(self, c: sqlite3.Connection, hid: int, position: int, card: dict) -> int:
        cur = c.execute(
            "INSERT INTO card(handover_id, position, title, description, cycle, status, category,"
            " related_files, related_people, caution, evidence, evidence_total, confidence, needs_reply)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                hid, position, card["title"], card.get("description", ""), card.get("cycle", "비정기"),
                card.get("status", "정기"), card.get("category", "기타"),
                json.dumps(card.get("related_files", []), ensure_ascii=False),
                json.dumps(card.get("related_people", []), ensure_ascii=False),
                card.get("caution", ""),
                json.dumps(card.get("evidence", []), ensure_ascii=False),
                card.get("evidence_total", 0), card.get("confidence", "manual"),
                int(card.get("needs_reply", False)),
            ),
        )
        return int(cur.lastrowid)

    def list_handovers(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT h.*, (SELECT COUNT(*) FROM card WHERE handover_id = h.id) AS card_count"
            " FROM handover h ORDER BY h.id DESC"
        ).fetchall()
        return [self._row(r) for r in rows]  # type: ignore[misc]

    def get_handover(self, hid: int) -> dict | None:
        return self._row(self._conn.execute("SELECT * FROM handover WHERE id = ?", (hid,)).fetchone())

    def get_handover_by_token(self, token: str) -> dict | None:
        return self._row(self._conn.execute(
            "SELECT * FROM handover WHERE share_token = ? AND status = 'confirmed'", (token,)).fetchone())

    def delete_handover(self, hid: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM handover WHERE id = ?", (hid,))

    def set_confirmed(self, hid: int, confirmed: bool) -> dict:
        with self.tx() as c:
            h = self.get_handover(hid)
            assert h is not None
            token = h["share_token"] or secrets.token_urlsafe(12)
            c.execute(
                "UPDATE handover SET status = ?, share_token = ?, confirmed_at = ? WHERE id = ?",
                ("confirmed" if confirmed else "draft", token, now_iso() if confirmed else None, hid),
            )
        return self.get_handover(hid)  # type: ignore[return-value]

    # ------------------------------------------------------------ cards

    def cards(self, hid: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM card WHERE handover_id = ? ORDER BY position, id", (hid,)).fetchall()
        cards = [self._row(r) for r in rows]
        if not cards:
            return []
        ids = [c["id"] for c in cards]  # type: ignore[index]
        q = ",".join("?" * len(ids))
        comments = self._conn.execute(
            f"SELECT * FROM comment WHERE card_id IN ({q}) ORDER BY id", ids).fetchall()
        by_card: dict[int, list[dict]] = {}
        for cm in comments:
            by_card.setdefault(cm["card_id"], []).append(dict(cm))
        for card in cards:
            card["comments"] = by_card.get(card["id"], [])  # type: ignore[index]
        return cards  # type: ignore[return-value]

    def get_card(self, hid: int, cid: int) -> dict | None:
        return self._row(self._conn.execute(
            "SELECT * FROM card WHERE id = ? AND handover_id = ?", (cid, hid)).fetchone())

    def add_card(self, hid: int, card: dict) -> int:
        with self.tx() as c:
            pos = c.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM card WHERE handover_id = ?",
                            (hid,)).fetchone()[0]
            return self._insert_card(c, hid, pos, card)

    def update_card(self, hid: int, cid: int, fields: dict) -> None:
        if not fields:
            return
        sets, vals = [], []
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            vals.append(json.dumps(v, ensure_ascii=False) if k in JSON_COLS else
                        int(v) if isinstance(v, bool) else v)
        with self.tx() as c:
            c.execute(f"UPDATE card SET {', '.join(sets)} WHERE id = ? AND handover_id = ?", (*vals, cid, hid))

    def delete_cards(self, hid: int, ids: list[int]) -> None:
        if not ids:
            return
        q = ",".join("?" * len(ids))
        with self.tx() as c:
            c.execute(f"DELETE FROM card WHERE handover_id = ? AND id IN ({q})", (hid, *ids))

    def reorder(self, hid: int, ids: list[int]) -> None:
        with self.tx() as c:
            for pos, cid in enumerate(ids):
                c.execute("UPDATE card SET position = ? WHERE id = ? AND handover_id = ?", (pos, cid, hid))

    # ------------------------------------------------------------ contacts & comments

    def contacts(self, hid: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM contact WHERE handover_id = ? ORDER BY count DESC, name", (hid,)).fetchall()
        return [self._row(r) for r in rows]  # type: ignore[misc]

    def add_comment(self, cid: int, author: str, body: str) -> dict:
        with self.tx() as c:
            cur = c.execute("INSERT INTO comment(card_id, author, body, created_at) VALUES (?,?,?,?)",
                            (cid, author, body, now_iso()))
            row = c.execute("SELECT * FROM comment WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
