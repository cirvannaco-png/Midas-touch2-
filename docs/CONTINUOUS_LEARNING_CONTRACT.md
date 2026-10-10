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

### Current implementation boundary

The authenticated `POST /research/backtest-evidence` endpoint now provides the backend evidence-ingestion path. It validates a normalized MT5 Tester evidence bundle, computes key train/validation/locked-OOS metrics on the server, checks chronological walk-forward folds and a parameter-neighborhood plateau, and appends an immutable `ConfigurationEvaluation` with report/dataset provenance references. An adequately supported, positive candidate can reach `VALIDATED`; incomplete or weak evidence remains `BACKTESTED` with a hold/insufficient-evidence decision.

The next integration requirement is the **trusted exporter and scheduled caller** that reads genuine Strategy Tester outputs, adds the run/configuration manifest and research artifacts, and sends the normalized evidence bundle to that endpoint. The endpoint intentionally does not claim to authenticate an MT5 desktop or independently read local report files. Keep the original report and market-data file, and compare their digests to the registered provenance.

The ordinary biweekly `POST /admin/run-cycle` still analyzes recent production outcomes and already-registered `CHALLENGER` configurations. It does not silently transform backtest observations into live `signal_outcomes`. Backtest evidence also does not skip `QUARANTINE`, `SHADOW`, or `CHALLENGER`, create an approval, or activate the EA. Candidate promotion remains gated by the existing configuration lifecycle, human approval, and exact EA configuration-hash acknowledgement.

This separation prevents live and synthetic evidence from being mixed and prevents a candidate from winning merely because it performed well in-sample.
