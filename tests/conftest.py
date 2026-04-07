"""Shared fixtures for web3-docs tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path so we can import db, parser, server
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import ProposalDB, ProposalRecord


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary ProposalDB backed by a temp file."""
    db = ProposalDB(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def tmp_file(tmp_path):
    """Factory for creating temporary proposal files."""
    def _make_file(content: str, name: str = "proposal.md") -> Path:
        filepath = tmp_path / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
        return filepath
    return _make_file


@pytest.fixture
def sample_eip():
    """A minimal EIP ProposalRecord for testing."""
    return ProposalRecord(
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
        description="Base fee burning mechanism",
        body="## Abstract\n\nA base fee mechanism.\n\n## Specification\n\nThe base fee is calculated.",
        discussions_to="https://ethereum-magicians.org/t/eip-1559",
    )


@pytest.fixture
def sample_bip():
    """A minimal BIP ProposalRecord for testing."""
    return ProposalRecord(
        id="bip-141",
        chain="bitcoin",
        type="bip",
        number=141,
        title="Segregated Witness",
        status="Final",
        category="Core",
        authors="Eric Lombrozo",
        created="2015-12-21",
        requires="",
        description="SegWit consensus layer",
        body="## Abstract\n\nThis BIP defines a new structure called a witness.",
        layer="Consensus (soft fork)",
    )


@pytest.fixture
def sample_simd():
    """A minimal SIMD ProposalRecord for testing."""
    return ProposalRecord(
        id="simd-0096",
        chain="solana",
        type="simd",
        number=96,
        title="Reward full priority fee",
        status="Final",
        category="Core",
        authors="Tao Zhu",
        created="2024-01-15",
        requires="",
        description="Priority fee goes to validator",
        body="## Summary\n\nReward the full priority fee to the validator.",
        feature="3opE3EzAKnUftUDURkzMgwpNgimBAypW1mNDYH4x4Zg7",
    )


@pytest.fixture
def populated_db(tmp_db, sample_eip, sample_bip, sample_simd):
    """A database pre-populated with sample proposals from all chains."""
    for record in [sample_eip, sample_bip, sample_simd]:
        tmp_db.upsert(record)
    tmp_db.commit()
    return tmp_db
