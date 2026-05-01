# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `keep_history` flag on `SOURCES`. When set, the source is cloned with `--filter=blob:none --no-checkout` (full commit history, no blob content) and the glob root is selectively checked out. Existing shallow clones are migrated automatically on next `--sync`. Cosmos ADRs and Avalanche ACPs use this so the parsers can read git-derived authors+dates.
- `_git_first_commits` / `_git_meta_for` parser helpers — cached per (repo, subpath) walk of `git log --reverse` to recover the earliest commit touching each file. Bails out cleanly on shallow clones or git errors.
- `tmp_git_repo` test fixture for tests that need a real git repo with deterministic dates+authors.

### Fixed
- **Tezos TZIP-26 was silently dropped from the index** because PyYAML's implicit timestamp resolver raises `ValueError` on `date: 2023-25-09` (DD-MM swap) and the parser only caught `yaml.YAMLError`. New `_StringDateLoader` keeps date scalars as strings; `_split_yaml_frontmatter` also catches `ValueError`/`TypeError` as defense in depth. Indexed TZIP count: 25 → 26.
- **Cosmos ADRs had no authors or created dates** (parser hardcoded both as empty). Now derived from git history. **60/60 ADRs gain authors+created.**
- **Avalanche ACPs had no created dates** (no Created row in upstream table). Same git-derived approach. **34/34 ACPs gain created.**
- **Stacks SIP author preambles are heterogeneous** — single-line, comma-separated, multi-line `*` bullets, multi-line `-` bullets, indented commas, same-line wraps, and the `Author(s):` key spelling. The previous regex caught only the first variant, leaving 13/28 SIPs with empty `authors`. New `_parse_stacks_preamble` + `_normalize_authors_block` handle all six shapes. **28/28 SIPs gain authors.**
- **Polkadot RFC table parser consumed across newlines** when a row was missing its trailing pipe (rfc-0017's Description), eating the next row's data. Anchored to single lines so each row matches independently.
- **Polkadot RFCs had `category=""`** (no upstream Category field). Defaults to `"RFC"` so DB rows aren't stuck empty. **44/44 RFCs gain category.**

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
