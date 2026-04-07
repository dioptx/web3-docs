"""Unit tests for ProposalDB — schema, upsert, search, enriched fields."""

from __future__ import annotations

import pytest

from db import ProposalDB, ProposalRecord


class TestSchema:
    def test_creates_tables(self, tmp_db):
        tables = tmp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "proposals" in names
        assert "proposals_fts" in names

    def test_empty_db_stats(self, tmp_db):
        stats = tmp_db.stats()
        assert stats == {"total": 0}

    def test_empty_search(self, tmp_db):
        assert tmp_db.search("anything") == []


class TestUpsert:
    def test_insert_and_retrieve(self, tmp_db, sample_eip):
        tmp_db.upsert(sample_eip)
        tmp_db.commit()

        result = tmp_db.get("eip-1559")
        assert result is not None
        assert result["title"] == "Fee market change for ETH 1.0 chain"
        assert result["chain"] == "ethereum"
        assert result["status"] == "Final"

    def test_upsert_updates_existing(self, tmp_db, sample_eip):
        tmp_db.upsert(sample_eip)
        tmp_db.commit()

        sample_eip.status = "Superseded"
        tmp_db.upsert(sample_eip)
        tmp_db.commit()

        result = tmp_db.get("eip-1559")
        assert result["status"] == "Superseded"

    def test_body_capped_at_50kb(self, tmp_db):
        record = ProposalRecord(
            id="eip-big", chain="ethereum", type="eip", number=99999,
            title="Big Proposal", status="Draft", category="Core",
            authors="Test", created="2024-01-01", requires="",
            description="", body="x" * 100000,
        )
        tmp_db.upsert(record)
        tmp_db.commit()

        result = tmp_db.get("eip-big")
        assert len(result["body"]) == 50000

    def test_stats_count_by_type(self, tmp_db, sample_eip, sample_bip, sample_simd):
        for r in [sample_eip, sample_bip, sample_simd]:
            tmp_db.upsert(r)
        tmp_db.commit()

        stats = tmp_db.stats()
        assert stats["eip"] == 1
        assert stats["bip"] == 1
        assert stats["simd"] == 1
        assert stats["total"] == 3


class TestEnrichedFields:
    def test_discussions_to_stored(self, tmp_db, sample_eip):
        tmp_db.upsert(sample_eip)
        tmp_db.commit()

        result = tmp_db.get("eip-1559")
        assert result["discussions_to"] == "https://ethereum-magicians.org/t/eip-1559"

    def test_layer_stored(self, tmp_db, sample_bip):
        tmp_db.upsert(sample_bip)
        tmp_db.commit()

        result = tmp_db.get("bip-141")
        assert result["layer"] == "Consensus (soft fork)"

    def test_feature_gate_stored(self, tmp_db, sample_simd):
        tmp_db.upsert(sample_simd)
        tmp_db.commit()

        result = tmp_db.get("simd-0096")
        assert result["feature"] == "3opE3EzAKnUftUDURkzMgwpNgimBAypW1mNDYH4x4Zg7"

    def test_enriched_fields_in_search_results(self, tmp_db, sample_bip):
        tmp_db.upsert(sample_bip)
        tmp_db.commit()

        results = tmp_db.search("segwit")
        assert len(results) > 0
        assert results[0]["layer"] == "Consensus (soft fork)"

    def test_enriched_fields_omitted_when_empty(self, tmp_db, sample_eip):
        tmp_db.upsert(sample_eip)
        tmp_db.commit()

        results = tmp_db.search("eip-1559")
        result = results[0]
        # layer should not be present since it's empty for EIPs
        assert "layer" not in result
        # discussions_to should be present since it's populated
        assert "discussions_to" in result


class TestSearch:
    def test_exact_id_match(self, populated_db):
        results = populated_db.search("eip-1559")
        assert len(results) == 1
        assert results[0]["id"] == "eip-1559"

    def test_keyword_search(self, populated_db):
        results = populated_db.search("fee")
        ids = [r["id"] for r in results]
        assert "eip-1559" in ids

    def test_cross_chain_search(self, populated_db):
        results = populated_db.search("fee")
        chains = {r["chain"] for r in results}
        # Both EIP-1559 and SIMD-0096 mention "fee"
        assert "ethereum" in chains
        assert "solana" in chains

    def test_title_weighted_higher_than_body(self, tmp_db):
        # Insert two proposals: one with "witness" in title, one only in body
        title_match = ProposalRecord(
            id="bip-title", chain="bitcoin", type="bip", number=1,
            title="Segregated Witness", status="Final", category="Core",
            authors="A", created="2020", requires="", description="",
            body="Technical details here.",
        )
        body_match = ProposalRecord(
            id="bip-body", chain="bitcoin", type="bip", number=2,
            title="Some Other Proposal", status="Final", category="Core",
            authors="B", created="2020", requires="", description="",
            body="This discusses witness data structures.",
        )
        tmp_db.upsert(title_match)
        tmp_db.upsert(body_match)
        tmp_db.commit()

        results = tmp_db.search("witness")
        assert len(results) == 2
        assert results[0]["id"] == "bip-title", "Title match should rank higher"

    def test_special_chars_sanitized(self, populated_db):
        # These should not raise FTS5 syntax errors
        for q in ['fee* OR (market)', '"exact phrase"', 'a:b', 'test~1', 'foo^2']:
            results = populated_db.search(q)
            # Just verify no exception — results may or may not be empty
            assert isinstance(results, list)

    def test_empty_query_returns_empty(self, populated_db):
        assert populated_db.search("") == []

    def test_get_nonexistent(self, populated_db):
        assert populated_db.get("eip-99999") is None

    def test_case_insensitive_id_lookup(self, populated_db):
        assert populated_db.get("EIP-1559") is not None
        assert populated_db.get("  eip-1559  ") is not None
