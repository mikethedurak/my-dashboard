from __future__ import annotations

import sys
from pathlib import Path

from one_piece_missing import (
    run_all,
    run_big_bang,
    run_geek_haven,
    run_knightly,
    run_marvellous,
    run_toad,
    run_tanuki,
)


RUNNERS = {
    "all": run_all,
    "bigbang": run_big_bang,
    "bigbangshop": run_big_bang,
    "geek": run_geek_haven,
    "geekhaven": run_geek_haven,
    "knightly": run_knightly,
    "knightlygaming": run_knightly,
    "marvellous": run_marvellous,
    "marvelloushobbies": run_marvellous,
    "toad": run_toad,
    "toadtrader": run_toad,
    "toadtradertcg": run_toad,
    "tanuki": run_tanuki,
    "tanukitrader": run_tanuki,
}


def main() -> int:
    store = sys.argv[1].lower().replace("-", "").replace("_", "") if len(sys.argv) > 1 else "all"
    runner = RUNNERS.get(store)
    if runner is None:
        choices = "all, bigbang, geekhaven, knightly, marvellous, toad, tanuki"
        print(f"Unknown store {sys.argv[1]!r}. Use one of: {choices}", file=sys.stderr)
        return 2

    runner()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
