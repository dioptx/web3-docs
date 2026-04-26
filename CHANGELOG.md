# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-26

### Added
- Cardano CIP support (`cardano-foundation/CIPs`).
- Tezos TZIP support (`tezos/tzip` on GitLab).
- Sui SIP support (`sui-foundation/sips`).
- New MCP tool `list_fork_proposals(fork_name)` — answers "what's in Cancun?" / "which BIPs activated with Taproot?". Handles consensus-layer aliases (Pectra → Prague, Dencun → Cancun, Shapella → Shanghai, The Merge → Paris).
- Optional `chain` filter on `resolve_proposal` for keyword disambiguation when a term matches across chains (e.g. "staking" on `ethereum` vs `cosmos`).
- Empty-index detection: every read tool returns a clear actionable message pointing at `--sync` instead of a misleading "No proposals found" when the database is empty.
- `[project.scripts]` entry point — install via `uvx --from git+https://github.com/dioptx/web3-docs web3-docs-mcp`.
- `WEB3_DOCS_DATA_DIR` env var to override the index location.
- Hatchling-based wheel/sdist build, PyPI-ready metadata.
- CHANGELOG, hero GIF + asciinema cast, contract-lookup demo GIF.

### Changed
- Default data directory moved from `./data/` to the platform user cache directory (`~/.cache/web3-docs-mcp/` on macOS/Linux) so installed packages can write to it.
- All sync-time logging now goes to stderr; stdout stays exclusively the JSON-RPC channel.
- README is now MCP-client-agnostic (Claude Code / Cursor / Windsurf / Cline / Continue / Zed / Codex), with collapsible per-client install blocks.

### Fixed
- 17 sync `print()` calls that previously could have polluted stdout if invoked at MCP runtime now route through a dedicated stderr logger.

## [0.1.0] — 2026-04-07

### Added
- Initial standalone release.
- Sources: EIPs, ERCs, BIPs, SIMDs, Cosmos ADRs, Polkadot RFCs, Stacks SIPs, Avalanche ACPs.
- SQLite + FTS5 backed index, FastMCP stdio transport.
- Tools: `resolve_proposal`, `query_protocol_docs`, `resolve_contract`.
- Canonical contract registry covering 19 protocols across major EVM chains.
- BDD test suite under `tests/`.

[0.2.0]: https://github.com/dioptx/web3-docs/releases/tag/v0.2.0
[0.1.0]: https://github.com/dioptx/web3-docs/releases/tag/v0.1.0
