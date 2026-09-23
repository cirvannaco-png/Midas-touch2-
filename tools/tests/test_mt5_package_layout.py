from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA"
INCLUDE_RE = re.compile(r'^\\s*#include\\s+"([^"]+)"', re.MULTILINE)


def _read(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _assert_entry_point_include_tree(entry: Path) -> set[Path]:
    assert entry.is_file(), f"missing entry point: {entry}"
    visited: set[Path] = set()
    stack = [entry.resolve()]

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)

        for target in INCLUDE_RE.findall(_read(current)):
            resolved = (current.parent / target).resolve()
            assert resolved.exists(), (
                f'{current.relative_to(ROOT)} includes missing "{target}"'
            )
            try:
                resolved.relative_to(EA.resolve())
            except ValueError as exc:
                raise AssertionError(
                    f'{current.relative_to(ROOT)} include escapes EA/: "{target}"'
                ) from exc
            if resolved.suffix.lower() in {".mq5", ".mqh"}:
                stack.append(resolved)

    return visited


def test_expert_include_tree_is_self_contained():
    visited = _assert_entry_point_include_tree(EA / "MedisTouch_v2.8.mq5")
    assert all(path.is_file() for path in visited)
    assert all(path.suffix.lower() in {".mq5", ".mqh"} for path in visited)


def test_indicator_include_tree_is_self_contained():
    visited = _assert_entry_point_include_tree(
        EA / "MedisTouch_Indicator_v2.8.mq5"
    )
    assert all(path.is_file() for path in visited)


def test_mt5_package_layout_is_unambiguous():
    assert (EA / "MedisTouch_v2.8.mq5").is_file()
    assert (EA / "MedisTouch_Indicator_v2.8.mq5").is_file()
    assert (EA / "includes").is_dir()

    placeholder = ROOT / "mql5" / "Experts" / "MedisTouch"
    assert (placeholder / "README.md").is_file()

    # The repository source of truth is EA/. The mql5/Experts directory is
    # documentation-only; deployment is performed by the staging script.
    assert not list(placeholder.glob("*.mq5"))
    assert not list(placeholder.glob("*.ex5"))


def test_no_compiled_mql_binaries_in_source_tree():
    binaries = [
        p for p in EA.rglob("*")
        if p.is_file() and p.suffix.lower() in {".ex4", ".ex5"}
    ]
    assert binaries == []
