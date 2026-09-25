from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "EA" / "includes" / "Core" / "Config.mqh"
CANDLES = ROOT / "EA" / "includes" / "Core" / "CandleData.mqh"
VALUE_AREA = ROOT / "EA" / "includes" / "SmartMoney" / "ValueAreaEngine.mqh"
SCORING = ROOT / "EA" / "includes" / "Analysis" / "Scoring.mqh"
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
INDICATOR = ROOT / "EA" / "MedisTouch_Indicator_v2.8.mq5"
LOGGER = ROOT / "EA" / "includes" / "Core" / "SignalLogger.mqh"
DASHBOARD = ROOT / "EA" / "includes" / "UI" / "Dashboard.mqh"


def test_candle_model_retains_real_volume():
    assert "long real_volume;" in CONFIG.read_text()
    assert "m_data[i].real_volume = rates[i].real_volume;" in CANDLES.read_text()


def test_value_profile_has_trade_tick_and_bar_fallback_hierarchy():
    t = VALUE_AREA.read_text()
    assert "CopyTicksRange" in t
    assert "COPY_TICKS_TRADE" in t
    assert "tick.volume_real" in t
    assert "tick.volume" in t
    assert "cd.real_volume" in t
    assert "cd.tick_volume" in t
    assert "VA_SOURCE_REAL_TRADE_TICKS" in t
    assert "VA_SOURCE_BROKER_TRADE_TICKS" in t
    assert "VA_SOURCE_REAL_VOLUME_BARS" in t
    assert "VA_SOURCE_TICK_VOLUME_BARS" in t


def test_value_profile_is_cross_asset_and_does_not_fake_exchange_volume():
    t = VALUE_AREA.read_text()
    assert "symbol-agnostic" in t
    assert "never labels a bar approximation as exchange trade volume" in t
    assert "Low-quality tick-volume proxies fail open" in t


def test_value_profile_tracks_acceptance_rejection_and_poc_migration():
    t = VALUE_AREA.read_text()
    assert "VA_STATE_ACCEPTED_ABOVE" in t
    assert "VA_STATE_ACCEPTED_BELOW" in t
    assert "VA_STATE_REJECTED_ABOVE" in t
    assert "VA_STATE_REJECTED_BELOW" in t
    assert "m_pocMigrationATR" in t
    assert "POCMigrationATR()" in t


def test_default_hard_gate_is_contradiction_based():
    s = SCORING.read_text()
    ea = EA.read_text()
    ind = INDICATOR.read_text()
    assert "m_blockValueAreaContradictions(true)" in s
    assert "HardConflict(forBuy, price)" in s
    assert "input bool InpBlockValueAreaContradictions=true;" in ea
    assert "input bool   InpBlockValueAreaContradictions = true;" in ind
    assert "ConfigureValueArea(InpRequireValueAreaLocation,InpBlockValueAreaContradictions);" in ea
    assert "ConfigureValueArea(InpRequireValueAreaLocation, InpBlockValueAreaContradictions);" in ind


def test_legacy_strict_location_gate_remains_explicitly_optional():
    assert "input bool InpRequireValueAreaLocation=false;" in EA.read_text()
    assert "input bool   InpRequireValueAreaLocation = false;" in INDICATOR.read_text()


def test_value_area_telemetry_is_persisted_and_visible():
    c = CONFIG.read_text()
    l = LOGGER.read_text()
    d = DASHBOARD.read_text()
    for token in [
        "ENUM_VALUE_PROFILE_SOURCE value_profile_source",
        "ENUM_VALUE_PROFILE_STATE value_profile_state",
        "double va_poc_migration_atr",
        "double va_source_quality",
        "double va_score",
        "bool value_area_contradiction",
    ]:
        assert token in c
    assert "VAProfileSource" in l
    assert "VAProfileState" in l
    assert "VAPOCMigrationATR" in l
    assert "VASourceQuality" in l
    assert "VAScore" in l
    assert "VAContradiction" in l
    assert "HARD CONFLICT" in d


def test_low_quality_profiles_cannot_trigger_hard_conflict():
    assert "m_sourceQuality < 0.70" in VALUE_AREA.read_text()


def test_successful_value_area_compute_restores_valid_state():
    t = VALUE_AREA.read_text()
    assert "m_havePreviousPOC = true;\\n   m_valid = true;" in t
