"""CLI:  python -m solar_relay --config config.yaml [--once] [--dry-run] [--list-adapters]"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .config import OutputConfig, RelayConfig
from .registry import ADAPTERS, OUTPUTS
from .scheduler import Relay


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="solar-relay", description="multi-brand PV / hybrid inverter relay")
    p.add_argument("--config", "-c", default="config.yaml")
    p.add_argument("--once", action="store_true", help="poll every device once, flush outputs, exit")
    p.add_argument("--dry-run", action="store_true", help="ignore configured outputs, print readings to console")
    p.add_argument("--list-adapters", action="store_true")
    p.add_argument("--log-level", default=None)
    args = p.parse_args(argv)

    if args.list_adapters:
        print("adapters:")
        for k, v in sorted(ADAPTERS.items()):
            print(f"  {k:20s} {v}")
        print("outputs:")
        for k, v in sorted(OUTPUTS.items()):
            print(f"  {k:20s} {v}")
        return 0

    cfg = RelayConfig.load(args.config)
    logging.basicConfig(
        level=(args.log_level or cfg.log_level).upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    if args.dry_run:
        cfg.outputs = [OutputConfig(type="console")]

    relay = Relay(cfg).build()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, relay.stop)
            except NotImplementedError:  # Windows
                pass
        await relay.run(once=args.once)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
