from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_packaged_version_matches_both_mql5_artifacts():
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert expected == "2.81"

    sources = (
        ROOT / "EA" / "MedisTouch_v2.8.mq5",
        ROOT / "EA" / "MedisTouch_Indicator_v2.8.mq5",
    )
    for source in sources:
        match = re.search(
            r'^\s*#property\s+version\s+"([^"]+)"\s*$',
            source.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        assert match is not None, f"Missing #property version in {source}"
        assert match.group(1) == expected, (
            f"{source.relative_to(ROOT)} declares {match.group(1)!r}; "
            f"VERSION declares {expected!r}"
        )


def test_legacy_filename_contract_is_explicit():
    # These paths are consumed by MT5 packaging, so keep them stable until an
    # atomic rename updates every staging/install/CI reference.
    assert (ROOT / "EA" / "MedisTouch_v2.8.mq5").is_file()
    assert (ROOT / "EA" / "MedisTouch_Indicator_v2.8.mq5").is_file()
