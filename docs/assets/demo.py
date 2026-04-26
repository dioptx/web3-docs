#!/usr/bin/env python3
"""Pretty terminal demo for the README hero GIF. Used by demo.tape (VHS)."""

from __future__ import annotations
import sys
import time

R = "\033[0m"
DIM = "\033[90m"
BOLD = "\033[1m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
ORANGE = "\033[38;5;215m"


def out(s: str = "", *, end: str = "\n", pause: float = 0.0) -> None:
    sys.stdout.write(s + end)
    sys.stdout.flush()
    if pause:
        time.sleep(pause)


def main() -> None:
    out(f"{DIM}$ claude mcp add web3-docs -- uvx --from git+https://github.com/dioptx/web3-docs web3-docs-mcp{R}", pause=0.6)
    out(f"{GREEN}✔{R}  Added MCP server {BOLD}web3-docs{R} {DIM}(stdio){R}", pause=1.2)

    out("", pause=0.3)
    out(f"{ORANGE}▸ You{R}     What fork shipped PUSH0 and why?", pause=1.4)

    out(f"{CYAN}▸ Claude{R}  → resolve_proposal({BOLD}\"PUSH0\"{R})", pause=0.5)
    out(f"           → query_protocol_docs({BOLD}\"eip-3855\"{R}, query={BOLD}\"rationale\"{R})", pause=1.6)

    out("", pause=0.2)
    out(f"{BOLD}{CYAN}eip-3855{R} — PUSH0 instruction", pause=0.3)
    out(f"chain: {BLUE}ethereum{R}   status: {GREEN}Final{R}   fork: {YELLOW}Shanghai{R} (2023-04-12)", pause=0.3)
    out(f"{DIM}──────────────────────────────────────────────{R}", pause=0.3)
    out("PUSH1 0x00 currently accounts for ~11% of all", pause=0.4)
    out("deployed bytecode. A dedicated PUSH0 opcode shrinks", pause=0.4)
    out("contracts and saves 2 gas/byte + 3 gas per call.", pause=2.5)

    out("", pause=0.2)
    out(f"{DIM}11 spec sources · 1,767 proposals · 19 contract registries{R}", pause=2.5)


if __name__ == "__main__":
    main()
