"""Parsers for Web3 protocol proposal formats (EIPs, ERCs, BIPs, SIMDs)."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from db import ProposalRecord


# --- Git history cache (used by parsers whose upstream omits authors/created) ---

_GIT_HISTORY_CACHE: dict[tuple[Path, str], dict[str, tuple[str, str]]] = {}


def _git_first_commits(repo_dir: Path, subpath: str = ".") -> dict[str, tuple[str, str]]:
    """Return ``{relpath: (iso_date, author_name)}`` for every file under
    ``subpath`` in the repo, keyed by the commit that *added* the file.

    Scoping the walk to ``subpath`` keeps the call cheap on large repos like
    cosmos-sdk (otherwise git would walk the entire history of every file).
    Requires a non-shallow clone (partial clones with full commit history are
    fine). Returns an empty dict if the repo is shallow or git fails.
    """
    if not (repo_dir / ".git").exists() and not (repo_dir / ".git").is_file():
        return {}
    if (repo_dir / ".git" / "shallow").exists():
        return {}

    # Walk commits oldest-first and remember the *earliest* commit that touched
    # each path. We don't use --diff-filter=A because reorgs that moved a file
    # into its current location (e.g. Avalanche ACPs/<num>-<slug>/README.md
    # was previously ACPs/X-<slug>.md) would otherwise leave the moved file
    # without any date. For files that were never renamed this is the creation
    # commit; for moved files it's the rename-to-current-path commit. Both are
    # acceptable creation-of-this-record dates.
    cmd = [
        "git", "-C", str(repo_dir),
        "log", "--reverse",
        "--name-only", "--pretty=format:COMMIT%x09%aI%x09%an",
    ]
    if subpath and subpath != ".":
        cmd += ["--", subpath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}

    out: dict[str, tuple[str, str]] = {}
    cur_date = cur_author = ""
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT\t"):
            parts = line.split("\t", 2)
            if len(parts) == 3:
                cur_date, cur_author = parts[1], parts[2]
        elif line.strip() and cur_date:
            out.setdefault(line.strip(), (cur_date, cur_author))
    return out


def _git_history_for(repo_dir: Path, subpath: str = ".") -> dict[str, tuple[str, str]]:
    """Cached wrapper around :func:`_git_first_commits`."""
    key = (repo_dir, subpath)
    if key not in _GIT_HISTORY_CACHE:
        _GIT_HISTORY_CACHE[key] = _git_first_commits(repo_dir, subpath)
    return _GIT_HISTORY_CACHE[key]


def _git_meta_for(filepath: Path, subpath: str = ".") -> tuple[str, str]:
    """Return ``(iso_date, author)`` for the commit that added ``filepath``,
    or ``("", "")`` if no git history is available. ``subpath`` scopes the
    underlying ``git log`` walk so very large repos stay cheap.
    """
    repo_root = filepath.parent
    while repo_root.parent != repo_root:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    if not (repo_root / ".git").exists():
        return "", ""
    history = _git_history_for(repo_root, subpath)
    if not history:
        return "", ""
    try:
        rel = str(filepath.relative_to(repo_root))
    except ValueError:
        return "", ""
    return history.get(rel, ("", ""))


class _StringDateLoader(yaml.SafeLoader):
    """SafeLoader variant that keeps date/timestamp scalars as strings.

    PyYAML's default loaders auto-construct datetime.date for YYYY-MM-DD scalars,
    raising ValueError on malformed dates (e.g. tzip-26's `date: 2023-25-09`).
    Treating them as strings keeps such proposals indexable.
    """


_StringDateLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for (tag, regexp) in resolvers
         if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def parse_eip(filepath: Path) -> ProposalRecord | None:
    """Parse EIP/ERC markdown with YAML frontmatter (--- delimited).

    Works for both EIPs and ERCs since they share the same format.
    The `eip` field in frontmatter holds the proposal number for both.
    """
    text = filepath.read_text(errors="replace")
    meta, body = _split_yaml_frontmatter(text)
    if not meta:
        return None

    number = meta.get("eip")
    if number is None:
        return None

    # Determine type from the file path or category
    is_erc = "/ERCS/" in str(filepath) or "/ercs/" in str(filepath)
    prop_type = "erc" if is_erc else "eip"
    prop_id = f"{prop_type}-{number}"

    requires_raw = meta.get("requires", "")
    if isinstance(requires_raw, list):
        requires = ", ".join(str(r) for r in requires_raw)
    else:
        requires = str(requires_raw) if requires_raw else ""

    return ProposalRecord(
        id=prop_id,
        chain="ethereum",
        type=prop_type,
        number=int(number),
        title=meta.get("title", ""),
        status=meta.get("status", ""),
        category=meta.get("category", meta.get("type", "")),
        authors=meta.get("author", ""),
        created=str(meta.get("created", "")),
        requires=requires,
        description=meta.get("description", _extract_abstract(body)),
        body=body,
        discussions_to=meta.get("discussions-to", ""),
        superseded_by=str(meta.get("superseded-by", "")),
        last_call_deadline=str(meta.get("last-call-deadline", "")),
        withdrawal_reason=meta.get("withdrawal-reason", ""),
    )


def parse_simd(filepath: Path) -> ProposalRecord | None:
    """Parse SIMD markdown with YAML frontmatter.

    SIMD uses `simd` field (zero-padded string) and `authors` as a YAML list.
    """
    text = filepath.read_text(errors="replace")
    meta, body = _split_yaml_frontmatter(text)
    if not meta:
        return None

    simd_raw = meta.get("simd")
    if simd_raw is None:
        return None

    # Strip leading zeros for the number, keep padded for the ID
    simd_str = str(simd_raw).strip("'\"")
    number = int(simd_str)
    prop_id = f"simd-{simd_str.zfill(4)}"

    authors_raw = meta.get("authors", [])
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a) for a in authors_raw)
    else:
        authors = str(authors_raw)

    # Parse development status if present
    dev_raw = meta.get("development", [])
    dev_str = ""
    if isinstance(dev_raw, list):
        dev_str = "; ".join(str(d) for d in dev_raw)

    return ProposalRecord(
        id=prop_id,
        chain="solana",
        type="simd",
        number=number,
        title=meta.get("title", ""),
        status=meta.get("status", ""),
        category=meta.get("category", meta.get("type", "")),
        authors=authors,
        created=str(meta.get("created", "")),
        requires="",
        description=_extract_abstract(body),
        body=body if not dev_str else f"**Development**: {dev_str}\n\n{body}",
        feature=str(meta.get("feature", "")),
        superseded_by=str(meta.get("superseded-by", "")),
        extends=str(meta.get("extends", "")),
    )


def _normalize_bip_status(raw: str) -> str:
    """Normalize BIP statuses. Strip parenthetical comments, map non-standard values."""
    cleaned = re.sub(r'\s*\(.*?\)', '', str(raw)).strip()
    bip_status_map = {
        "DEPLOYED": "Final", "COMPLETE": "Final", "ACTIVE": "Active",
        "CLOSED": "Withdrawn", "OBSOLETE": "Replaced",
    }
    return bip_status_map.get(cleaned.upper(), cleaned)


def parse_bip(filepath: Path) -> ProposalRecord | None:
    """Parse BIP in either mediawiki or markdown format.

    MediaWiki BIPs use plain `Key: Value` frontmatter (no YAML delimiters).
    Markdown BIPs use code-fenced or YAML frontmatter.
    """
    text = filepath.read_text(errors="replace")
    suffix = filepath.suffix.lower()

    if suffix == ".mediawiki":
        meta, body = _split_bip_mediawiki_frontmatter(text)
        body = _mediawiki_to_markdown(body)
    else:
        meta, body = _split_yaml_frontmatter(text)
        if not meta:
            meta, body = _split_bip_mediawiki_frontmatter(text)

    if not meta:
        return None

    # BIP field can be uppercase or lowercase
    number_raw = meta.get("BIP") or meta.get("bip")
    if number_raw is None:
        return None

    number = int(str(number_raw).strip())
    prop_id = f"bip-{number}"

    authors_raw = meta.get("Authors") or meta.get("Author") or meta.get("author") or ""
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a).strip() for a in authors_raw)
    else:
        authors = str(authors_raw).strip()

    title = meta.get("Title") or meta.get("title") or ""
    status = _normalize_bip_status(meta.get("Status") or meta.get("status") or "")
    layer = meta.get("Layer") or meta.get("layer") or ""
    bip_type = meta.get("Type") or meta.get("type") or ""
    category = layer if layer else bip_type
    created = meta.get("Created") or meta.get("Assigned") or meta.get("created") or ""

    replaces_raw = meta.get("Replaces") or meta.get("replaces") or ""
    requires_raw = meta.get("Requires") or meta.get("requires") or ""
    superseded_raw = (
        meta.get("Superseded-By") or meta.get("superseded-by")
        or meta.get("Proposed-Replacement") or meta.get("proposed-replacement")
        or ""
    )

    return ProposalRecord(
        id=prop_id,
        chain="bitcoin",
        type="bip",
        number=number,
        title=str(title),
        status=str(status),
        category=str(category),
        authors=authors,
        created=str(created),
        requires=str(requires_raw),
        description=_extract_abstract(body),
        body=body,
        layer=str(layer),
        replaces=str(replaces_raw),
        superseded_by=str(superseded_raw),
        discussions_to=str(meta.get("Comments-URI") or meta.get("comments-uri") or meta.get("Discussion") or meta.get("discussion") or ""),
    )


# --- Frontmatter Splitting ---


def _split_yaml_frontmatter(text: str) -> tuple[dict | None, str]:
    """Split YAML frontmatter from body. Returns (metadata_dict, body_text)."""
    text = text.strip()
    if not text.startswith("---"):
        return None, text

    end = text.find("---", 3)
    if end == -1:
        return None, text

    front = text[3:end].strip()
    body = text[end + 3:].strip()

    try:
        meta = yaml.load(front, Loader=_StringDateLoader)
        if not isinstance(meta, dict):
            return None, text
        return meta, body
    except (yaml.YAMLError, ValueError, TypeError):
        return None, text


def _split_bip_mediawiki_frontmatter(text: str) -> tuple[dict | None, str]:
    """Parse BIP-style plain text frontmatter (Key: Value pairs).

    BIPs use a <pre>...</pre> block or just plain key-value lines at the top.
    Multi-line values (like Authors) are continued with indentation.
    """
    lines = text.split("\n")
    meta: dict[str, str] = {}
    body_start = 0
    in_pre = False
    current_key = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle <pre> wrapper
        if stripped.lower() == "<pre>":
            in_pre = True
            continue
        if stripped.lower() == "</pre>":
            in_pre = False
            body_start = i + 1
            break

        # Key: Value pattern (may be indented inside <pre>)
        kv_match = re.match(r"^\s*([A-Za-z][A-Za-z\-_ ]*?):\s*(.*)$", line)

        if kv_match:
            current_key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            meta[current_key] = value
            body_start = i + 1
        elif stripped and current_key and in_pre:
            # Continuation of multi-line value (indented lines inside <pre>)
            meta[current_key] = meta[current_key] + ", " + stripped
            body_start = i + 1
        elif stripped == "":
            if meta and not in_pre:
                body_start = i + 1
                break
        elif not meta and not in_pre:
            break
        else:
            if not in_pre:
                body_start = i
                break

    if not meta:
        return None, text

    body = "\n".join(lines[body_start:]).strip()
    return meta, body


# --- MediaWiki to Markdown Conversion ---


def _mediawiki_to_markdown(text: str) -> str:
    """Convert MediaWiki markup to Markdown-like text.

    Doesn't need to be perfect -- consumed by LLMs, not rendered in a browser.
    """
    # Headers: ==H2== → ## H2, ===H3=== → ### H3
    text = re.sub(r"^====\s*(.+?)\s*====", r"#### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^===\s*(.+?)\s*===", r"### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^==\s*(.+?)\s*==", r"## \1", text, flags=re.MULTILINE)

    # Bold/italic
    text = re.sub(r"'''(.+?)'''", r"**\1**", text)
    text = re.sub(r"''(.+?)''", r"*\1*", text)

    # Links: [url text] → [text](url)
    text = re.sub(r"\[(\S+)\s+([^\]]+)\]", r"[\2](\1)", text)

    # Inline code
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text)
    text = re.sub(r"<tt>(.*?)</tt>", r"`\1`", text)

    # Code blocks
    text = re.sub(r"<source[^>]*>(.*?)</source>", r"```\n\1\n```", text, flags=re.DOTALL)
    text = re.sub(r"<pre>(.*?)</pre>", r"```\n\1\n```", text, flags=re.DOTALL)

    # Numbered lists: # item → 1. item (only single #, not ## headings)
    text = re.sub(r"^#(?!#)\s+", "1. ", text, flags=re.MULTILINE)

    return text


# --- Body Text Extractors ---


# Common noise hex values to skip
_HEX_NOISE = frozenset({
    "0x00", "0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07",
    "0x08", "0x09", "0x0a", "0x0b", "0x0c", "0x0d", "0x0e", "0x0f",
    "0x10", "0x20", "0x30", "0x40", "0x60", "0x80", "0xff", "0xfe",
    "0xef", "0x00000000", "0xffffffff", "0xffffffffffffffff",
})

_KNOWN_OPCODES = {
    "PUSH0": "0x5f", "MCOPY": "0x5e", "TLOAD": "0x5c", "TSTORE": "0x5d",
    "BLOBHASH": "0x49", "BLOBBASEFEE": "0x4a", "BASEFEE": "0x48",
    "SELFBALANCE": "0x47", "CHAINID": "0x46", "CREATE2": "0xf5",
    "STATICCALL": "0xfa", "REVERT": "0xfd", "DELEGATECALL": "0xf4",
    "RETURNDATASIZE": "0x3d", "RETURNDATACOPY": "0x3e",
}


def extract_on_chain_refs(body: str) -> list[str]:
    """Extract hex addresses, opcode references, and precompile addresses from body."""
    refs: set[str] = set()

    # Contract/precompile addresses: 0x followed by 8-40 hex chars
    for match in re.finditer(r'\b(0x[0-9a-fA-F]{8,40})\b', body):
        addr = match.group(1).lower()
        if addr not in _HEX_NOISE:
            refs.add(addr)

    # Hex opcode patterns: "opcode 0xNN" or "OPCODE (0xNN)"
    for match in re.finditer(r'(?:opcode|OPCODE|instruction)\s*[:(]?\s*(0x[0-9a-fA-F]{2,4})', body):
        refs.add(f"opcode:{match.group(1).lower()}")

    # Decimal opcode patterns: "opcode 95" or "opcode number 0x5f (95)"
    for match in re.finditer(r'(?:opcode|instruction)\s+(?:number\s+)?(\d{1,3})\b', body, re.IGNORECASE):
        num = int(match.group(1))
        if 0 < num < 256:
            refs.add(f"opcode:0x{num:02x}")

    # Named EVM instructions with known opcode numbers
    for name, code in _KNOWN_OPCODES.items():
        if re.search(rf'\b{name}\b', body):
            refs.add(f"opcode:{code}:{name}")

    # Precompile patterns: "precompile at 0x..." or "precompiled contract at 0x..."
    for match in re.finditer(r'precompile[d]?\s+(?:contract\s+)?(?:at\s+)?(0x[0-9a-fA-F]{2,40})', body, re.IGNORECASE):
        refs.add(match.group(1).lower())

    # Address in table format: | 0x... | or address: 0x...
    for match in re.finditer(r'(?:address|addr)[:\s]+`?(0x[0-9a-fA-F]{8,42})`?', body, re.IGNORECASE):
        addr = match.group(1).lower()
        if addr not in _HEX_NOISE:
            refs.add(addr)

    # Gas cost constants mentioned explicitly (e.g., "costs 700 gas", "gas cost of 3")
    for match in re.finditer(r'(?:costs?|gas cost(?:\s+of)?)\s+(\d{2,6})\s*gas', body, re.IGNORECASE):
        refs.add(f"gas:{match.group(1)}")

    return sorted(refs)


def extract_impl_links(body: str) -> list[str]:
    """Extract GitHub URLs and resolve relative EIP references from proposal body text."""
    links: set[str] = set()

    # Full GitHub URLs
    for match in re.finditer(r'https?://github\.com/[^\s\)\]\}>,\'"]+', body):
        url = match.group(0).rstrip(".")
        if any(url.endswith(ext) for ext in (".png", ".jpg", ".gif", ".svg")):
            continue
        links.add(url)

    # Relative EIP/ERC links: ./eip-1559.md or ../EIPS/eip-1559.md
    for match in re.finditer(r'(?:\./|\.\./)(?:EIPS/)?(?:ERCS/)?(eip|erc)-(\d+)\.md', body):
        prop_type = match.group(1).lower()
        num = match.group(2)
        links.add(f"https://eips.ethereum.org/EIPS/{prop_type}-{num}")

    return sorted(links)


def enrich_record(record: ProposalRecord) -> ProposalRecord:
    """Post-parse enrichment: extract on-chain refs and impl links from body."""
    refs = extract_on_chain_refs(record.body)
    links = extract_impl_links(record.body)
    if refs:
        record.on_chain_refs = json.dumps(refs)
    if links:
        record.impl_links = json.dumps(links)
    return record


# --- Helpers ---


def _extract_abstract(body: str) -> str:
    """Extract the Abstract/Summary/Context section from the body as a description."""
    # Try in priority order: Abstract > Summary > Simple Summary > Context > Overview > Motivation
    for heading in ("Abstract", "Summary", "Simple Summary", "Context", "Overview", "Motivation"):
        match = re.search(
            rf"^#{{1,3}}\s*{re.escape(heading)}\s*\n(.*?)(?=^#{{1,3}}\s|\Z)",
            body,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if match:
            abstract = match.group(1).strip()
            if len(abstract) > 300:
                abstract = abstract[:297] + "..."
            return abstract

    # Fallback: first meaningful paragraph (join continuation lines)
    paragraph = []
    in_para = False
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("---") or stripped.startswith("```"):
            if in_para and paragraph:
                break
            continue
        if stripped:
            paragraph.append(stripped)
            in_para = True
        elif in_para and paragraph:
            break

    text = " ".join(paragraph)
    if len(text) > 20:
        if len(text) > 300:
            text = text[:297] + "..."
        return text
    return ""


# --- Fork Mapping Parser ---


@dataclass
class ForkRecord:
    name: str               # "london", "cancun"
    display_name: str       # "London", "Cancun"
    eip_numbers: list[int]
    activation_block: int | None
    activation_timestamp: int | None
    mainnet_date: str       # "August 5, 2021"


_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _normalize_date(raw: str) -> str:
    """Normalize dates to YYYY-MM-DD. Handles 'August 5, 2021' and '2024-03-13 13:55:35'."""
    raw = raw.strip()
    if not raw:
        return ""
    # Reject placeholder/garbage values (backtick-padded empty fields from execution-specs)
    if not re.search(r"\d", raw):
        return ""
    # Already ISO-ish: 2024-03-13 or 2024-03-13 13:55:35
    iso_match = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if iso_match:
        return iso_match.group(1)
    # Human-readable: "August 5, 2021" or "June 30, 2021"
    human_match = re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if human_match:
        month_name = human_match.group(1).lower()
        day = int(human_match.group(2))
        year = human_match.group(3)
        month = _MONTH_MAP.get(month_name, "01")
        return f"{year}-{month}-{day:02d}"
    return ""


def parse_fork_file(filepath: Path) -> ForkRecord | None:
    """Parse an execution-specs fork __init__.py to extract EIP mapping + activation data."""
    text = filepath.read_text(errors="replace")

    # Extract docstring
    doc_match = re.search(r'"""(.*?)"""', text, re.DOTALL)
    if not doc_match:
        return None

    docstring = doc_match.group(1)

    # Extract fork name from directory
    fork_name = filepath.parent.name  # e.g., "london"
    display_name = fork_name.replace("_", " ").title()

    # Extract EIP numbers from "### Changes" section (deduplicate)
    eip_numbers = sorted(set(int(m) for m in re.findall(r'EIP-(\d+)', docstring)))
    if not eip_numbers:
        return None

    # Extract activation: ByBlockNumber(N) or ByTimestamp(N)
    activation_block = None
    activation_timestamp = None

    block_match = re.search(r'ByBlockNumber\((\d+)\)', text)
    if block_match:
        activation_block = int(block_match.group(1))

    ts_match = re.search(r'ByTimestamp\((\d+)\)', text)
    if ts_match:
        activation_timestamp = int(ts_match.group(1))

    # Extract mainnet date from upgrade schedule table
    mainnet_date = ""
    # Match: | Mainnet | 12,965,000 | August 5, 2021 | ... |
    # or:    | Mainnet | `1710338135` | 2024-03-13 13:55:35 | ... |
    date_match = re.search(
        r'\|\s*Mainnet\s*\|[^|]+\|\s*(.+?)\s*\|',
        docstring
    )
    if date_match:
        mainnet_date = date_match.group(1).strip()

    return ForkRecord(
        name=fork_name,
        display_name=display_name,
        eip_numbers=eip_numbers,
        activation_block=activation_block,
        activation_timestamp=activation_timestamp,
        mainnet_date=_normalize_date(mainnet_date),
    )


# --- Additional Chain Parsers ---


def _normalize_cosmos_status(raw: str) -> str:
    """Normalize Cosmos ADR status to official values: PROPOSED, LAST CALL, ACCEPTED, REJECTED."""
    # Strip markdown formatting, trailing periods, parentheticals, links
    cleaned = raw.strip("*_ >")
    cleaned = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', cleaned)  # strip markdown links
    cleaned = re.sub(r'\(.*?\)', '', cleaned)  # strip parentheticals
    cleaned = re.sub(r'\.\s*$', '', cleaned)  # strip trailing period
    # Remove implementation qualifiers
    cleaned = re.sub(
        r'\s*(Partially\s+Implemented|Not\s+Implemented|Implemented|Implementation\s+started).*',
        '', cleaned, flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip().upper()

    status_map = {
        "PROPOSED": "PROPOSED",
        "ACCEPTED": "ACCEPTED",
        "REJECTED": "REJECTED",
        "LAST CALL": "LAST CALL",
        "DRAFT": "PROPOSED",
        "ABANDONED": "REJECTED",
        "SUPERSEDED": "ACCEPTED",
        "IMPLEMENTED": "ACCEPTED",
    }
    # Try prefix match for compound statuses like "SUPERSEDED by ADR-045"
    for key, val in status_map.items():
        if cleaned.startswith(key):
            return val
    return cleaned or "PROPOSED"


def parse_cosmos_adr(filepath: Path) -> ProposalRecord | None:
    """Parse Cosmos SDK ADR. Format: # ADR NNN: Title, then markdown sections."""
    text = filepath.read_text(errors="replace")

    # Extract number from filename: adr-001-coin-source-tracing.md
    num_match = re.search(r'adr[_-]?(\d+)', filepath.name, re.IGNORECASE)
    if not num_match:
        return None
    number = int(num_match.group(1))

    # Extract title from first H1
    title_match = re.search(r'^#\s+ADR[- ]?\d+[:\s]*(.+)', text, re.MULTILINE | re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else filepath.stem.replace("-", " ").title()

    # Extract status from ## Status section
    status = ""
    status_match = re.search(
        r'^##\s*Status\s*\n+(.+?)(?=\n#|\Z)',
        text, re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if status_match:
        status_line = status_match.group(1).strip().split("\n")[0]
        status = _normalize_cosmos_status(status_line)

    # Body is everything after the title
    body = text.strip()

    # ADRs have no preamble metadata; pull authors+created from git history.
    created, authors = _git_meta_for(filepath, "docs/architecture")

    return ProposalRecord(
        id=f"adr-{number:03d}",
        chain="cosmos",
        type="adr",
        number=number,
        title=title,
        status=status,
        category="Architecture",
        authors=authors,
        created=created,
        requires="",
        description=_extract_abstract(body),
        body=body,
    )


def parse_polkadot_rfc(filepath: Path) -> ProposalRecord | None:
    """Parse Polkadot RFC. Format: # RFC-N: Title, then metadata table.

    Status is tracked externally (on-chain Fellowship vote + Notion dashboard).
    All RFCs merged into the text/ directory have been approved by the Fellowship.
    """
    text = filepath.read_text(errors="replace")

    # Extract number from filename: 0001-agile-coretime.md
    num_match = re.search(r'^(\d+)', filepath.name)
    if not num_match:
        return None
    number = int(num_match.group(1))

    # Extract title from H1
    title_match = re.search(r'^#\s+(?:RFC-?\d+[:\s]*)?(.+)', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract metadata from table — anchor to single lines so a malformed
    # row (e.g. RFC-0017's Description without a trailing pipe) can't consume
    # subsequent rows like Authors.
    authors = ""
    start_date = ""
    description = ""
    for match in re.finditer(
        r'^\|[ \t]*\*\*([^*|\n]+?)\*\*[ \t]*\|[ \t]*([^\n|]*?)[ \t]*\|',
        text, re.MULTILINE,
    ):
        key = match.group(1).strip().lower()
        val = match.group(2).strip()
        if "author" in key:
            authors = val
        elif ("start" in key and "date" in key) or "proposition date" in key:
            start_date = val
        elif "description" in key:
            description = val

    body = text.strip()

    return ProposalRecord(
        id=f"rfc-{number:04d}",
        chain="polkadot",
        type="rfc",
        number=number,
        title=title,
        status="Approved",
        category="RFC",
        authors=authors,
        created=start_date,
        requires="",
        description=description or _extract_abstract(body),
        body=body,
    )


def _normalize_sip_status(raw: str) -> str:
    """Normalize SIP status to consistent casing (upstream has mixed casing)."""
    cleaned = raw.strip()
    if not cleaned:
        return ""
    # Title-case hyphenated statuses: "Activation-in-Progress" → "Activation-In-Progress"
    return "-".join(part.capitalize() for part in cleaned.split("-"))


def _parse_stacks_preamble(text: str) -> dict[str, str]:
    """Parse a Stacks SIP preamble into {lowercase_key: raw_block}.

    Stacks SIPs use four header shapes that all need to round-trip cleanly:

    1. ``Key: value`` on one line.
    2. ``Key: value, more`` followed by an unindented line-wrap continuation
       (sip-020).
    3. ``Key:\\n    indented continuation, comma-separated`` (sip-015).
    4. ``Key:\\n\\n* bullet\\n* bullet`` (sip-021), with optional blank line
       between header and bullets.

    Field headers must start at column 0 and not be a bullet marker. Anything
    that follows a header until the next header (or blank-line-then-header) is
    that field's block. Callers normalize the block with helpers below.
    """
    # Bound to the preamble — everything after the first body section
    # heading (`## Abstract`, `## Introduction`, etc.) is not metadata.
    body_split = re.search(r"^##\s", text, re.MULTILINE)
    preamble = text[: body_split.start()] if body_split else text

    blocks: dict[str, list[str]] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    blank_run = 0

    for line in preamble.splitlines():
        is_blank = line.strip() == ""
        is_indented = line.startswith((" ", "\t"))
        is_bullet = bool(re.match(r"\s*[-*]\s", line))
        header = re.match(r"^([A-Za-z][\w\s\-()]*?):[ \t]*(.*)$", line)

        if header and not is_indented and not is_bullet:
            if current_key is not None:
                blocks.setdefault(current_key, current_lines)
            current_key = header.group(1).strip().lower()
            tail = header.group(2).strip()
            current_lines = [tail] if tail else []
            blank_run = 0
        elif current_key is not None:
            if is_blank:
                blank_run += 1
                # Two consecutive blanks ends the field.
                if blank_run >= 2:
                    blocks.setdefault(current_key, current_lines)
                    current_key = None
                    current_lines = []
                    blank_run = 0
            else:
                blank_run = 0
                current_lines.append(line)

    if current_key is not None:
        blocks.setdefault(current_key, current_lines)

    return {k: "\n".join(v).strip() for k, v in blocks.items()}


def _normalize_authors_block(raw: str) -> str:
    """Flatten a Stacks author block into a comma-separated string.

    Handles both ``*`` and ``-`` bullet markers; falls back to comma-split
    for indented continuation or wrapped same-line lists.
    """
    if not raw:
        return ""
    if re.search(r"(?:^|\n)[ \t]*[-*]\s", raw):
        names: list[str] = []
        for line in raw.splitlines():
            cleaned = re.sub(r"^[ \t]*[-*]\s*", "", line).strip()
            if cleaned:
                names.append(cleaned)
        return ", ".join(names)
    flat = re.sub(r"\s+", " ", raw).strip().rstrip(",")
    parts = [p.strip() for p in flat.split(",") if p.strip()]
    return ", ".join(parts)


def parse_stacks_sip(filepath: Path) -> ProposalRecord | None:
    """Parse Stacks SIP. Format: # Preamble with key: value pairs."""
    text = filepath.read_text(errors="replace")

    # Extract SIP number from preamble or filename
    num_match = re.search(r'SIP\s*Number:\s*(\d+)', text, re.IGNORECASE)
    if not num_match:
        num_match = re.search(r'sip[_-]?(\d+)', filepath.name, re.IGNORECASE)
    if not num_match:
        return None
    number = int(num_match.group(1))

    meta = _parse_stacks_preamble(text)
    # Normalize across the three observed key spellings: `Author`, `Authors`, `Author(s)`.
    authors_raw = (
        meta.get("authors")
        or meta.get("author")
        or meta.get("author(s)")
        or ""
    )
    meta["authors"] = _normalize_authors_block(authors_raw)

    title = meta.get("title", "")
    if not title:
        return None

    body = text.strip()

    return ProposalRecord(
        id=f"sip-{number:03d}",
        chain="stacks",
        type="sip",
        number=number,
        title=title,
        status=_normalize_sip_status(meta.get("status", "")),
        category=meta.get("type", meta.get("consideration", "")),
        authors=meta.get("authors") or meta.get("author", ""),
        created=meta.get("created", ""),
        requires="",
        description=_extract_abstract(body),
        body=body,
        discussions_to=meta.get("discussions-to", ""),
    )


def parse_avalanche_acp(filepath: Path) -> ProposalRecord | None:
    """Parse Avalanche ACP. Format: metadata table at top with pipe-delimited rows."""
    text = filepath.read_text(errors="replace")

    # Extract metadata from table rows
    meta: dict[str, str] = {}
    for match in re.finditer(r'\|\s*\*?\*?([^|*]+?)\*?\*?\s*\|\s*(.+?)\s*\|', text):
        key = match.group(1).strip().lower()
        val = match.group(2).strip()
        meta[key] = val

    # Get ACP number
    number_raw = meta.get("acp", "")
    if not number_raw:
        num_match = re.search(r'(\d+)', filepath.parent.name)
        if not num_match:
            return None
        number_raw = num_match.group(1)

    try:
        number = int(number_raw)
    except ValueError:
        return None

    title = meta.get("title", "")
    if not title:
        return None

    # Clean status (may contain markdown links)
    status = meta.get("status", "")
    status = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', status).strip()
    # Remove parenthetical like "(Discussion ...)"
    status = re.sub(r'\s*\(.*?\)', '', status).strip()

    authors = meta.get("author(s)", meta.get("authors", meta.get("author", "")))
    # Clean markdown links from author
    authors = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', authors)

    body = text.strip()

    # ACPs have no Created row in their preamble table; pull it from git history.
    created, _ = _git_meta_for(filepath, "ACPs")

    return ProposalRecord(
        id=f"acp-{number}",
        chain="avalanche",
        type="acp",
        number=number,
        title=title,
        status=status,
        category=meta.get("track", ""),
        authors=authors,
        created=created,
        requires="",
        description=_extract_abstract(body),
        body=body,
        replaces=meta.get("replaces", ""),
        superseded_by=meta.get("superseded-by", ""),
    )


def parse_cardano_cip(filepath: Path) -> ProposalRecord | None:
    """Parse Cardano CIP with YAML frontmatter.

    Cardano CIPs live in CIP-XXXX/README.md with standard YAML frontmatter
    containing CIP number, Title, Status, Category, Authors (list), Created.
    """
    text = filepath.read_text(errors="replace")
    meta, body = _split_yaml_frontmatter(text)
    if not meta:
        return None

    number_raw = meta.get("CIP") or meta.get("cip")
    if number_raw is None:
        return None
    try:
        number = int(str(number_raw).strip())
    except ValueError:
        return None

    authors_raw = meta.get("Authors") or meta.get("authors") or []
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a).strip() for a in authors_raw)
    else:
        authors = str(authors_raw)

    discussions_raw = meta.get("Discussions") or meta.get("discussions") or []
    if isinstance(discussions_raw, list):
        discussions = ", ".join(str(d) for d in discussions_raw[:3])
    else:
        discussions = str(discussions_raw)

    return ProposalRecord(
        id=f"cip-{number}",
        chain="cardano",
        type="cip",
        number=number,
        title=meta.get("Title") or meta.get("title") or "",
        status=meta.get("Status") or meta.get("status") or "",
        category=meta.get("Category") or meta.get("category") or "",
        authors=authors,
        created=str(meta.get("Created") or meta.get("created") or ""),
        requires="",
        description=_extract_abstract(body),
        body=body,
        discussions_to=discussions,
    )


def parse_tezos_tzip(filepath: Path) -> ProposalRecord | None:
    """Parse Tezos TZIP with YAML frontmatter.

    TZIPs use zero-padded tzip field (e.g., "012"), standard YAML fields.
    Hosted on GitLab (gitlab.com/tezos/tzip).
    Note: YAML parses unquoted "012" as octal (=10), so we extract from filename.
    """
    text = filepath.read_text(errors="replace")
    meta, body = _split_yaml_frontmatter(text)
    if not meta:
        return None

    # Extract number from filename (tzip-12.md) to avoid YAML octal parsing
    num_match = re.search(r'tzip-(\d+)', filepath.name)
    if not num_match:
        # Fallback to frontmatter field
        tzip_raw = meta.get("tzip")
        if tzip_raw is None:
            return None
        num_match_str = str(tzip_raw).strip()
        if not num_match_str.isdigit():
            return None
        number = int(num_match_str)
    else:
        number = int(num_match.group(1))

    return ProposalRecord(
        id=f"tzip-{number:03d}",
        chain="tezos",
        type="tzip",
        number=number,
        title=meta.get("title") or "",
        status=meta.get("status") or "",
        category=meta.get("type") or "",
        authors=str(meta.get("author") or ""),
        created=str(meta.get("created") or ""),
        requires=str(meta.get("requires") or ""),
        description=_extract_abstract(body),
        body=body,
        discussions_to=str(meta.get("discussions-to") or ""),
        replaces=str(meta.get("replaces") or ""),
        superseded_by=str(meta.get("superseded-by") or ""),
    )


def parse_sui_sip(filepath: Path) -> ProposalRecord | None:
    """Parse Sui SIP with markdown table metadata.

    Sui SIPs use pipe-delimited table rows at the top (same pattern as
    Polkadot RFCs and Avalanche ACPs). Type is 'sui-sip' to avoid conflict
    with Stacks SIPs.
    """
    text = filepath.read_text(errors="replace")

    # Extract metadata from table rows
    meta: dict[str, str] = {}
    for match in re.finditer(r'\|\s*\*?\*?([^|*]+?)\*?\*?\s*\|\s*(.+?)\s*\|', text):
        key = match.group(1).strip().lower()
        val = match.group(2).strip()
        meta[key] = val

    # Get SIP number from table or filename
    number_raw = meta.get("sip-number", "")
    if not number_raw or not number_raw.strip().isdigit():
        num_match = re.search(r'sip-(\d+)', filepath.name)
        if not num_match:
            return None
        number_raw = num_match.group(1)

    try:
        number = int(number_raw)
    except ValueError:
        return None

    title = meta.get("title", "")
    if not title:
        return None

    # Clean markdown escapes from author field
    authors = meta.get("author", "")
    authors = authors.replace("\\<", "<").replace("\\>", ">")
    authors = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', authors)

    body = text.strip()

    return ProposalRecord(
        id=f"sui-sip-{number}",
        chain="sui",
        type="sui-sip",
        number=number,
        title=title,
        status=meta.get("status", ""),
        category=meta.get("category", meta.get("type", "")),
        authors=authors,
        created=meta.get("created", ""),
        requires=meta.get("requires", ""),
        description=meta.get("description", "") or _extract_abstract(body),
        body=body,
        discussions_to=meta.get("comments-uri", ""),
    )


# --- Source Configuration ---


SOURCES = [
    {
        "name": "EIPs",
        "repo": "https://github.com/ethereum/EIPs.git",
        "branch": "master",
        "glob": "EIPS/eip-*.md",
        "parser": parse_eip,
    },
    {
        "name": "ERCs",
        "repo": "https://github.com/ethereum/ERCs.git",
        "branch": "master",
        "glob": "ERCS/erc-*.md",
        "parser": parse_eip,  # same format as EIPs
    },
    {
        "name": "BIPs",
        "repo": "https://github.com/bitcoin/bips.git",
        "branch": "master",
        "glob": "bip-*",
        "parser": parse_bip,
    },
    {
        "name": "SIMDs",
        "repo": "https://github.com/solana-foundation/solana-improvement-documents.git",
        "branch": "main",
        "glob": "proposals/*.md",
        "parser": parse_simd,
    },
    {
        "name": "Cosmos ADRs",
        "repo": "https://github.com/cosmos/cosmos-sdk.git",
        "branch": "main",
        "glob": "docs/architecture/adr-*.md",
        "parser": parse_cosmos_adr,
        # ADRs have no preamble metadata; need full history for authors+created.
        "keep_history": True,
    },
    {
        "name": "Polkadot RFCs",
        "repo": "https://github.com/polkadot-fellows/RFCs.git",
        "branch": "main",
        "glob": "text/*.md",
        "parser": parse_polkadot_rfc,
    },
    {
        "name": "Stacks SIPs",
        "repo": "https://github.com/stacksgov/sips.git",
        "branch": "main",
        "glob": "sips/sip-*/sip-*.md",
        "parser": parse_stacks_sip,
    },
    {
        "name": "Avalanche ACPs",
        "repo": "https://github.com/avalanche-foundation/ACPs.git",
        "branch": "main",
        "glob": "ACPs/*/README.md",
        "parser": parse_avalanche_acp,
        # ACP preamble has no Created row; need full history.
        "keep_history": True,
    },
    {
        "name": "Cardano CIPs",
        "repo": "https://github.com/cardano-foundation/CIPs.git",
        "branch": "master",
        "glob": "CIP-*/README.md",
        "parser": parse_cardano_cip,
    },
    {
        "name": "Tezos TZIPs",
        "repo": "https://gitlab.com/tezos/tzip.git",
        "branch": "master",
        "glob": "proposals/tzip-*/tzip-*.md",
        "parser": parse_tezos_tzip,
    },
    {
        "name": "Sui SIPs",
        "repo": "https://github.com/sui-foundation/sips.git",
        "branch": "main",
        "glob": "sips/sip-*.md",
        "parser": parse_sui_sip,
    },
]
