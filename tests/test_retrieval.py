"""BDD tests for proposal retrieval and section extraction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest_bdd import given, when, then, scenario, parsers

# Import server functions directly (not through MCP transport)
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import ProposalDB, ProposalRecord
from server import _extract_relevant_sections, _split_by_heading


# --- Scenarios ---

@scenario("features/retrieval.feature", "Retrieve full proposal without query")
def test_full_retrieval():
    pass

@scenario("features/retrieval.feature", "Retrieve targeted sections with a query")
def test_targeted_retrieval():
    pass

@scenario("features/retrieval.feature", "Retrieve returns abstract even with specific query")
def test_abstract_always_included():
    pass

@scenario("features/retrieval.feature", "Retrieve non-existent proposal")
def test_not_found():
    pass

@scenario("features/retrieval.feature", "Enriched metadata appears in header")
def test_enriched_header():
    pass


# --- Given ---

@given('a database with a proposal "eip-1559"', target_fixture="retrieval_db")
def given_retrieval_db(tmp_db):
    record = ProposalRecord(
        id="eip-1559",
        chain="ethereum",
        type="eip",
        number=1559,
        title="Fee market change for ETH 1.0 chain",
        status="Final",
        category="Core",
        authors="Vitalik Buterin",
        created="2019-04-13",
        requires="2718, 2930",
        description="A base fee mechanism.",
        body=(
            "## Abstract\n\nA base fee mechanism.\n\n"
            "## Specification\n\nThe base fee is calculated as follows.\n\n"
            "## Security Considerations\n\nMiner extractable value concerns.\n\n"
            "## Rationale\n\nWhy we chose this design."
        ),
        discussions_to="https://ethereum-magicians.org/t/eip-1559",
    )
    tmp_db.upsert(record)
    tmp_db.commit()
    return tmp_db


# --- When ---

@when(parsers.parse('I retrieve proposal "{proposal_id}" without a query'), target_fixture="retrieval_response")
def when_retrieve_no_query(retrieval_db, proposal_id):
    proposal = retrieval_db.get(proposal_id)
    if not proposal:
        return f"Proposal '{proposal_id}' not found. Use resolve_proposal to search."
    return _format_response(proposal, "")


@when(parsers.parse('I retrieve proposal "{proposal_id}" with query "{query}"'), target_fixture="retrieval_response")
def when_retrieve_with_query(retrieval_db, proposal_id, query):
    proposal = retrieval_db.get(proposal_id)
    if not proposal:
        return f"Proposal '{proposal_id}' not found. Use resolve_proposal to search."
    return _format_response(proposal, query)


# --- Then ---

@then(parsers.parse('the response should contain "{expected}"'))
def then_response_contains(retrieval_response, expected):
    assert expected in retrieval_response, (
        f"Expected '{expected}' in response.\n"
        f"Response preview: {retrieval_response[:500]}..."
    )


# --- Helpers ---

def _format_response(proposal: dict, query: str) -> str:
    """Replicate the query_protocol_docs compact formatting for testing."""
    meta = [f"{proposal['id']} — {proposal['title']}"]
    fields = [
        ("chain", None), ("type", None), ("status", None), ("category", None),
        ("fork", None), ("fork_date", "activated"), ("authors", None),
        ("created", None), ("requires", None), ("layer", None),
        ("feature", "feature_gate"), ("discussions_to", "discussion"),
        ("superseded_by", None), ("replaces", None), ("extends", None),
    ]
    for field, label in fields:
        val = proposal.get(field, "")
        if val:
            meta.append(f"{label or field}: {val}")

    header = "\n".join(meta) + "\n---\n"
    body = proposal["body"]

    if query:
        content = _extract_relevant_sections(body, query, budget=6000)
    else:
        content = body[:4000]

    return header + content


# --- Additional unit tests for section extraction ---

class TestSectionExtraction:
    def test_split_by_heading(self):
        body = "## A\n\nContent A.\n\n## B\n\nContent B.\n\n### C\n\nContent C."
        sections = _split_by_heading(body)
        assert len(sections) == 3
        assert "## A" in sections[0]
        assert "## B" in sections[1]
        assert "### C" in sections[2]

    def test_relevant_sections_scored_by_query(self):
        body = (
            "## Abstract\n\nGeneral overview.\n\n"
            "## Security\n\nSecurity analysis of the fee mechanism.\n\n"
            "## Rationale\n\nWhy this design was chosen."
        )
        result = _extract_relevant_sections(body, "security fee")
        assert "Security" in result
        # Abstract always boosted
        assert "Abstract" in result

    def test_empty_query_returns_full_body(self):
        body = "## A\n\nFull content here."
        result = _extract_relevant_sections(body, "", budget=8000)
        assert result == body[:8000]

    def test_budget_respected(self):
        body = "\n\n".join(f"## Section {i}\n\n{'x' * 2000}" for i in range(10))
        result = _extract_relevant_sections(body, "Section 5", budget=5000)
        assert len(result) <= 5500  # some slack for section headers

    def test_sections_returned_in_original_order(self):
        body = (
            "## First\n\nA.\n\n"
            "## Second\n\nB target word.\n\n"
            "## Third\n\nC.\n\n"
            "## Fourth\n\nD target word here too."
        )
        result = _extract_relevant_sections(body, "target word")
        second_pos = result.find("Second")
        fourth_pos = result.find("Fourth")
        if second_pos != -1 and fourth_pos != -1:
            assert second_pos < fourth_pos, "Sections should be in original document order"
