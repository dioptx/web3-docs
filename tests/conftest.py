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


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Factory for tmp git repos with files committed at known dates+authors.

    Returns a callable that takes a list of ``(relpath, content, iso_date,
    author_name, author_email)`` tuples, runs ``git init`` + per-tuple commits,
    and returns the repo Path. Used by parser tests that need git history.
    """
    import os
    import subprocess

    def _make_repo(commits: list[tuple[str, str, str, str, str]]) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, env=env, check=True)
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
            cwd=repo, env=env, check=True,
        )
        for relpath, content, iso_date, author_name, author_email in commits:
            f = repo / relpath
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
            subprocess.run(["git", "add", relpath], cwd=repo, env=env, check=True)
            commit_env = {
                **env,
                "GIT_AUTHOR_NAME": author_name,
                "GIT_AUTHOR_EMAIL": author_email,
                "GIT_AUTHOR_DATE": iso_date,
                "GIT_COMMITTER_NAME": author_name,
                "GIT_COMMITTER_EMAIL": author_email,
                "GIT_COMMITTER_DATE": iso_date,
            }
            subprocess.run(
                ["git", "commit", "-q", "-m", f"add {relpath}"],
                cwd=repo, env=commit_env, check=True,
            )
        return repo

    return _make_repo
