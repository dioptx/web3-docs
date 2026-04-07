"""BDD tests for cross-chain proposal search."""

from __future__ import annotations

import pytest
from pytest_bdd import given, when, then, scenario, parsers

from db import ProposalDB, ProposalRecord


# --- Scenarios ---

@scenario("features/search.feature", "Search by exact proposal ID")
def test_exact_id():
    pass

@scenario("features/search.feature", "Search by keyword returns cross-chain results")
def test_cross_chain():
    pass

@scenario("features/search.feature", "Search by concept finds related proposals")
def test_concept_search():
    pass

@scenario("features/search.feature", "Search for taproot finds Bitcoin BIPs")
def test_taproot():
    pass

@scenario("features/search.feature", "Search returns empty for nonsense query")
def test_empty_results():
    pass

@scenario("features/search.feature", "Search handles special characters safely")
def test_special_chars():
    pass


# --- Given ---

@given("a database with the following proposals", target_fixture="search_db")
def given_populated_db(tmp_db):
    proposals = [
        ProposalRecord(
            id="eip-1559", chain="ethereum", type="eip", number=1559,
            title="Fee market change for ETH 1.0 chain", status="Final",
            category="Core", authors="Vitalik Buterin", created="2019-04-13",
            requires="2718, 2930",
            description="Base fee burning mechanism",
            body="## Abstract\n\nA transaction pricing mechanism with base fee.",
        ),
        ProposalRecord(
            id="eip-4844", chain="ethereum", type="eip", number=4844,
            title="Shard Blob Transactions", status="Final",
            category="Core", authors="Vitalik Buterin", created="2022-02-25",
            requires="", description="Proto-danksharding blob txs",
            body="## Abstract\n\nBlob-carrying transactions for data availability.",
        ),
        ProposalRecord(
            id="erc-20", chain="ethereum", type="erc", number=20,
            title="Token Standard", status="Final",
            category="ERC", authors="Fabian Vogelsteller", created="2015-11-19",
            requires="", description="Standard interface for tokens",
            body="## Simple Summary\n\nA standard interface for tokens.",
        ),
        ProposalRecord(
            id="erc-721", chain="ethereum", type="erc", number=721,
            title="Non-Fungible Token Standard", status="Final",
            category="ERC", authors="William Entriken", created="2018-01-24",
            requires="", description="NFT standard interface",
            body="## Abstract\n\nA standard interface for non-fungible tokens.",
        ),
        ProposalRecord(
            id="bip-141", chain="bitcoin", type="bip", number=141,
            title="Segregated Witness", status="Final",
            category="Core", authors="Eric Lombrozo", created="2015-12-21",
            requires="", description="SegWit consensus layer",
            body="## Abstract\n\nSegregated witness at the consensus layer.",
            layer="Consensus (soft fork)",
        ),
        ProposalRecord(
            id="bip-340", chain="bitcoin", type="bip", number=340,
            title="Schnorr Signatures for secp256k1", status="Final",
            category="Core", authors="Pieter Wuille", created="2020-01-19",
            requires="", description="Schnorr signature scheme",
            body="## Abstract\n\nSchnorr signature scheme for Bitcoin.",
        ),
        ProposalRecord(
            id="bip-341", chain="bitcoin", type="bip", number=341,
            title="Taproot SegWit version 1", status="Final",
            category="Core", authors="Pieter Wuille", created="2020-01-19",
            requires="340", description="Taproot spending rules",
            body="## Abstract\n\nTaproot spending rules for SegWit v1.",
        ),
        ProposalRecord(
            id="simd-0096", chain="solana", type="simd", number=96,
            title="Reward full priority fee", status="Final",
            category="Core", authors="Tao Zhu", created="2024-01-15",
            requires="", description="Priority fee goes to validator",
            body="## Summary\n\nReward the full priority fee to the validator.",
            feature="3opE3EzAKnUftUDURkzMgwpNgimBAypW1mNDYH4x4Zg7",
        ),
    ]
    for p in proposals:
        tmp_db.upsert(p)
    tmp_db.commit()
    return tmp_db


# --- When ---

@when(parsers.parse('I search for "{query}"'), target_fixture="search_results")
def when_search(search_db, query):
    try:
        results = search_db.search(query)
        return {"results": results, "error": None}
    except Exception as e:
        return {"results": [], "error": str(e)}


# --- Then ---

@then(parsers.parse('the first result should be "{expected_id}"'))
def then_first_is(search_results, expected_id):
    results = search_results["results"]
    assert len(results) > 0, "Expected at least one result"
    assert results[0]["id"] == expected_id


@then(parsers.parse('there should be {count:d} result'))
def then_count_singular(search_results, count):
    assert len(search_results["results"]) == count


@then(parsers.parse('there should be {count:d} results'))
def then_count_plural(search_results, count):
    assert len(search_results["results"]) == count


@then(parsers.parse('results should include "{expected_id}"'))
def then_includes(search_results, expected_id):
    ids = [r["id"] for r in search_results["results"]]
    assert expected_id in ids, f"Expected {expected_id} in results, got {ids}"


@then(parsers.parse('results should be from chain "{expected_chain}"'))
def then_chain(search_results, expected_chain):
    for r in search_results["results"]:
        assert r["chain"] == expected_chain, f"Expected chain {expected_chain}, got {r['chain']} for {r['id']}"


@then("the search should not raise an error")
def then_no_error(search_results):
    assert search_results["error"] is None, f"Search raised: {search_results['error']}"
