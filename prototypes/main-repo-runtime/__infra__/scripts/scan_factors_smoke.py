from __future__ import annotations

import argparse
from pathlib import Path

from evozeus.factors.packs import FactorPackRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-root", default=str(PROJECT_ROOT / "__infra__" / "factor_packs"))
    args = parser.parse_args()

    packs = FactorPackRepository(Path(args.pack_root)).discover()
    factor_ids = [pack.manifest.id for pack in packs]
    intro_count = sum(1 for pack in packs if pack.introduction.summary)
    assert len(packs) >= 3
    assert "default.tool_failure" in factor_ids
    print(f"scan factors ok: count={len(packs)} intro_count={intro_count} ids={','.join(factor_ids)}")


if __name__ == "__main__":
    main()
