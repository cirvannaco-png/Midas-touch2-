from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "EA" / "includes" / "Recovery" / "RecoveryEngine.mqh"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTrackerLive.mqh"


def test_recovery_comment_identity_is_validated_before_integer_conversion():
    source = RECOVERY.read_text(encoding="utf-8")
    assert "bool CRecoveryEngine::IsDecimalDigits(const string value)" in source

    start = source.index("bool CRecoveryEngine::ParseTradeIdentity")
    end = source.index("bool CRecoveryEngine::ParseDecisionId", start)
    parser = source[start:end]

    # MQL's numeric conversion accepts some malformed prefixes. Identity text
    # must be ASCII decimal digits and canonical before it can select a trade.
    assert parser.index("IsDecimalDigits(legPart)") < parser.index("StringToInteger(legPart)")
    assert parser.index("IsDecimalDigits(payload)") < parser.index("StringToInteger(payload)")
    assert "IntegerToString(parsedLeg)!=legPart" in parser
    assert "IntegerToString(idOut)!=payload" in parser
    assert "parsedLeg>2147483647" in parser
    assert "idOut<=0" in parser



def test_history_rebuild_rejects_malformed_identity_leg_suffixes():
    source = TRACKER.read_text(encoding="utf-8")
    assert "bool HistoryIdentityDigits(const string value)" in source
    start = source.index("bool ParseHistoryDecisionComment")
    end = source.index("bool HistoryDealDecisionId", start)
    parser = source[start:end]

    # Never truncate an arbitrary colon suffix into an otherwise valid decision
    # ID: it could attribute a broker deal to the wrong trade after restart.
    assert parser.index('StringFind(payload,":L")') < parser.index("StringToInteger(legPart)")
    assert parser.index("HistoryIdentityDigits(legPart)") < parser.index("StringToInteger(legPart)")
    assert 'StringFind(payload,":")>=0' in parser
    assert "IntegerToString(leg)!=legPart" in parser
    assert parser.index("HistoryIdentityDigits(payload)") < parser.index("StringToInteger(payload)")
    assert "IntegerToString(decisionId)!=payload" in parser
