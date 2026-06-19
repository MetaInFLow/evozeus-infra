from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

from evozeus_runtime.sessions.schema import SessionEnvelope
from evozeus_runtime.factors.base import FactorContext
from evozeus_runtime.factors.packs import load_factor_from_pack, load_factor_pack


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m evozeus.factors.subprocess_worker <factor-pack-root>")

    pack_root = Path(sys.argv[1])
    payload = json.loads(sys.stdin.read())
    pack = load_factor_pack(pack_root)
    context = FactorContext(
        session=SessionEnvelope.model_validate(payload["session"]),
        config=payload.get("config") or {},
    )

    with contextlib.redirect_stdout(sys.stderr):
        factor = load_factor_from_pack(pack)
        result = factor.execute(context)

    sys.stdout.write(result.model_dump_json())


if __name__ == "__main__":
    main()
