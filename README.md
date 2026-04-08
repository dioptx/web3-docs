# web3-docs

MCP server for Web3 protocol documentation — EIPs, ERCs, BIPs, SIMDs, Cosmos ADRs, Polkadot RFCs, Stacks SIPs, Avalanche ACPs, plus a canonical contract registry.

## What it does

A queryable MCP for blockchain protocol specs and canonical contract addresses. Stop digging through eight different GitHub repos when you need to look up EIP-4844, BIP-340, or which fork shipped PUSH0 — ask one tool that has them all indexed locally with FTS5 ranking. Bundles 1,500+ proposals across 7 chains plus addresses for 19 protocols on Ethereum, Arbitrum, Base, Optimism, Polygon, and more.

## Quick Start

Clone, install, and build the local index:

```bash
git clone https://github.com/dioptx/web3-docs.git
cd web3-docs
uv sync           # or: pip install -e .
python3 server.py --sync   # one-time: clones source repos and builds proposals.db
```

Register the server in `~/.claude.json` (or your project `.mcp.json`):

```json
{
  "mcpServers": {
    "web3-docs": {
      "command": "python3",
      "args": ["/absolute/path/to/web3-docs/server.py"],
      "type": "stdio"
    }
  }
}
```

If you use `uv`, swap `python3` for `uv` and prepend `["run", "--directory", "/absolute/path/to/web3-docs", "python3", "server.py"]`.

## Example queries

The server exposes three tools: `resolve_proposal`, `query_protocol_docs`, and `resolve_contract`.

**1. Look up EIP-4844 (proto-danksharding)**

> "Use web3-docs to find the EIP for blob transactions and explain the fee market."

Claude calls `resolve_proposal(query="blob transactions")` → `eip-4844`, then `query_protocol_docs(proposal_id="eip-4844", query="blob fee")` and returns the relevant spec section with metadata (status, fork, activation date).

**2. Fetch a Cosmos ADR**

> "Show me Cosmos ADR-001."

Claude calls `resolve_proposal(query="ADR-001")` → `query_protocol_docs(proposal_id="cosmos-adr-001")`. Returns the architectural decision record body with its status header.

**3. Get the canonical Uniswap address on Base**

> "What's the Uniswap router on Base?"

Claude calls `resolve_contract(protocol="uniswap", chain_id="8453")` and returns the deployed router/factory addresses for the matching Uniswap version on Base.

## Supported sources

Protocol specs (synced from upstream Git repos via `python3 server.py --sync`):

- **EIPs** — [ethereum/EIPs](https://github.com/ethereum/EIPs)
- **ERCs** — [ethereum/ERCs](https://github.com/ethereum/ERCs)
- **BIPs** — [bitcoin/bips](https://github.com/bitcoin/bips)
- **SIMDs** — [solana-foundation/solana-improvement-documents](https://github.com/solana-foundation/solana-improvement-documents)
- **Cosmos ADRs** — [cosmos/cosmos-sdk](https://github.com/cosmos/cosmos-sdk) (`docs/architecture`)
- **Polkadot RFCs** — [polkadot-fellows/RFCs](https://github.com/polkadot-fellows/RFCs)
- **Stacks SIPs** — [stacksgov/sips](https://github.com/stacksgov/sips)
- **Avalanche ACPs** — [avalanche-foundation/ACPs](https://github.com/avalanche-foundation/ACPs)

Fork mappings come from [ethereum/execution-specs](https://github.com/ethereum/execution-specs) plus canonical Bitcoin soft-fork activations (P2SH, SegWit, Taproot, …).

Contract registry (`contracts.json`) covers 19 protocols across major EVM chains:

`aave`, `across`, `chainlink`, `compound`, `create2_deployer`, `curve`, `ens`, `erc4337`, `gnosis_safe`, `lido`, `maker`, `multicall`, `oneinch`, `permit2`, `seaport`, `uniswap`, `usdc`, `usdt`, `weth`.

## Status

v0.1.0 — initial standalone release (2026-04-07). SQLite + FTS5 backed, FastMCP stdio transport, BDD test suite under `tests/`.
