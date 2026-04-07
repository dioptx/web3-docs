"""Tests for additional chain parsers and contract registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parser import (
    parse_cosmos_adr,
    parse_polkadot_rfc,
    parse_stacks_sip,
    parse_avalanche_acp,
)
from server import resolve_contract


# --- Cosmos ADR ---

class TestCosmosADR:
    def test_parse_standard_adr(self, tmp_file):
        f = tmp_file("""# ADR 002: SDK Documentation Structure

## Status

ACCEPTED

## Context

There is a need for a scalable structure of the SDK docs.

## Decision

Re-structure the /docs folder.
""", "adr-002-sdk-documentation.md")
        result = parse_cosmos_adr(f)

        assert result is not None
        assert result.id == "adr-002"
        assert result.chain == "cosmos"
        assert result.type == "adr"
        assert result.number == 2
        assert result.title == "SDK Documentation Structure"
        assert result.status == "ACCEPTED"

    def test_no_number_returns_none(self, tmp_file):
        f = tmp_file("# ADR Template\n\nSome content.", "adr-template.md")
        assert parse_cosmos_adr(f) is None


# --- Polkadot RFC ---

class TestPolkadotRFC:
    def test_parse_standard_rfc(self, tmp_file):
        f = tmp_file("""# RFC-1: Agile Coretime

|                 |                                                         |
| --------------- | ------------------------------------------------------- |
| **Start Date**  | 30 June 2023                                            |
| **Description** | Agile periodic-sale-based model for assigning Coretime. |
| **Authors**     | Gavin Wood                                              |

## Summary

This proposes a periodic, sale-based method for assigning Coretime.
""", "0001-agile-coretime.md")
        result = parse_polkadot_rfc(f)

        assert result is not None
        assert result.id == "rfc-0001"
        assert result.chain == "polkadot"
        assert result.type == "rfc"
        assert result.number == 1
        assert "Agile Coretime" in result.title
        assert "Gavin Wood" in result.authors
        assert result.created == "30 June 2023"

    def test_no_number_returns_none(self, tmp_file):
        f = tmp_file("# README\n\nNot an RFC.", "README.md")
        assert parse_polkadot_rfc(f) is None


# --- Stacks SIP ---

class TestStacksSIP:
    def test_parse_standard_sip(self, tmp_file):
        f = tmp_file("""# Preamble

SIP Number: 010

Title: Standard Trait Definition for Fungible Tokens

Author: Friedger Müffke <friedger@stacks.org>

Consideration: Technical

Type: Standard

Status: Ratified

Created: 14 March 2021

License: CC0-1.0

# Abstract

This SIP defines a standard trait for fungible tokens.
""", "sip-010-fungible-token-standard.md")
        result = parse_stacks_sip(f)

        assert result is not None
        assert result.id == "sip-010"
        assert result.chain == "stacks"
        assert result.type == "sip"
        assert result.number == 10
        assert "Fungible Token" in result.title
        assert result.status == "Ratified"
        assert "Friedger" in result.authors

    def test_no_sip_number_returns_none(self, tmp_file):
        f = tmp_file("# Just a doc\n\nNo SIP number here.", "readme.md")
        assert parse_stacks_sip(f) is None


# --- Avalanche ACP ---

class TestAvalancheACP:
    def test_parse_standard_acp(self, tmp_file):
        f = tmp_file("""| ACP           | 77                                                    |
| :------------ | :---------------------------------------------------- |
| **Title**     | Reinventing Subnets                                   |
| **Author(s)** | Dhruba Basu ([@dhrubabasu](https://github.com/dhrubabasu)) |
| **Status**    | Activated ([Discussion](https://github.com/avalanche-foundation/ACPs/discussions/78)) |
| **Track**     | Standards                                             |
| **Replaces**  | ACP-13                                                |

## Abstract

Overhaul Subnet creation and management.
""", "77-reinventing-subnets/README.md")
        result = parse_avalanche_acp(f)

        assert result is not None
        assert result.id == "acp-77"
        assert result.chain == "avalanche"
        assert result.type == "acp"
        assert result.number == 77
        assert "Reinventing Subnets" in result.title
        assert "Activated" in result.status
        assert "Dhruba Basu" in result.authors
        assert result.category == "Standards"
        assert result.replaces == "ACP-13"

    def test_no_title_returns_none(self, tmp_file):
        f = tmp_file("| ACP | 99 |\n\nNo title row.", "99-test/README.md")
        assert parse_avalanche_acp(f) is None


# --- Contract Registry ---

class TestResolveContract:
    def test_resolve_uniswap(self):
        result = resolve_contract("uniswap")
        assert "Uniswap" in result
        assert "0x1F98431c8aD98523631AE4a59f267346ea31F765" in result

    def test_resolve_with_chain_filter(self):
        result = resolve_contract("weth", "42161")
        assert "Arbitrum" in result
        assert "0x82aF49447d8a07e3bd95BD0d56f35db45227D331" in result

    def test_resolve_unknown_protocol(self):
        result = resolve_contract("nonexistent_protocol")
        assert "not found" in result.lower()
        assert "Available:" in result

    def test_resolve_ens(self):
        result = resolve_contract("ens")
        assert "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e" in result

    def test_resolve_erc4337(self):
        result = resolve_contract("erc4337")
        assert "entry_point" in result.lower()
        assert "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789" in result

    def test_partial_match(self):
        result = resolve_contract("multi")
        assert "Multicall" in result
