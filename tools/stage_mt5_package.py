#!/usr/bin/env python3
"""Stage the MedisTouch MQL5 sources into an MT5 data-folder layout.

The repository keeps development sources under EA/. MetaEditor compiles
relative includes from the directory where the .mq5 entry point lives.
This tool creates the exact runtime layout without copying tests or binaries.

Example (PowerShell):
  python tools/stage_mt5_package.py --destination "C:\\...\\MQL5\\Experts\\MedisTouch"

Indicator (optional):
  python tools/stage_mt5_package.py --destination "C:\\...\\MQL5\\Experts\\MedisTouch" \
    --indicator-destination "C:\\...\\MQL5\\Indicators\\MedisTouch"
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

INCLUDE_RE = re.compile(r'^\\s*#include\\s+"([^"]+)"', re.MULTILINE)
LOCAL_SOURCE_SUFFIXES = {".mq5", ".mqh"}


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def validate_local_includes(root: Path, entry_points: list[Path]) -> None:
    errors: list[str] = []
    visited: set[Path] = set()
    stack = list(entry_points)

    while stack:
        src = stack.pop().resolve()
        if src in visited:
            continue
        visited.add(src)

        if not src.exists():
            errors.append(f"missing source: {src}")
            continue

        for target in INCLUDE_RE.findall(read_text(src)):
            resolved = (src.parent / target).resolve()

            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f'{src.relative_to(root)}: #include "{target}" escapes source root'
                )
                continue

            if not resolved.exists():
                errors.append(
                    f'{src.relative_to(root)}: #include "{target}" does not exist'
                )
                continue

            if resolved.suffix.lower() in LOCAL_SOURCE_SUFFIXES:
                stack.append(resolved)

    if errors:
        raise RuntimeError(
            "MQL5 include validation failed:\n- " + "\n- ".join(errors)
        )


def copy_tree(source: Path, destination: Path) -> int:
    copied = 0
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in LOCAL_SOURCE_SUFFIXES:
            continue
        rel = path.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        default="EA",
        help="Repository EA source directory (default: EA)",
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="MT5 MQL5/Experts/MedisTouch directory",
    )
    parser.add_argument(
        "--indicator-destination",
        help="Optional MT5 MQL5/Indicators/MedisTouch directory",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source_root = (repo_root / args.source_root).resolve()
    if not source_root.is_dir():
        print(f"error: source root does not exist: {source_root}", file=sys.stderr)
        return 1

    expert = source_root / "MedisTouch_v2.8.mq5"
    indicator = source_root / "MedisTouch_Indicator_v2.8.mq5"
    includes = source_root / "includes"

    if not expert.is_file():
        print(f"error: missing EA entry point: {expert}", file=sys.stderr)
        return 1
    if not includes.is_dir():
        print(f"error: missing include directory: {includes}", file=sys.stderr)
        return 1
    if args.indicator_destination and not indicator.is_file():
        print(f"error: missing indicator entry point: {indicator}", file=sys.stderr)
        return 1

    validate_local_includes(
        source_root,
        [expert] + ([indicator] if args.indicator_destination else []),
    )

    expert_destination = Path(args.destination).expanduser().resolve()
    expert_destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(expert, expert_destination / expert.name)
    copied = copy_tree(includes, expert_destination / "includes")

    if args.indicator_destination:
        indicator_destination = Path(args.indicator_destination).expanduser().resolve()
        indicator_destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(indicator, indicator_destination / indicator.name)
        copy_tree(includes, indicator_destination / "includes")

    print(f"Staged {expert.name} + {copied} include source file(s).")
    print(f"Expert location: {expert_destination}")
    if args.indicator_destination:
        print(f"Indicator location: {Path(args.indicator_destination).expanduser().resolve()}")
    print("Include validation: passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
