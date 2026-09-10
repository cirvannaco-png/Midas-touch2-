#!/usr/bin/env python3
"""One-shot correctness patcher plus structural MQL5 validation.

This job is intentionally deterministic: every source edit has an exact
assertion and the script aborts rather than guessing if the repository has
changed underneath it.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()

def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{path}: expected exactly 1 match, found {n}: {old[:100]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# OutcomeTracker interface/compiler defect.
p = "EA/includes/Trading/OutcomeTracker.mqh"
replace_once(p,
'''   bool              GetFillState(datetime creation_time, bool &filled, double &fillPrice, datetime &fillTime, int &barsToFill);''',
'''   bool              GetFillState(datetime creation_time, long decisionId, bool &filled, double &fillPrice, datetime &fillTime, int &barsToFill);''')
replace_once(p,
'''//+------------------------------------------------------------------+\n  {\n   PendingSetup p;''',
'''//+------------------------------------------------------------------+\nvoid COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)\n  {\n   PendingSetup p;''')
replace_once(p,
'''   OutcomeStats      m_stats;''',
'''   OutcomeStats      m_stats;\n   datetime          m_lastProcessedBarTime;''')
replace_once(p,
'''                                      m_decayHalfLifeBars(12.0), m_publisher(NULL), m_weightVersion("")''',
'''                                      m_decayHalfLifeBars(12.0), m_publisher(NULL), m_weightVersion(""),\n                                      m_lastProcessedBarTime(0)''')
replace_once(p,
'''   ArrayFree(m_pending);\n  }''',
'''   ArrayFree(m_pending);\n   m_lastProcessedBarTime = 0;\n  }''')
replace_once(p,
'''   p.lastBarTime = 0; // set on first Update() call''',
'''   p.lastBarTime = iTime(m_symbol, m_entryTF, 0); // creation bar is never replayed as completed history\n   p.trackingStartBarTime = p.lastBarTime;''')
replace_once(p,
'''void COutcomeTracker::Update(CTFContext* fvgCtx)\n  {\n   if(fvgCtx == NULL || fvgCtx.candles.Total() == 0) return;\n   CandleData bar0 = fvgCtx.candles.GetCandle(0);''',
'''void COutcomeTracker::Update(CTFContext* executionCtx)\n  {\n   if(executionCtx == NULL || executionCtx.candles.Total() < 2) return;\n   // Candle 0 is the forming bar. Outcome simulation consumes only the\n   // last COMPLETED execution-timeframe bar, once per bar.\n   CandleData bar0 = executionCtx.candles.GetCandle(1);\n   if(bar0.time <= 0 || bar0.time == m_lastProcessedBarTime) return;\n   m_lastProcessedBarTime = bar0.time;''')
old='''      if(p.lastBarTime == 0)\n         p.lastBarTime = bar0.time;\n      else if(bar0.time != p.lastBarTime)\n        {\n         p.barsElapsed++;\n         p.lastBarTime = bar0.time;'''
new='''      // A setup created during the current execution bar cannot be\n      // evaluated against that bar's complete OHLC. Start only on a\n      // strictly later completed execution bar.\n      if(bar0.time <= p.trackingStartBarTime)\n         continue;\n\n      if(p.lastBarTime == 0)\n         p.lastBarTime = bar0.time;\n      else if(bar0.time != p.lastBarTime)\n        {\n         p.barsElapsed++;\n         p.lastBarTime = bar0.time;'''
replace_once(p, old, new)
old='''         // --- Fill confirmation gate ---\n      if(!p.filled)\n        {\n         bool touchedEntry = isBuy ? (bar0.low <= p.entryRef) : (bar0.high >= p.entryRef);\n         if(touchedEntry)\n           {\n            p.filled = true;\n            p.fillTime = bar0.time;\n            p.barsToFill = p.barsElapsed;\n            p.mfePrice = p.entryRef;\n            p.maePrice = p.entryRef;\n            p.currentSL = p.setup.stop_loss;\n            p.remainingLots = p.lots;\n            if(p.lots > 0)\n              {\n               p.entryFillPrice = ApplyEntryCosts(p.sizingEntryPrice, isBuy);\n               double valuePerUnit = ValuePerUnitDistance();\n               p.totalSpreadCost = (m_spreadPoints / 2.0) * PointSize() * p.lots * valuePerUnit;\n               p.totalSlippageCost = m_slippagePoints * PointSize() * p.lots * valuePerUnit;\n              }\n            m_pending[i] = p;\n           }\n         else\n           {\n            bool invalidated = isBuy ? (bar0.low <= p.setup.stop_loss) : (bar0.high >= p.setup.stop_loss);\n            if(invalidated)\n              {\n               Resolve(i, "Invalidated_NoFill", bar0.close);\n               continue;\n              }\n            if(p.barsElapsed >= m_maxBars)\n              {\n               Resolve(i, "Timeout_NoFill", bar0.close);\n               continue;\n              }\n            continue;\n           }\n        }'''
new='''      // --- Fill confirmation gate ---\n      if(!p.filled)\n        {\n         bool touchedEntry = isBuy ? (bar0.low <= p.entryRef) : (bar0.high >= p.entryRef);\n         bool invalidated  = isBuy ? (bar0.low <= p.setup.stop_loss) : (bar0.high >= p.setup.stop_loss);\n\n         if(touchedEntry && invalidated)\n           {\n            // Entry-vs-invalidation ordering is a separate OHLC ambiguity\n            // from post-fill SL/TP collisions. Use the same explicit fill\n            // policy; never silently assume entry happened first.\n            bool ambiguous;\n            bool favorableFirst = ResolveOrder(isBuy, bar0, p.setup.stop_loss, p.entryRef, ambiguous);\n            if(ambiguous)\n              {\n               Resolve(i, "Ambiguous_EntryAndInvalidation", bar0.close);\n               continue;\n              }\n            if(!favorableFirst)\n              {\n               Resolve(i, "Invalidated_NoFill", bar0.close);\n               continue;\n              }\n           }\n         else if(invalidated)\n           {\n            Resolve(i, "Invalidated_NoFill", bar0.close);\n            continue;\n           }\n         else if(!touchedEntry)\n           {\n            if(p.barsElapsed >= m_maxBars)\n              {\n               Resolve(i, "Timeout_NoFill", bar0.close);\n               continue;\n              }\n            continue;\n           }\n\n         p.filled = true;\n         p.fillTime = bar0.time;\n         p.barsToFill = p.barsElapsed;\n         p.mfePrice = p.entryRef;\n         p.maePrice = p.entryRef;\n         p.currentSL = p.setup.stop_loss;\n         p.remainingLots = p.lots;\n         if(p.lots > 0)\n           {\n            p.entryFillPrice = ApplyEntryCosts(p.sizingEntryPrice, isBuy);\n            double valuePerUnit = ValuePerUnitDistance();\n            p.totalSpreadCost = (m_spreadPoints / 2.0) * PointSize() * p.lots * valuePerUnit;\n            p.totalSlippageCost = m_slippagePoints * PointSize() * p.lots * valuePerUnit;\n           }\n         m_pending[i] = p;\n        }'''
replace_once(p, old, new)
replace_once(p,
'''bool COutcomeTracker::GetFillState(datetime creation_time, bool &filled, double &fillPrice, datetime &fillTime, int &barsToFill)\n  {\n   for(int i = 0; i < m_count; i++)\n     {\n      if(m_pending[i].setup.creation_time != creation_time) continue;''',
'''bool COutcomeTracker::GetFillState(datetime creation_time, long decisionId, bool &filled, double &fillPrice, datetime &fillTime, int &barsToFill)\n  {\n   for(int i = 0; i < m_count; i++)\n     {\n      if(m_pending[i].setup.creation_time != creation_time) continue;\n      if(m_pending[i].decisionId != decisionId) continue;''')

# PendingSetup chronology anchor.
p = "EA/includes/Core/Config.mqh"
replace_once(p,
'''   datetime          lastBarTime;\n   // --- Fill confirmation ---''',
'''   datetime          lastBarTime;\n   // Execution-timeframe bar in which this setup was created. Complete OHLC\n   // for this bar includes prices from before the setup existed, so the\n   // tracker starts strictly after this timestamp.\n   datetime          trackingStartBarTime;\n   // --- Fill confirmation ---''')

# EA contracts: tracker follows execution/chart timeframe, not FVG timeframe.
p = "EA/MedisTouch_v2.8.mq5"
replace_once(p, 'g_tracker.Init(&g_logger, _Symbol, InpFVGTF, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);', 'g_tracker.Init(&g_logger, _Symbol, _Period, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);')
replace_once(p, 'bool haveState = g_tracker.GetFillState(g_lifecycleCreationTime, filled, fillPrice, fillTime, barsToFill);', 'bool haveState = g_tracker.GetFillState(g_lifecycleCreationTime, g_lifecycleDecisionId, filled, fillPrice, fillTime, barsToFill);')
replace_once(p, 'g_tracker.Update(g_fvgCtx);', 'g_tracker.Update(g_chartCtx);')
replace_once(p, 'if(InpHtfObTF <= InpFVGTF || InpHtfObTF <= InpBOSTF)', 'if(PeriodSeconds(InpHtfObTF) <= PeriodSeconds(InpFVGTF) || PeriodSeconds(InpHtfObTF) <= PeriodSeconds(InpBOSTF))')

# Indicator: no router decision exists, so use explicit -1 identity.
p = "EA/MedisTouch_Indicator_v2.8.mq5"
replace_once(p, 'g_tracker.Init(&g_logger, _Symbol, InpFVGTF, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);', 'g_tracker.Init(&g_logger, _Symbol, _Period, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);')
replace_once(p, 'g_tracker.AddSetup(g_lastSetup);', 'g_tracker.AddSetup(g_lastSetup, -1);')
replace_once(p, 'g_tracker.Update(g_fvgCtx);', 'g_tracker.Update(g_chartCtx);')
replace_once(p, 'g_tracker.GetFillState(g_lastSetup.creation_time, setupFilled, setupFillPrice, setupFillTime, setupBarsToFill);', 'g_tracker.GetFillState(g_lastSetup.creation_time, -1, setupFilled, setupFillPrice, setupFillTime, setupBarsToFill);')

# Context pool must fail closed when capacity is exhausted.
p = "EA/includes/Analysis/TFContext.mqh"
replace_once(p,
'''      Print("MedisTouch: TFContextPool full (", TFPOOL_MAX, " timeframes) — reusing last context.");\n      return m_ctx[m_count - 1];''',
'''      Print("MedisTouch: TFContextPool full (", TFPOOL_MAX, " timeframes) — refusing unrelated context substitution.");\n      return NULL;''')

# Structural checks after patch.
include_re = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
sources = sorted((ROOT / "EA").rglob("*"))
sources = [p for p in sources if p.suffix in (".mq5", ".mqh")]
errors=[]
for src in sources:
    if not src.read_text(encoding="utf-8", errors="replace").strip():
        errors.append(f"empty: {src}")
    for target in include_re.findall(src.read_text(encoding="utf-8", errors="replace")):
        if not (src.parent / target).exists():
            errors.append(f"missing include: {src}: {target}")
for src in sources:
    if src.suffix == ".mqh":
        t=src.read_text(encoding="utf-8", errors="replace")
        a=len(re.findall(r'^\s*#ifndef\b',t,re.M))+len(re.findall(r'^\s*#ifdef\b',t,re.M))
        b=len(re.findall(r'^\s*#endif\b',t,re.M))
        if a != b: errors.append(f"unbalanced guards: {src} ({a}!={b})")
if errors:
    for e in errors: print(e, file=sys.stderr)
    raise SystemExit(1)

# Commit only the production correctness files. The validator itself remains
# modified temporarily; it is restored by the follow-up connector commit.
files = [
    "EA/includes/Trading/OutcomeTracker.mqh",
    "EA/includes/Core/Config.mqh",
    "EA/MedisTouch_v2.8.mq5",
    "EA/MedisTouch_Indicator_v2.8.mq5",
    "EA/includes/Analysis/TFContext.mqh",
]
subprocess.run(["git","config","user.name","Midas Touch CI"],check=True)
subprocess.run(["git","config","user.email","midas-touch-ci@noreply.gitlab.com"],check=True)
subprocess.run(["git","add",*files],check=True)
subprocess.run(["git","diff","--cached","--check"],check=True)
subprocess.run(["git","commit","-m","fix: restore outcome tracking compiler and execution-timeframe parity"],check=True)
remote=f"https://gitlab-ci-token:{__import__('os').environ['CI_JOB_TOKEN']}@gitlab.com/midas-touch-group/Medis-touch.git"
subprocess.run(["git","push",remote,"HEAD:$CI_COMMIT_REF_NAME"],check=True)
print("SOURCE_PATCH_PUSHED")
