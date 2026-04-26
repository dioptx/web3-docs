#!/usr/bin/env python3
"""Third README demo — fork lookup ("What's in Cancun?"). Used by demo3.tape."""

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
MAGENTA = "\033[35m"


def out(s: str = "", *, end: str = "\n", pause: float = 0.0) -> None:
    sys.stdout.write(s + end)
    sys.stdout.flush()
    if pause:
        time.sleep(pause)


def main() -> None:
    out(f"{ORANGE}▸ You{R}     What shipped with Cancun?", pause=1.4)

    out(f"{CYAN}▸ Agent{R}   → list_fork_proposals({BOLD}\"Cancun\"{R})", pause=1.4)

    out("", pause=0.2)
    out(f"{BOLD}{YELLOW}Cancun{R} — activated 2024-03-13 · block 19,426,587", pause=0.4)
    out("", pause=0.2)
    out(f"eip-1153  │ Transient storage opcodes                      │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-4788  │ Beacon block root in the EVM                   │ {GREEN}Final{R}", pause=0.18)
    out(f"{BOLD}eip-4844  │ Shard Blob Transactions {DIM}(proto-danksharding){R}{BOLD}    │ {GREEN}Final{R}", pause=0.18)
    out(f"{R}eip-5656  │ MCOPY — Memory copying instruction             │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-6780  │ SELFDESTRUCT only in same transaction          │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-7044  │ Perpetually valid signed voluntary exits       │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-7045  │ Increased max attestation inclusion slot       │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-7514  │ Add max epoch churn limit                      │ {GREEN}Final{R}", pause=0.18)
    out(f"eip-7516  │ BLOBBASEFEE opcode                             │ {GREEN}Final{R}", pause=2.5)

    # Now drill into eip-4844.
    out("", pause=0.3)
    out(f"{ORANGE}▸ You{R}     Pull the fee-market section of 4844.", pause=1.5)
    out(f"{CYAN}▸ Agent{R}   → query_protocol_docs({BOLD}\"eip-4844\"{R}, query={BOLD}\"fee market\"{R})", pause=1.5)

    out("", pause=0.2)
    out(f"{BOLD}{CYAN}eip-4844{R} — Shard Blob Transactions", pause=0.3)
    out(f"chain: {BLUE}ethereum{R}   status: {GREEN}Final{R}   fork: {YELLOW}Cancun{R}   activated: 2024-03-13", pause=0.4)
    out(f"{DIM}──────────────────────────────────────────────────────────{R}", pause=0.3)
    out("Each blob carries a separate, exponentially-priced gas market", pause=0.4)
    out("(`blob_gas_price`) decoupled from execution gas. Targets 3 blobs", pause=0.4)
    out("per block, max 6. Price doubles every ~8 blocks above target.", pause=2.5)

    out("", pause=0.2)
    out(f"{DIM}One tool call: fork → 9 EIPs. Two tool calls: drilled into the spec.{R}", pause=2.5)


if __name__ == "__main__":
    main()
