"""Unit tests for proposal parsers across all formats."""

from __future__ import annotations

import pytest

from parser import parse_eip, parse_bip, parse_simd


# --- EIP Parsing ---

class TestParseEIP:
    def test_standard_eip(self, tmp_file):
        f = tmp_file("""---
eip: 1559
title: Fee market change for ETH 1.0 chain
author: Vitalik Buterin (@vbuterin), Eric Conner (@econoar)
status: Final
type: Standards Track
category: Core
created: 2019-04-13
requires: 2718, 2930
discussions-to: https://ethereum-magicians.org/t/eip-1559
---

## Abstract

This EIP introduces a base fee per gas in blocks.
""", "EIPS/eip-1559.md")
        result = parse_eip(f)

        assert result is not None
        assert result.id == "eip-1559"
        assert result.chain == "ethereum"
        assert result.type == "eip"
        assert result.number == 1559
        assert result.title == "Fee market change for ETH 1.0 chain"
        assert result.status == "Final"
        assert result.category == "Core"
        assert "Vitalik Buterin" in result.authors
        assert "Eric Conner" in result.authors
        assert result.requires == "2718, 2930"
        assert result.discussions_to == "https://ethereum-magicians.org/t/eip-1559"
        assert "base fee" in result.description.lower()

    def test_erc_detected_by_path(self, tmp_file):
        f = tmp_file("""---
eip: 20
title: Token Standard
author: Fabian Vogelsteller <fabian@ethereum.org>
type: Standards Track
category: ERC
status: Final
created: 2015-11-19
---

## Simple Summary

A standard interface for tokens.
""", "ERCS/erc-20.md")
        result = parse_eip(f)

        assert result is not None
        assert result.id == "erc-20"
        assert result.type == "erc"
        assert result.chain == "ethereum"

    def test_requires_as_list(self, tmp_file):
        f = tmp_file("""---
eip: 4844
title: Shard Blob Transactions
author: Test Author
status: Final
category: Core
created: 2022-02-25
requires:
  - 1559
  - 2718
  - 4895
---

## Abstract

Proto-danksharding.
""", "EIPS/eip-4844.md")
        result = parse_eip(f)
        assert "1559" in result.requires
        assert "4895" in result.requires

    def test_last_call_deadline(self, tmp_file):
        f = tmp_file("""---
eip: 9999
title: Test Last Call
author: Test
status: Last Call
category: Core
created: 2024-01-01
last-call-deadline: 2024-02-15
---

## Abstract

Testing last call.
""", "EIPS/eip-9999.md")
        result = parse_eip(f)
        assert result.last_call_deadline == "2024-02-15"

    def test_no_frontmatter_returns_none(self, tmp_file):
        f = tmp_file("Just plain text, no frontmatter.", "EIPS/eip-bad.md")
        assert parse_eip(f) is None

    def test_missing_eip_number_returns_none(self, tmp_file):
        f = tmp_file("""---
title: No EIP number
author: Test
status: Draft
---

Body text.
""", "EIPS/eip-bad.md")
        assert parse_eip(f) is None


# --- BIP Parsing ---

class TestParseBIP:
    def test_mediawiki_format(self, tmp_file):
        f = tmp_file("""<pre>
  BIP: 141
  Layer: Consensus (soft fork)
  Title: Segregated Witness (Consensus layer)
  Authors: Eric Lombrozo <elombrozo@gmail.com>
           Johnson Lau <jl2012@xbt.hk>
  Status: Deployed
  Type: Standards Track
  Created: 2015-12-21
</pre>

==Abstract==

This BIP defines a new structure called a witness.
""", "bip-0141.mediawiki")
        result = parse_bip(f)

        assert result is not None
        assert result.id == "bip-141"
        assert result.chain == "bitcoin"
        assert result.type == "bip"
        assert result.number == 141
        assert result.layer == "Consensus (soft fork)"
        assert "Eric Lombrozo" in result.authors
        assert "Johnson Lau" in result.authors
        # Body should be converted from mediawiki to markdown
        assert "## Abstract" in result.body

    def test_markdown_format(self, tmp_file):
        f = tmp_file("""---
bip: 3
title: Updated BIP Process
author: Some Author
status: Draft
type: Process
created: 2024-01-01
---

## Abstract

An updated BIP process.
""", "bip-0003.md")
        result = parse_bip(f)

        assert result is not None
        assert result.id == "bip-3"
        assert result.status == "Draft"

    def test_mediawiki_to_markdown_conversion(self, tmp_file):
        f = tmp_file("""<pre>
  BIP: 99
  Title: Test Conversion
  Authors: Test Author
  Status: Draft
  Type: Standards Track
</pre>

==Motivation==

This is '''bold''' and ''italic'' text.

===Sub Section===

See [https://example.com this link] for details.
""", "bip-0099.mediawiki")
        result = parse_bip(f)

        assert "## Motivation" in result.body
        assert "**bold**" in result.body
        assert "*italic*" in result.body
        assert "### Sub Section" in result.body
        assert "[this link](https://example.com)" in result.body

    def test_no_bip_number_returns_none(self, tmp_file):
        f = tmp_file("""<pre>
  Title: No BIP Number
  Authors: Test
  Status: Draft
</pre>

Some content.
""", "bip-bad.mediawiki")
        assert parse_bip(f) is None


# --- SIMD Parsing ---

class TestParseSIMD:
    def test_standard_simd(self, tmp_file):
        f = tmp_file("""---
simd: '0096'
title: Reward full priority fee to validator
authors:
  - Tao Zhu (Anza)
category: Standard
type: Core
status: Accepted
created: 2024-01-15
feature: 3opE3EzAKnUftUDURkzMgwpNgimBAypW1mNDYH4x4Zg7
development:
  - Anza - implemented
  - Firedancer - implemented
---

## Summary

Reward the full priority fee to the validator.
""", "proposals/0096-test.md")
        result = parse_simd(f)

        assert result is not None
        assert result.id == "simd-0096"
        assert result.chain == "solana"
        assert result.type == "simd"
        assert result.number == 96
        assert result.feature == "3opE3EzAKnUftUDURkzMgwpNgimBAypW1mNDYH4x4Zg7"
        assert "Tao Zhu" in result.authors
        # Development status should be in body
        assert "Development" in result.body
        assert "Anza - implemented" in result.body

    def test_zero_padded_id(self, tmp_file):
        f = tmp_file("""---
simd: '0001'
title: Solana Proposal Process
authors:
  - Jacob Creech
category: Meta
type: Meta
status: Living
created: 2022-10-18
---

## Summary

Meta proposal.
""", "proposals/0001-process.md")
        result = parse_simd(f)

        assert result.id == "simd-0001"
        assert result.number == 1

    def test_no_simd_field_returns_none(self, tmp_file):
        f = tmp_file("""---
title: No SIMD number
authors:
  - Test
status: Draft
---

Body.
""", "proposals/bad.md")
        assert parse_simd(f) is None
