#!/usr/bin/env python3
"""Second README demo — multi-chain contract lookup. Used by demo2.tape (VHS)."""

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
    # First query — single chain.
    out(f"{ORANGE}▸ You{R}     Where's the Uniswap V3 SwapRouter on Base?", pause=1.4)

    out(f"{CYAN}▸ Agent{R}   → resolve_contract({BOLD}\"uniswap\"{R}, chain_id={BOLD}\"8453\"{R})", pause=1.2)

    out("", pause=0.2)
    out(f"{BOLD}Uniswap{R}", pause=0.3)
    out(f"v3 │ {BLUE}Base{R}     │ factory:           {YELLOW}0x33128a8fC17869897dcE68Ed026d694621f6FDfD{R}", pause=0.25)
    out(f"v3 │ {BLUE}Base{R}     │ router:            {YELLOW}0x2626664c2603336E57B271c5C0b26F421741e481{R}", pause=2.0)

    # Second query — cross-chain comparison.
    out("", pause=0.2)
    out(f"{ORANGE}▸ You{R}     And on every chain you know about?", pause=1.3)

    out(f"{CYAN}▸ Agent{R}   → resolve_contract({BOLD}\"uniswap\"{R})", pause=1.0)

    out("", pause=0.2)
    out(f"{BOLD}Uniswap{R}", pause=0.2)
    out(f"v2 │ {BLUE}Ethereum{R} │ router:            {YELLOW}0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D{R}", pause=0.18)
    out(f"v3 │ {BLUE}Ethereum{R} │ router:            {YELLOW}0xE592427A0AEce92De3Edee1F18E0157C05861564{R}", pause=0.18)
    out(f"v3 │ {BLUE}Ethereum{R} │ universal_router:  {YELLOW}0x66a9893cC07D91D95644Aedd05D03f95e1dBA8Af{R}", pause=0.18)
    out(f"v3 │ {BLUE}Optimism{R} │ router:            {YELLOW}0xE592427A0AEce92De3Edee1F18E0157C05861564{R}", pause=0.18)
    out(f"v3 │ {BLUE}Polygon{R}  │ router:            {YELLOW}0xE592427A0AEce92De3Edee1F18E0157C05861564{R}", pause=0.18)
    out(f"v3 │ {BLUE}Arbitrum{R} │ router:            {YELLOW}0xE592427A0AEce92De3Edee1F18E0157C05861564{R}", pause=0.18)
    out(f"v3 │ {BLUE}Base{R}     │ router:            {YELLOW}0x2626664c2603336E57B271c5C0b26F421741e481{R}  {DIM}← fresh deploy{R}", pause=2.8)

    out("", pause=0.2)
    out(f"{DIM}19 protocols · 6 EVM chains · canonical addresses, no etherscan tabs.{R}", pause=2.5)


if __name__ == "__main__":
    main()
