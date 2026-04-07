"""Tests for Phase 1b enrichment: on-chain refs, impl links, fork mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parser import (
    extract_on_chain_refs,
    extract_impl_links,
    enrich_record,
    parse_fork_file,
    ForkRecord,
)
from db import ProposalDB, ProposalRecord


# --- On-Chain Reference Extraction ---


class TestExtractOnChainRefs:
    def test_extracts_contract_address(self):
        body = "The EntryPoint contract is at 0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789."
        refs = extract_on_chain_refs(body)
        assert "0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789" in refs

    def test_extracts_precompile_address(self):
        body = "The BLAKE2F precompile is at address 0x0000000000000000000000000000000000000009."
        refs = extract_on_chain_refs(body)
        assert "0x0000000000000000000000000000000000000009" in refs

    def test_filters_short_noise_hex(self):
        body = "Values 0x00, 0xff, 0x01 are common constants."
        refs = extract_on_chain_refs(body)
        assert len(refs) == 0

    def test_extracts_opcode_pattern(self):
        body = "The new PUSH0 opcode 0x5f is introduced. Also OPCODE (0x49)."
        refs = extract_on_chain_refs(body)
        assert any("opcode:" in r for r in refs)

    def test_deduplicates(self):
        body = "Address 0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789 appears twice: 0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789."
        refs = extract_on_chain_refs(body)
        addr_refs = [r for r in refs if not r.startswith("opcode:")]
        assert len(addr_refs) == 1

    def test_empty_body(self):
        assert extract_on_chain_refs("") == []
        assert extract_on_chain_refs("No hex here at all.") == []


# --- Implementation Link Extraction ---


class TestExtractImplLinks:
    def test_extracts_github_urls(self):
        body = "See https://github.com/ethereum/go-ethereum/pull/12345 for the implementation."
        links = extract_impl_links(body)
        assert "https://github.com/ethereum/go-ethereum/pull/12345" in links

    def test_extracts_multiple_urls(self):
        body = """
        Reference: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1559.md
        Implementation: https://github.com/ethereum/go-ethereum/pull/22837
        """
        links = extract_impl_links(body)
        assert len(links) == 2

    def test_skips_image_urls(self):
        body = "Diagram: https://github.com/user/repo/blob/main/diagram.png"
        links = extract_impl_links(body)
        assert len(links) == 0

    def test_handles_markdown_link_syntax(self):
        body = "[reference](https://github.com/ethereum/go-ethereum/pull/123)"
        links = extract_impl_links(body)
        assert len(links) == 1

    def test_deduplicates(self):
        body = "https://github.com/ethereum/EIPs/pull/1 and again https://github.com/ethereum/EIPs/pull/1"
        links = extract_impl_links(body)
        assert len(links) == 1

    def test_empty_body(self):
        assert extract_impl_links("") == []
        assert extract_impl_links("No links here.") == []


# --- Enrich Record ---


class TestEnrichRecord:
    def test_populates_on_chain_refs(self):
        record = ProposalRecord(
            id="eip-test", chain="ethereum", type="eip", number=1,
            title="Test", status="Draft", category="Core", authors="A",
            created="2024", requires="", description="",
            body="Deploy at 0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789",
        )
        enrich_record(record)
        assert record.on_chain_refs
        refs = json.loads(record.on_chain_refs)
        assert len(refs) >= 1

    def test_populates_impl_links(self):
        record = ProposalRecord(
            id="eip-test", chain="ethereum", type="eip", number=1,
            title="Test", status="Draft", category="Core", authors="A",
            created="2024", requires="", description="",
            body="See https://github.com/ethereum/go-ethereum/pull/999",
        )
        enrich_record(record)
        assert record.impl_links
        links = json.loads(record.impl_links)
        assert len(links) == 1

    def test_leaves_empty_when_nothing_found(self):
        record = ProposalRecord(
            id="eip-test", chain="ethereum", type="eip", number=1,
            title="Test", status="Draft", category="Core", authors="A",
            created="2024", requires="", description="",
            body="Plain text with no addresses or links.",
        )
        enrich_record(record)
        assert record.on_chain_refs == ""
        assert record.impl_links == ""


# --- Fork Mapping Parser ---


class TestParseForkFile:
    def test_parse_london(self, tmp_file):
        f = tmp_file('''"""
The London fork overhauls the transaction fee market.

### Changes

- [EIP-1559: Fee market change for ETH 1.0 chain][EIP-1559]
- [EIP-3198: BASEFEE opcode][EIP-3198]
- [EIP-3529: Reduction in refunds][EIP-3529]

### Upgrade Schedule

| Network | Block        | Expected Date    | Fork Hash    |
| ------- | ------------ | ---------------- | ------------ |
| Mainnet | 12,965,000   |  August 5, 2021  | 0x0eb440f6   |

[EIP-1559]: https://eips.ethereum.org/EIPS/eip-1559
[EIP-3198]: https://eips.ethereum.org/EIPS/eip-3198
[EIP-3529]: https://eips.ethereum.org/EIPS/eip-3529
"""  # noqa: E501

from ethereum.fork_criteria import ByBlockNumber, ForkCriteria

FORK_CRITERIA: ForkCriteria = ByBlockNumber(12965000)
''', "london/__init__.py")
        result = parse_fork_file(f)

        assert result is not None
        assert result.name == "london"
        assert result.display_name == "London"
        assert 1559 in result.eip_numbers
        assert 3198 in result.eip_numbers
        assert 3529 in result.eip_numbers
        assert result.activation_block == 12965000
        assert result.activation_timestamp is None
        assert result.mainnet_date == "2021-08-05"

    def test_parse_timestamp_fork(self, tmp_file):
        f = tmp_file('''"""
The Cancun fork introduces blob transactions.

### Changes

- [EIP-4844: Shard Blob Transactions][EIP-4844]
- [EIP-1153: Transient storage opcodes][EIP-1153]

### Upgrade Schedule

| Network | Timestamp    | Date & Time (UTC)   | Fork Hash    |
| ------- | ------------ | ------------------- | ------------ |
| Mainnet | `1710338135` | 2024-03-13 13:55:35 | `0x9f3d2254` |

[EIP-4844]: https://eips.ethereum.org/EIPS/eip-4844
[EIP-1153]: https://eips.ethereum.org/EIPS/eip-1153
"""  # noqa: E501

from ethereum.fork_criteria import ByTimestamp, ForkCriteria

FORK_CRITERIA: ForkCriteria = ByTimestamp(1710338135)
''', "cancun/__init__.py")
        result = parse_fork_file(f)

        assert result is not None
        assert result.name == "cancun"
        assert 4844 in result.eip_numbers
        assert 1153 in result.eip_numbers
        assert result.activation_block is None
        assert result.activation_timestamp == 1710338135
        assert "2024-03-13" in result.mainnet_date

    def test_no_eips_returns_none(self, tmp_file):
        f = tmp_file('''"""
A fork with no EIP references.
"""

from ethereum.fork_criteria import ByBlockNumber, ForkCriteria

FORK_CRITERIA: ForkCriteria = ByBlockNumber(0)
''', "empty/__init__.py")
        assert parse_fork_file(f) is None

    def test_no_docstring_returns_none(self, tmp_file):
        f = tmp_file("# No docstring here\nx = 1\n", "bad/__init__.py")
        assert parse_fork_file(f) is None


# --- Fork Mapping Integration ---


class TestForkDBIntegration:
    def test_upsert_fork_and_set_eip(self, tmp_db):
        # Insert an EIP first
        tmp_db.upsert(ProposalRecord(
            id="eip-1559", chain="ethereum", type="eip", number=1559,
            title="Fee market", status="Final", category="Core",
            authors="V", created="2019", requires="", description="", body="text",
        ))
        tmp_db.commit()

        # Set fork mapping
        tmp_db.upsert_fork("london", 12965000, None, "August 5, 2021", [1559, 3198])
        tmp_db.set_fork_for_eip(1559, "London", "August 5, 2021")
        tmp_db.commit()

        # Verify
        result = tmp_db.get("eip-1559")
        assert result["fork"] == "London"
        assert result["fork_date"] == "August 5, 2021"

        fork = tmp_db.get_fork("london")
        assert fork is not None
        assert fork["activation_block"] == 12965000
        assert json.loads(fork["eip_list"]) == [1559, 3198]

    def test_fork_appears_in_search_results(self, tmp_db):
        tmp_db.upsert(ProposalRecord(
            id="eip-4844", chain="ethereum", type="eip", number=4844,
            title="Shard Blob Transactions", status="Final", category="Core",
            authors="V", created="2022", requires="", description="Blobs",
            body="Blob transactions for data availability",
            fork="Cancun", fork_date="2024-03-13",
        ))
        tmp_db.commit()

        results = tmp_db.search("blob transactions")
        assert len(results) > 0
        assert results[0]["fork"] == "Cancun"
        assert results[0]["fork_date"] == "2024-03-13"
