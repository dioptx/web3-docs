"""Web3 Protocol Docs MCP Server — search and query EIPs, ERCs, BIPs, SIMDs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from db import ProposalDB
from parser import SOURCES, enrich_record, parse_fork_file


def _resolve_data_dir() -> Path:
    """Pick a writeable data dir.

    Priority: $WEB3_DOCS_DATA_DIR, then platform user-cache dir, then ./data
    (the last only when running from a source checkout).
    """
    override = os.environ.get("WEB3_DOCS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    try:
        from platformdirs import user_cache_dir
        return Path(user_cache_dir("web3-docs-mcp", "dioptx"))
    except ImportError:
        return Path.home() / ".cache" / "web3-docs-mcp"


DATA_DIR = _resolve_data_dir()
REPOS_DIR = DATA_DIR / "repos"
DB_PATH = DATA_DIR / "proposals.db"
CONTRACTS_PATH = Path(__file__).parent / "contracts.json"
_contracts_cache: dict | None = None

# Chain ID to name mapping
CHAIN_NAMES = {
    "1": "Ethereum", "10": "Optimism", "56": "BNB Chain", "100": "Gnosis",
    "137": "Polygon", "250": "Fantom", "324": "zkSync Era", "8453": "Base",
    "42161": "Arbitrum One", "43114": "Avalanche",
}

mcp = FastMCP(
    "web3-docs",
    instructions=(
        "Blockchain protocol specification server. 1,700+ proposals across 10 chains "
        "plus canonical contract addresses for 19 protocols.\n\n"
        "USE THIS when the developer:\n"
        "- Mentions EIPs, BIPs, SIMDs, ERCs, CIPs, TZIPs, or protocol upgrade names (London, Taproot, Cancun)\n"
        "- Asks about opcode behavior, precompile addresses, or EVM changes\n"
        "- Needs canonical contract addresses (Uniswap, Aave, WETH, ENS, etc.)\n"
        "- Asks which fork introduced a feature, or whether an EIP is live\n"
        "- Works with Cosmos ADRs, Polkadot RFCs, Stacks SIPs, Avalanche ACPs\n"
        "- Works with Cardano CIPs, Tezos TZIPs, Sui SIPs\n\n"
        "DO NOT USE for: live on-chain data, gas prices, block explorers, library API docs "
        "(use context7 instead), or general web3 tutorials.\n\n"
        "Workflow: resolve_proposal → find ID → query_protocol_docs → read spec. "
        "For contract addresses: resolve_contract directly."
    ),
)

DATA_DIR.mkdir(parents=True, exist_ok=True)
db = ProposalDB(DB_PATH)


@mcp.tool()
def resolve_proposal(query: str) -> str:
    """Find blockchain protocol proposals by keyword, concept, or proposal number.

    Searches across EIPs, ERCs, BIPs, SIMDs, Cosmos ADRs, Polkadot RFCs, Stacks SIPs,
    Avalanche ACPs, Cardano CIPs, Tezos TZIPs, Sui SIPs.
    Returns ranked results with fork info and status. Use the returned ID with query_protocol_docs to read the full spec.

    Args:
        query: What to search for. Accepts concept names, keywords, proposal IDs, fork names, or opcode names.
               Examples: "fee market", "ERC-721", "taproot", "blob transactions", "PUSH0", "London fork",
               "CIP-25", "FA2 token", "sui object"
    """
    results = db.search(query, limit=5)
    if not results:
        return "No proposals found. Try different keywords."

    lines = []
    for r in results:
        fork = f" [{r['fork']}]" if r.get("fork") else ""
        lines.append(f"{r['id']} | {r['title']} | {r['chain']}/{r['status']}{fork}")
    return "\n".join(lines)


@mcp.tool()
def resolve_contract(protocol: str, chain_id: str = "") -> str:
    """Look up canonical deployed contract addresses for Web3 protocols.

    Covers: Uniswap, Aave, Compound, Curve, ENS, Lido, Maker, WETH, USDT, USDC,
    Multicall3, ERC-4337 EntryPoint, Gnosis Safe, Permit2, Seaport, 1inch, Across,
    Chainlink, CREATE2 Deployer. Multi-chain (Ethereum, Arbitrum, Base, Optimism, Polygon, etc.)

    Args:
        protocol: Protocol name. Examples: "uniswap", "weth", "usdc", "aave", "safe"
        chain_id: Optional chain ID filter. "1"=Ethereum, "42161"=Arbitrum, "8453"=Base,
                  "10"=Optimism, "137"=Polygon. Omit for all chains.
    """
    global _contracts_cache
    if _contracts_cache is None:
        if not CONTRACTS_PATH.exists():
            return "Contract registry not found."
        try:
            _contracts_cache = json.loads(CONTRACTS_PATH.read_text())
        except (json.JSONDecodeError, OSError) as e:
            return f"Contract registry error: {e}"

    protocols = _contracts_cache.get("protocols", {})

    protocol_key = protocol.lower().strip().replace(" ", "_")
    # Match priority: exact > prefix > substring
    matched = None
    for key, data in protocols.items():
        if protocol_key == key:
            matched = (key, data)
            break
    if not matched:
        for key, data in protocols.items():
            if key.startswith(protocol_key) or data.get("name", "").lower().startswith(protocol_key):
                matched = (key, data)
                break
    if not matched:
        for key, data in protocols.items():
            if protocol_key in key or protocol_key in data.get("name", "").lower():
                matched = (key, data)
                break

    if not matched:
        available = ", ".join(sorted(protocols.keys()))
        return f"Not found: '{protocol}'. Available: {available}"

    key, data = matched
    lines = [f"{data['name']}"]

    for version, vdata in data.get("versions", {}).items():
        for cid, contracts in sorted(vdata.get("deployments", {}).items()):
            if chain_id and cid != chain_id:
                continue
            chain_name = CHAIN_NAMES.get(cid, f"chain:{cid}")
            for name, address in contracts.items():
                lines.append(f"{version} | {chain_name} | {name}: {address}")

    return "\n".join(lines)


@mcp.tool()
def query_protocol_docs(proposal_id: str, query: str = "") -> str:
    """Read the specification of a blockchain protocol proposal.

    Returns a compact metadata header plus the proposal body. When a query is provided,
    returns only the most relevant sections (saves tokens). Without a query, returns
    the full text (truncated to 4K chars — use a query to get specific sections of long proposals).

    Args:
        proposal_id: Proposal ID from resolve_proposal. Examples: "eip-1559", "bip-341", "erc-20"
        query: Optional focus question. Examples: "base fee calculation", "security", "backwards compatibility"
    """
    proposal = db.get(proposal_id)
    if not proposal:
        return f"Not found: '{proposal_id}'. Use resolve_proposal to search."

    # Compact key:value metadata header
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

    # On-chain refs (compact)
    refs_raw = proposal.get("on_chain_refs", "")
    if refs_raw:
        try:
            refs = json.loads(refs_raw)
            if refs:
                meta.append(f"on_chain_refs: {', '.join(refs[:8])}")
        except json.JSONDecodeError:
            pass

    # Impl links (compact, max 3)
    links_raw = proposal.get("impl_links", "")
    if links_raw:
        try:
            links = json.loads(links_raw)
            if links:
                meta.append(f"impl_links: {', '.join(links[:3])}")
        except json.JSONDecodeError:
            pass

    header = "\n".join(meta) + "\n---\n"
    body = proposal["body"]

    if query:
        content = _extract_relevant_sections(body, query, budget=6000)
    else:
        cutoff = body[:4000].rfind("\n")
        content = body[:cutoff] if cutoff > 2000 else body[:4000]
        if len(body) > 4000:
            content += "\n\n[truncated — use a query param to get specific sections]"

    return header + content


def _extract_relevant_sections(body: str, query: str, budget: int = 8000) -> str:
    """Split document into sections, score against query, return best ones."""
    sections = _split_by_heading(body)
    if not sections:
        return body[:budget]

    query_terms = set(re.findall(r"\w+", query.lower()))
    if not query_terms:
        return body[:budget]

    scored: list[tuple[float, int, str]] = []
    for i, section in enumerate(sections):
        text_lower = section.lower()
        score = sum(text_lower.count(term) for term in query_terms)
        # Boost first section (Abstract/Summary)
        if i == 0:
            score += 50
        scored.append((score, i, section))

    scored.sort(key=lambda x: (-x[0], x[1]))

    result_parts: list[tuple[int, str]] = []
    used = 0
    for score, idx, section in scored:
        if score == 0 and idx != 0:
            continue
        if used + len(section) > budget and used > 0:
            break
        result_parts.append((idx, section))
        used += len(section)

    result_parts.sort(key=lambda x: x[0])
    return "\n\n".join(part for _, part in result_parts)


def _split_by_heading(body: str) -> list[str]:
    """Split body into sections by markdown headings."""
    parts = re.split(r"(?=^#{1,4}\s)", body, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


# --- Sync ---


def sync():
    """Clone/pull source repos and rebuild the index."""
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    total_counts: dict[str, int] = {}

    for source in SOURCES:
        name = source["name"]
        repo_url = source["repo"]
        branch = source["branch"]
        repo_dir = REPOS_DIR / name

        # Clone or pull
        if repo_dir.exists():
            print(f"Updating {name}...")
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "pull", "--ff-only"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print(f"  Warning: git pull failed for {name}: {result.stderr.strip()}")
        else:
            print(f"Cloning {name}...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(repo_dir)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print(f"  Error: git clone failed for {name}: {result.stderr.strip()}")
                continue

        # Parse proposals
        glob_pattern = source["glob"]
        parser_fn = source["parser"]
        files = sorted(repo_dir.glob(glob_pattern))

        # For BIPs, filter to only top-level proposal files
        if name == "BIPs":
            files = [
                f for f in files
                if f.suffix in (".mediawiki", ".md")
                and re.match(r"bip-\d+\.", f.name)
            ]

        count = 0
        for filepath in files:
            try:
                record = parser_fn(filepath)
                if record and record.title:
                    enrich_record(record)
                    db.upsert(record)
                    count += 1
            except Exception as e:
                print(f"  Warning: failed to parse {filepath.name}: {e}")

        total_counts[name] = count
        print(f"  Indexed {count} {name}")

    # --- Fork mapping ---
    _sync_forks()

    # --- Backfill missing descriptions from body ---
    _backfill_descriptions()

    db.commit()

    summary = ", ".join(f"{count} {name}" for name, count in total_counts.items())
    total = sum(total_counts.values())
    print(f"\nTotal: {total} proposals indexed ({summary})")

    stats = db.stats()
    print(f"Database stats: {json.dumps(stats)}")


def _sync_forks():
    """Parse execution-specs fork files and map EIPs to their forks."""
    specs_dir = REPOS_DIR / "execution-specs"

    # Clone or pull
    if specs_dir.exists():
        print("Updating execution-specs...")
        subprocess.run(
            ["git", "-C", str(specs_dir), "pull", "--ff-only"],
            capture_output=True,
        )
    else:
        print("Cloning execution-specs...")
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/ethereum/execution-specs.git",
             str(specs_dir)],
            capture_output=True,
        )

    forks_dir = specs_dir / "src" / "ethereum" / "forks"
    if not forks_dir.exists():
        print("  Warning: forks directory not found in execution-specs")
        return

    fork_count = 0
    eip_mapped = 0

    for init_file in sorted(forks_dir.glob("*/__init__.py")):
        try:
            fork = parse_fork_file(init_file)
            if not fork:
                continue

            db.upsert_fork(
                name=fork.name,
                activation_block=fork.activation_block,
                activation_timestamp=fork.activation_timestamp,
                mainnet_date=fork.mainnet_date,
                eip_list=fork.eip_numbers,
            )

            for eip_num in fork.eip_numbers:
                db.set_fork_for_eip(eip_num, fork.display_name, fork.mainnet_date)
                eip_mapped += 1

            fork_count += 1
        except Exception as e:
            print(f"  Warning: failed to parse fork {init_file.parent.name}: {e}")

    if fork_count < 10:
        print(f"  WARNING: only {fork_count} forks found — execution-specs structure may have changed")
    print(f"  Mapped {eip_mapped} EIPs across {fork_count} forks")

    # Fill gaps for early Ethereum forks not fully in execution-specs
    _sync_early_ethereum_forks()

    # Bitcoin activations (no structured repo — canonical known activations)
    _sync_bitcoin_activations()


# Early Ethereum forks that may not be fully covered by execution-specs
_ETHEREUM_EARLY_FORKS = [
    ("Homestead", 1150000, "2016-03-14", [2, 7, 8]),
    ("Tangerine Whistle", 2463000, "2016-10-18", [150]),
    ("Spurious Dragon", 2675000, "2016-11-22", [155, 160, 161, 170]),
    ("Byzantium", 4370000, "2017-10-16", [100, 140, 196, 197, 198, 211, 214, 649, 658]),
    ("Constantinople", 7280000, "2019-02-28", [145, 1014, 1052, 1234, 1283]),
    ("Istanbul", 9069000, "2019-12-08", [152, 1108, 1344, 1884, 2028, 2200]),
    ("Berlin", 12244000, "2021-04-15", [2565, 2929, 2718, 2930]),
]


_HARDCODED_DESCRIPTIONS = {
    "eip-198": "Precompiled contract for big integer modular exponentiation, enabling RSA signature verification and other cryptographic operations.",
    "eip-1015": "Configurable on-chain issuance: block reward goes to a contract address instead of miner etherbase.",
    "eip-1901": "Add OpenRPC service discovery (rpc.discover method) to JSON-RPC services.",
    "eip-2937": "Add SET_INDESTRUCTIBLE (0xA8) opcode that prevents a contract from calling SELFDESTRUCT.",
    "eip-2970": "Add IS_STATIC (0x4A) opcode that pushes 1 if the current context is a STATICCALL.",
    "erc-55": "Mixed-case checksum address encoding for Ethereum addresses (EIP-55 checksum).",
}


def _backfill_descriptions():
    """Fill missing descriptions by re-extracting from body text or using hardcoded values."""
    from parser import _extract_abstract
    rows = db.conn.execute(
        "SELECT id, body FROM proposals WHERE description = ''"
    ).fetchall()
    if not rows:
        return
    count = 0
    for row in rows:
        desc = _HARDCODED_DESCRIPTIONS.get(row["id"]) or _extract_abstract(row["body"])
        if desc:
            db.conn.execute(
                "UPDATE proposals SET description = ? WHERE id = ?",
                (desc, row["id"]),
            )
            count += 1
    if count:
        print(f"  Backfilled {count} descriptions")


def _sync_early_ethereum_forks():
    """Fill fork mapping gaps for early Ethereum forks."""
    count = 0
    for fork_name, block, date, eip_nums in _ETHEREUM_EARLY_FORKS:
        db.upsert_fork(
            name=fork_name.lower().replace(" ", "_"),
            activation_block=block,
            activation_timestamp=None,
            mainnet_date=date,
            eip_list=eip_nums,
        )
        for eip_num in eip_nums:
            # Only set fork if not already set (execution-specs takes priority)
            proposal = db.get(f"eip-{eip_num}")
            if proposal and not proposal.get("fork"):
                db.set_fork_for_eip(eip_num, fork_name, date)
                count += 1
    print(f"  Filled {count} early fork mappings across {len(_ETHEREUM_EARLY_FORKS)} forks")


# Canonical Bitcoin soft fork activations and their BIPs
_BITCOIN_ACTIVATIONS = [
    ("P2SH", 160000, "2012-04-01", [16]),
    ("BIP34 (Height in Coinbase)", 227931, "2013-03-24", [34]),
    ("BIP66 (Strict DER)", 363725, "2015-07-04", [66]),
    ("BIP65 (CHECKLOCKTIMEVERIFY)", 388381, "2015-12-01", [65]),
    ("CSV (BIP68/112/113)", 419328, "2016-07-04", [68, 112, 113]),
    ("SegWit", 481824, "2017-08-24", [141, 143, 144, 145, 147, 148]),
    ("Taproot", 709632, "2021-11-14", [340, 341, 342]),
]


def _sync_bitcoin_activations():
    """Map Bitcoin BIPs to their activation soft forks."""
    count = 0
    for fork_name, block, date, bip_nums in _BITCOIN_ACTIVATIONS:
        db.upsert_fork(
            name=fork_name.lower().replace(" ", "_"),
            activation_block=block,
            activation_timestamp=None,
            mainnet_date=date,
            eip_list=bip_nums,
        )
        for bip_num in bip_nums:
            db.conn.execute(
                "UPDATE proposals SET fork = ?, fork_date = ? WHERE id = ?",
                (fork_name, date, f"bip-{bip_num}"),
            )
            count += 1
    print(f"  Mapped {count} BIPs across {len(_BITCOIN_ACTIVATIONS)} Bitcoin activations")


def main():
    if "--sync" in sys.argv:
        sync()
    elif "--stats" in sys.argv:
        stats = db.stats()
        print(json.dumps(stats, indent=2))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
