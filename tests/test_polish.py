"""Tests for v0.2.0 tool-polish additions: empty-DB UX, chain filter, fork lookup."""

from __future__ import annotations


def test_empty_db_is_empty(tmp_db):
    assert tmp_db.is_empty() is True


def test_populated_db_is_not_empty(populated_db):
    assert populated_db.is_empty() is False


def test_chain_filter_narrows_results(populated_db):
    # Without filter: should match across chains
    all_hits = populated_db.search("priority", limit=10)
    # With ethereum filter: simd-0096 (solana) shouldn't appear
    eth_only = populated_db.search("priority", limit=10, chain="ethereum")
    assert all(r["chain"] == "ethereum" for r in eth_only)
    # And the ethereum-only set is a subset of (or equal to) the full set
    assert len(eth_only) <= len(all_hits)


def test_chain_filter_exact_id_match(populated_db):
    # Exact ID lookup respects the chain filter — wrong chain should miss.
    miss = populated_db.search("eip-1559", chain="bitcoin")
    assert miss == []
    hit = populated_db.search("eip-1559", chain="ethereum")
    assert len(hit) == 1
    assert hit[0]["id"] == "eip-1559"


def test_list_fork_proposals_unknown(tmp_db):
    assert tmp_db.list_fork_proposals("nonexistent-fork") is None


def test_list_fork_proposals_alias_resolution(populated_db):
    """Aliases should resolve to canonical fork rows."""
    # Seed a fork that maps to eip-1559
    populated_db.upsert_fork(
        name="london",
        activation_block=12965000,
        activation_timestamp=None,
        mainnet_date="2021-08-05",
        eip_list=[1559, 3198, 3529, 3541, 3554],
    )
    populated_db.commit()

    info = populated_db.list_fork_proposals("London")
    assert info is not None
    assert info["name"] == "london"
    assert info["mainnet_date"] == "2021-08-05"
    # eip-1559 is in the seeded list and present in the DB
    assert any(p["id"] == "eip-1559" for p in info["proposals"])


def test_list_fork_proposals_consensus_alias(populated_db):
    """Consensus-layer alias 'pectra' should resolve to 'prague'."""
    populated_db.upsert_fork(
        name="prague",
        activation_block=None,
        activation_timestamp=None,
        mainnet_date="2025-05-07",
        eip_list=[],
    )
    populated_db.commit()

    by_canonical = populated_db.list_fork_proposals("prague")
    by_alias = populated_db.list_fork_proposals("pectra")
    assert by_canonical is not None
    assert by_alias is not None
    assert by_canonical["name"] == by_alias["name"] == "prague"


def test_list_fork_proposals_bitcoin_taproot(populated_db):
    """Bitcoin Taproot soft-fork should resolve and pull bip-141 if seeded."""
    populated_db.upsert_fork(
        name="taproot",
        activation_block=709632,
        activation_timestamp=None,
        mainnet_date="2021-11-14",
        eip_list=[141],
    )
    populated_db.commit()

    info = populated_db.list_fork_proposals("Taproot")
    assert info is not None
    assert any(p["id"] == "bip-141" for p in info["proposals"])
