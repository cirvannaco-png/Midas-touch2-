# Continuous Learning and Recalibration Operating Contract

## 1. EA learning inside a chronological backtest

The EA's environment/strategy memory and confidence calibration are enabled by the default inputs in `EA/MedisTouch_v2.8.mq5`:

- `InpTrackOutcomes=true`
- `InpEnvironmentMemoryMinSample=30`
- `InpEnvironmentMemoryBonus=2.0`
- `InpEnvironmentMemoryPenalty=2.0`
- `InpCalibrationMinSample=30`

Resolved outcomes update the in-run memory after they resolve; only earlier outcomes may affect a later decision in that chronological run. Environment adjustments stay bounded and require sample-size/statistical qualification. Hard setup, news, broker, portfolio, and risk gates remain authoritative.

**Tester memory is intentionally isolated from persistent live memory.** A backtest must not silently overwrite live learning history. Its results should become a separate, immutable candidate-evidence record before they can influence a future live configuration.

## 2. External recalibration cycle

The backend cycle at `POST /admin/run-cycle` analyses persisted `signal_outcomes`, calculates coverage/expectancy and confidence intervals, stores a cycle report, and evaluates registered configuration challengers. Its ordinary metrics input is the recent production outcome database, not an arbitrary in-sample backtest.

The Render web service does not schedule itself. GitLab must trigger the endpoint. The `.gitlab-ci.yml` maintenance job added by the recalibration fix:

- supports scheduled pipelines with `SCHEDULE_TASK=biweekly-recalibration`;
- runs only on the default branch;
- applies the existing alternate-Saturday parity rule anchored to 2026-01-03 UTC;
- permits an explicitly started web pipeline to request an immediate cycle;
- requires protected/masked `BRIDGE_BASE_URL` and `BRIDGE_API_KEY` variables;
- does not print the API key, and fails on non-2xx endpoint responses.

A GitLab project schedule and those CI/CD variables remain external project settings; code cannot create them through this repository file alone.

## 3. Backtest-to-live promotion boundary

The Strategy Tester must be run against the actual EA and its versioned inputs. Candidate evidence must identify the EA/build, instrument/timeframe, data version, exact configuration hash, execution-cost assumptions, temporal train/validation/locked-OOS splits, trade counts, expectancy, profit factor, drawdown, and stability across walk-forward folds.

A favorable in-sample backtest alone is not promotion evidence. A candidate must pass locked-OOS and stability validation, then proceed through the registered configuration lifecycle, human approval, and exact configuration-hash acknowledgement by the EA. No research result may bypass risk controls or silently modify live parameters.

### Important current boundary

`tools/walk_forward.py --tester-csv` can parse a real outcome CSV, but that CLI path currently reports the parsed row count; it does **not** register those rows as a candidate evaluation in the backend database. The online learner within the EA's chronological Strategy Tester run is active, and the scheduled backend cycle evaluates persisted production outcomes and already-registered challengers. An automated import that turns each exported Tester result into immutable registered backtest/OOS evidence is a separate integration step and must not be represented as already active until implemented and tested.

This separation is deliberate: it avoids treating backtest rows as live trades, mixing live and synthetic evidence, or promoting a configuration merely because it won an in-sample optimization.
