"""SQLite + FTS5 database layer for Web3 protocol proposals."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ProposalRecord:
    id: str
    chain: str
    type: str
    number: int
    title: str
    status: str
    category: str
    authors: str
    created: str
    requires: str
    description: str
    body: str
    # Enriched fields
    discussions_to: str = ""
    superseded_by: str = ""
    replaces: str = ""
    extends: str = ""
    layer: str = ""            # BIP network layer (Consensus, Peer Services, etc.)
    feature: str = ""          # SIMD feature gate hash
    last_call_deadline: str = ""
    withdrawal_reason: str = ""
    # Phase 1b enrichment
    fork: str = ""             # Ethereum fork name (London, Cancun, Prague)
    fork_date: str = ""        # Mainnet activation date
    on_chain_refs: str = ""    # JSON: extracted hex addresses, opcodes from body
    impl_links: str = ""       # JSON: extracted GitHub URLs from body


SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    chain TEXT NOT NULL,
    type TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT '',
    category TEXT DEFAULT '',
    authors TEXT DEFAULT '',
    created TEXT DEFAULT '',
    requires TEXT DEFAULT '',
    description TEXT DEFAULT '',
    body TEXT NOT NULL,
    discussions_to TEXT DEFAULT '',
    superseded_by TEXT DEFAULT '',
    replaces TEXT DEFAULT '',
    extends TEXT DEFAULT '',
    layer TEXT DEFAULT '',
    feature TEXT DEFAULT '',
    last_call_deadline TEXT DEFAULT '',
    withdrawal_reason TEXT DEFAULT '',
    fork TEXT DEFAULT '',
    fork_date TEXT DEFAULT '',
    on_chain_refs TEXT DEFAULT '',
    impl_links TEXT DEFAULT '',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS forks (
    name TEXT PRIMARY KEY,
    activation_block INTEGER,
    activation_timestamp INTEGER,
    mainnet_date TEXT,
    eip_list TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS proposals_fts USING fts5(
    id,
    title,
    description,
    body,
    authors,
    content=proposals,
    content_rowid=rowid,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS proposals_ai AFTER INSERT ON proposals BEGIN
    INSERT INTO proposals_fts(rowid, id, title, description, body, authors)
    VALUES (new.rowid, new.id, new.title, new.description, new.body, new.authors);
END;

CREATE TRIGGER IF NOT EXISTS proposals_ad AFTER DELETE ON proposals BEGIN
    INSERT INTO proposals_fts(proposals_fts, rowid, id, title, description, body, authors)
    VALUES ('delete', old.rowid, old.id, old.title, old.description, old.body, old.authors);
END;

CREATE TRIGGER IF NOT EXISTS proposals_au AFTER UPDATE ON proposals BEGIN
    INSERT INTO proposals_fts(proposals_fts, rowid, id, title, description, body, authors)
    VALUES ('delete', old.rowid, old.id, old.title, old.description, old.body, old.authors);
    INSERT INTO proposals_fts(rowid, id, title, description, body, authors)
    VALUES (new.rowid, new.id, new.title, new.description, new.body, new.authors);
END;
"""


class ProposalDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert(self, record: ProposalRecord):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO proposals
               (id, chain, type, number, title, status, category, authors,
                created, requires, description, body,
                discussions_to, superseded_by, replaces, extends,
                layer, feature, last_call_deadline, withdrawal_reason,
                fork, fork_date, on_chain_refs, impl_links,
                updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                chain=excluded.chain, type=excluded.type, number=excluded.number,
                title=excluded.title, status=excluded.status, category=excluded.category,
                authors=excluded.authors, created=excluded.created, requires=excluded.requires,
                description=excluded.description, body=excluded.body,
                discussions_to=excluded.discussions_to, superseded_by=excluded.superseded_by,
                replaces=excluded.replaces, extends=excluded.extends, layer=excluded.layer,
                feature=excluded.feature, last_call_deadline=excluded.last_call_deadline,
                withdrawal_reason=excluded.withdrawal_reason,
                on_chain_refs=excluded.on_chain_refs, impl_links=excluded.impl_links,
                fork=CASE WHEN excluded.fork != '' THEN excluded.fork ELSE proposals.fork END,
                fork_date=CASE WHEN excluded.fork_date != '' THEN excluded.fork_date ELSE proposals.fork_date END,
                updated_at=excluded.updated_at""",
            (
                record.id,
                record.chain,
                record.type,
                record.number,
                record.title,
                record.status or "",
                record.category or "",
                record.authors or "",
                record.created or "",
                record.requires or "",
                record.description or "",
                record.body[:50000],
                record.discussions_to or "",
                record.superseded_by or "",
                record.replaces or "",
                record.extends or "",
                record.layer or "",
                record.feature or "",
                record.last_call_deadline or "",
                record.withdrawal_reason or "",
                record.fork or "",
                record.fork_date or "",
                record.on_chain_refs or "",
                record.impl_links or "",
                now,
            ),
        )

    def commit(self):
        self.conn.commit()

    # Combined upgrade aliases (consensus + execution layer names)
    _FORK_ALIASES = {
        "pectra": "prague",
        "dencun": "cancun",
        "shapella": "shanghai",
        "the merge": "paris",
    }

    def search(self, query: str, limit: int = 10) -> list[dict]:
        # Check for exact ID match first (eip-1559, bip-341, etc.)
        exact = self.conn.execute(
            "SELECT * FROM proposals WHERE id = ?", (query.lower().strip(),)
        ).fetchone()
        if exact:
            return [self._row_to_meta(exact)]

        # Expand fork aliases (e.g. "pectra" → "prague", "dencun" → "cancun")
        query_lower = query.lower().strip()
        for alias, canonical in self._FORK_ALIASES.items():
            if alias in query_lower:
                query = query_lower.replace(alias, canonical)
                break

        # FTS5 search with bm25 ranking
        # Column order: id(0), title(1), description(2), body(3), authors(4)
        # Weights: id=0, title=10, description=5, body=1, authors=2
        safe_query = self._sanitize_fts_query(query)
        if not safe_query:
            return []

        rows = self.conn.execute(
            """SELECT p.*, bm25(proposals_fts, 0, 10.0, 5.0, 1.0, 2.0) as rank
               FROM proposals_fts
               JOIN proposals p ON proposals_fts.rowid = p.rowid
               WHERE proposals_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (safe_query, limit),
        ).fetchall()

        return [self._row_to_meta(row) for row in rows]

    def get(self, proposal_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id.lower().strip(),)
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT type, COUNT(*) as count FROM proposals GROUP BY type ORDER BY type"
        ).fetchall()
        result = {row["type"]: row["count"] for row in rows}
        result["total"] = sum(result.values())
        return result

    def _row_to_meta(self, row: sqlite3.Row) -> dict:
        result = {
            "id": row["id"],
            "title": row["title"],
            "chain": row["chain"],
            "type": row["type"],
            "number": row["number"],
            "status": row["status"],
            "category": row["category"],
            "authors": row["authors"],
            "description": row["description"][:200] if row["description"] else "",
        }
        # Include enriched fields only when present (keep results compact)
        for field in ("discussions_to", "layer", "feature", "superseded_by",
                       "replaces", "extends", "last_call_deadline",
                       "fork", "fork_date"):
            val = row[field]
            if val:
                result[field] = val
        return result

    def _sanitize_fts_query(self, query: str) -> str:
        # Strip null bytes, remove FTS5 special chars, quote tokens for literal matching
        query = query.replace("\x00", "")
        special = set('*"(){}[]^~:+-')
        fts_keywords = {"AND", "OR", "NOT", "NEAR"}
        cleaned = "".join(c if c not in special else " " for c in query)
        tokens = []
        for t in cleaned.split():
            if t.upper() in fts_keywords:
                continue  # strip FTS5 operators
            tokens.append(f'"{t}"')  # quote each token for literal matching
        if not tokens:
            return ""
        return " ".join(tokens)

    def upsert_fork(self, name: str, activation_block: int | None,
                    activation_timestamp: int | None, mainnet_date: str,
                    eip_list: list[int]):
        self.conn.execute(
            """INSERT OR REPLACE INTO forks
               (name, activation_block, activation_timestamp, mainnet_date, eip_list)
               VALUES (?, ?, ?, ?, ?)""",
            (name, activation_block, activation_timestamp, mainnet_date,
             json.dumps(eip_list)),
        )

    def set_fork_for_eip(self, eip_number: int, fork_name: str, fork_date: str):
        """Set fork info on matching EIP/ERC proposals."""
        for prefix in ("eip", "erc"):
            self.conn.execute(
                "UPDATE proposals SET fork = ?, fork_date = ? WHERE id = ?",
                (fork_name, fork_date, f"{prefix}-{eip_number}"),
            )

    def get_fork(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM forks WHERE name = ?", (name.lower(),)
        ).fetchone()
        return dict(row) if row else None

    def close(self):
        self.conn.close()
