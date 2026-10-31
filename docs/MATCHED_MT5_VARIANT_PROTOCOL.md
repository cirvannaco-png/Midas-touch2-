# Matched MT5 Variant Comparison Protocol

## Purpose and safety boundary

Use this protocol to compare an original dual-lane setup against stricter dual-lane filters and a strict-only setup on the same instrument, time range, tick/data snapshot, terminal build, EA revision, spread/commission/slippage assumptions, fill policy, initial balance, leverage, and risk sizing.

The comparator consumes MT5 Strategy Tester artifacts that already exist. It does not run the Strategy Tester, infer settings from a report, create missing data, or claim a strategy is profitable. It hashes the exact .set, report, deal-history, open-position and dataset files so the comparison is reproducible. The run manifest must state the observed settings copied from the actual tester configuration/report. A hash establishes file identity; it does not independently prove the manifest's declarations were truthful.

This research tool does not promote a candidate. A green Python/MetaEditor pipeline is an engineering check, not evidence of expectancy or live readiness. Do not merge strategy-affecting settings or activate the EA solely because the comparison JSON is successfully generated.

## Required variant matrix

Provide exactly three independently run Strategy Tester artifacts:

- baseline_dual_lane: the original dual-lane logic and its frozen input preset.
- strict_filter_dual_lane: the same two lanes with the predeclared stricter qualification filters.
- strict_only: strict qualifying lane only; no fallback entry.

A run with zero qualifying positions is valid evidence of zero completed positions; it is not a reason to lower a filter or invent an entry. Each exported deal CSV must include a lane, risk_lane, or entry_lane field with a non-empty lane label on every completed position. The comparator rejects completed in-window positions without a lane label so lane-level results cannot be mistaken for verified attribution.

## Test and OOS windows

The declared period is [period_start, period_end). The locked OOS interval is [locked_oos_start, locked_oos_end) and must be contained in that period. Set period_end later than locked_oos_end when needed to let positions opened during OOS mature. Only trades opened within locked OOS and fully closed before locked_oos_end enter locked-OOS metrics. Positions whose exits occur at or after the OOS boundary are censored from OOS scores and shown separately; a still-open/incomplete trade must never be converted into a win, loss or scratch to complete the table.

Keep warm-up outside the declared comparison period, freeze the OOS window before looking at candidate results, and do not tune filters from locked-OOS outcomes. For strict interpretation, run an additional future untouched holdout after a candidate and thresholds have been frozen.

## Capturing artifacts

For each variant, export and retain:

1. The actual MT5 .set inputs file used for that run (not a subsequently edited preset).
2. The MT5 Strategy Tester report (HTML is acceptable).
3. The deal-history CSV with position identifier, time, deal-entry, volume, profit, commission, swap, fee, initial risk amount where available, and explicit lane attribution.
4. An open-position ID CSV from that tester result; if none remain open, a header-only CSV containing position_id is sufficient.
5. One shared historical dataset/tick-data artifact or immutable data archive whose SHA-256 is recorded.

Use identical test context across all three runs and record the actual account currency, leverage, EA source commit SHA, EA build, terminal build, selected broker/data vendor, spread model, commission per lot, slippage assumption, fill policy, starting balance and risk percent. Never copy the example cost values as if they described the selected broker. When a real-tick spread model is used, spread_points may be null; do not substitute an invented fixed-spread number.

## Manifest and command

Create a manifest file beside the artifacts. All artifact paths below are resolved relative to that manifest unless they are absolute paths.

Example shape (replace every sample value with actual exported values and real SHA-256s):

    {
      "schema_version": 1,
      "experiment_id": "xauusd-m5-matched-2025",
      "dataset_path": "artifacts/tick-data.zip",
      "test_context": {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2026-01-01T00:00:00Z",
        "locked_oos_start": "2025-10-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "dataset_sha256": "<sha256 of tick-data.zip>",
        "ea_source_sha": "<40- or 64-character commit SHA>",
        "ea_build": "<actual EA build>",
        "terminal_build": "<actual MT5 terminal build>",
        "data_vendor": "selected-broker-feed",
        "spread_model": "real_ticks",
        "spread_points": null,
        "commission_per_lot": 7.0,
        "slippage_points": 2.0,
        "fill_policy": "<actual fill policy>",
        "initial_balance": 10000.0,
        "risk_percent": 0.5,
        "account_currency": "USD",
        "leverage": "1:500"
      },
      "variants": [
        {
          "role": "baseline_dual_lane",
          "run_id": "<unique tester run identifier>",
          "observed_context": { "...": "repeat all test_context keys and values" },
          "parameters": { "InpRiskPercent": 0.5, "..." : "..." },
          "input_preset": "artifacts/baseline.set",
          "report_path": "artifacts/baseline.html",
          "deals_csv": "artifacts/baseline-deals.csv",
          "open_positions_csv": "artifacts/baseline-open.csv"
        },
        {
          "role": "strict_filter_dual_lane",
          "run_id": "<different run identifier>",
          "observed_context": { "...": "same matched context" },
          "parameters": { "InpRiskPercent": 0.5, "..." : "..." },
          "input_preset": "artifacts/strict-dual.set",
          "report_path": "artifacts/strict-dual.html",
          "deals_csv": "artifacts/strict-dual-deals.csv",
          "open_positions_csv": "artifacts/strict-dual-open.csv"
        },
        {
          "role": "strict_only",
          "run_id": "<different run identifier>",
          "observed_context": { "...": "same matched context" },
          "parameters": { "InpRiskPercent": 0.5, "..." : "..." },
          "input_preset": "artifacts/strict-only.set",
          "report_path": "artifacts/strict-only.html",
          "deals_csv": "artifacts/strict-only-deals.csv",
          "open_positions_csv": "artifacts/strict-only-open.csv"
        }
      ]
    }

In the real JSON file, observed_context must contain the full object rather than the illustrative ... text.

Run from the repository root:

    python tools/compare_mt5_variant_runs.py --manifest path/to/manifest.json --output path/to/comparison.json

The comparator fails closed when a required artifact is missing/empty, the dataset digest differs, run IDs or input presets are duplicated, a variant is missing, observed settings do not match the common context, deal history is malformed, or lane attribution is absent. It outputs hashes and separate full-period/locked-OOS performance summaries, including completed-position expectancy, profit factor, win/loss counts, average realized R where initial risk was exported, maximum closed-position drawdown, consecutive losses, and metrics by lane.

### Required payoff-asymmetry diagnostics

The comparison JSON reports average net winning-position P&L and average net losing-position P&L in account currency, average winner R, average absolute loser R, their payoff ratio, and the implied break-even win rate from those average R magnitudes. These R metrics are calculated only from completed positions with a positive, exported `risk_cash`; missing risk must remain missing, never be inferred from stop distance after the fact. R values are net of exported profit, commission, swap, and fee cashflows. The implied break-even win rate is descriptive, assumes observed average winner/loser magnitudes remain stable, and is not a forecast.

A candidate with a higher win rate but a lower payoff ratio can still have negative expectancy. Inspect payoff ratio and net expectancy together for the full period, locked OOS, and each attributed lane. Do not treat a configured target R multiple as a realized average winner R multiple.

Drawdown limitation: the existing position-ledger metric computes closed-position settlement drawdown, not intratrade/tick-level equity drawdown. Capture the native MT5 tester equity/drawdown report separately and compare it alongside this output.

## Interpretation rules

Review net expectancy after all exported deal cashflows, profit factor, maximum drawdown, win/loss size asymmetry, loss streaks, sample sufficiency, lane-specific performance, market-regime coverage, and the number of positions excluded/censored. A strict variant can reduce trade count but still improve or worsen expectancy; fewer trades alone are not success. Conversely, a target of three successful trades per weekday is an operating objective—not permission to create trades or lower entry, portfolio, execution, or risk constraints.

Do not infer statistical significance from metric differences. For the promotion decision, submit genuine normalized tester evidence through the existing evidence pipeline and use independent locked-OOS / challenger gates. This report is a matched-comparison aid, not a promotion token.
