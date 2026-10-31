# MT5 Strategy Tester + Broker-Neutral Demo Validation Runbook

Status: execution procedure only. No performance test or broker test is claimed by this document.

## Safety boundary

- Keep live trading disabled. Do not promote or deploy based only on compilation, structural checks, or policy unit tests; require matched Strategy Tester, locked-OOS and selected-broker demo evidence.
- Use a dedicated **MT5 demo** account with the broker selected by the operator. Never place credentials, account numbers, API keys, investor passwords, or unredacted account statements in GitHub artifacts or issue comments.
- Record the exact EA source commit, compiled EA build, terminal build, symbol specification, and tester configuration before the first run.
- Preserve the current production trailing-stop default and all existing emergency-stop and account-risk safeguards.
- If the terminal build, broker symbol properties, history quality, or cost assumptions cannot be verified, mark the run BLOCKED; do not fill missing facts with estimates.

## Gate A — prepare one immutable test bundle

For native tester deal exports, set `InpTesterServerUtcOffsetMinutes` to the selected broker server's verified UTC offset in minutes. The exporter records broker-wall-clock timestamps with an explicit ISO-8601 offset and never labels them UTC with `Z` by default. The configured offset must remain constant for each run. Split test windows at daylight-saving/timezone transitions and use the verified offset for each segment. Leave evidence export disabled when the offset is unknown or cannot be verified.

Create a dated folder outside the repository, for example `validation/2026-10-18/`, and retain:

1. Exact EA source commit SHA and compiled `.ex5` hash.
2. MetaEditor compile log with error and warning counts.
3. MT5 terminal build, broker server name (redacted if necessary), account currency, leverage, margin mode, symbol contract/tick/volume properties, and timezone.
4. One immutable tick/history dataset or a reproducible broker data window, with SHA-256. Record the tester's data mode (prefer real ticks where available).
5. Three distinct `.set` presets and a short parameter-difference declaration.
6. Commission, swap, spread, and slippage settings/assumptions based on the selected broker/account. If any cost is unavailable, state that limitation and do not describe the result as fully cost-inclusive.

## Gate B — matched historical Strategy Tester matrix

Run all three variants independently with identical symbol, timeframe, start/end dates, dataset, terminal build, initial balance, leverage, fill policy, risk sizing, and cost assumptions:

- `baseline_dual_lane`: frozen current baseline.
- `strict_filter_dual_lane`: same strategy with predeclared stricter qualification filters.
- `strict_only`: strict qualifying lane only, no fallback entries.

Change only the predeclared variant parameters. Do not tune on the locked out-of-sample (OOS) interval. Record the locked-OOS window before reviewing results. Run enough history beyond the OOS entry window to allow trades to close; positions still open at the boundary remain censored/unresolved, not wins or losses.

For every run, export:
- the actual `.set` file used;
- native Strategy Tester HTML report and complete deal-history CSV;
- open/incomplete position IDs (header-only file if none);
- tester log and run timestamps;
- a screenshot or export showing the tester configuration and data mode.

The deal export must preserve position identifiers, entry/exit deal types, timestamps, volume, profit, commission, swap, fees, and lane/risk-lane attribution. Do not manually edit the raw exports.

## Gate C — compare the real artifacts

Use `docs/MATCHED_MT5_VARIANT_PROTOCOL.md` and `tools/compare_mt5_variant_runs.py`. Build the manifest from the actual run settings and artifact hashes; never copy example values into the evidence.

Example command after the manifest and files are ready:

```bash
python tools/compare_mt5_variant_runs.py \
  --manifest validation/2026-10-18/manifest.json \
  --output validation/2026-10-18/comparison.json
```

Review full-period and locked-OOS results separately:
- net expectancy per completed position and realized R;
- profit factor and net P&L after costs;
- native tester equity drawdown plus the comparator's closed-position drawdown;
- maximum consecutive losses and loss-size asymmetry;
- completed positions, open/censored/incomplete positions, and sample coverage;
- minimum-volume rejections, risk-limit blocks, and every hard-halt trigger;
- long/short, symbol, timeframe, session, and regime splits where sample size supports them.

The comparison tool is not an automatic promotion decision. Zero trades is a valid result. Never lower a filter just to hit a daily trade-count target.

## Gate D — demo-broker execution and recovery

After historical tests are captured, run a bounded demo-only forward validation and record every case below. Use small, controlled exposure and stop immediately if the observed state disagrees with broker state.

- [ ] Confirm `PROP_FIRM` is the selected default and its frozen inputs match the compatibility baseline.
- [ ] Confirm `MICRO_RESEARCH` is blocked without the second explicit acknowledgement and cannot execute on a real-money account.
- [ ] Confirm a profile change while positions or pending orders exist keeps managing existing exposure under the persisted profile and blocks new entries.
- [ ] Restart the terminal/VPS with an open demo position and with a pending order; verify state recovery and protection.
- [ ] Verify partial close, partial fill, duplicate deal replay, rejected order, ambiguous submission, and delayed history cases.
- [ ] Verify reconciliation of live positions, pending orders, broker deal history, durable ledger, and database; any unresolved mismatch must block new entries.
- [ ] Verify stop-loss/take-profit modifications against the broker's tick size, stop/freeze levels, minimum volume and volume step.
- [ ] Verify emergency-stop persistence across terminal/VPS restart and confirm that no new entries are admitted while halted.
- [ ] Verify authenticated bridge/ledger health without printing secrets to logs.
- [ ] Retain sanitized logs, deal exports, config signature, EA/terminal build, and exact timestamps.

## Acceptance decision

Mark the gate PASS only when the evidence is reproducible and all required scenarios pass. Mark it FAIL for a verified defect; mark it BLOCKED when a required target-terminal or broker test could not be run. Do not substitute unit tests or compilation for historical performance testing or demo-forward evidence.

PR #82 remains draft until all acceptance criteria in Issue #84 are evidenced and independently reviewed. Even a passing demo run does not establish future profitability or authorize live deployment by itself.


## Export naming and attribution

The exporter only activates inside the native MetaTrader 5 Strategy Tester. It appends a runtime tick suffix to the supplied run tag so repeated runs are less likely to overwrite the same Common Files output. Keep the supplied run tag meaningful (for example, a model/build or experiment label) and retain the final emitted run ID from the journal.

The CSV `lane` field is deliberately `EA`: it identifies the managed-execution lane, not an asserted SMC/peer strategy classification. Do not infer strategy-level attribution from that column. Group deal rows by `position_id` and preserve individual deal cashflows; the `risk_cash` value is the position's aggregated recorded entry-risk basis, so do not sum it once per deal row.
