# SMC Structural Validator

## Purpose

Midas now records whether an SMC setup satisfies a causal structural chain before any future policy promotion:

`trend/HTF structure -> liquidity target -> sweep -> displacement/BOS -> causal entry origin -> premium/discount -> freshness -> structural invalidation`

The validator also records whether a nearby HTF Order Block exists, but HTF OB proximity is context telemetry rather than proof of validity.

## Important boundary

The validator is **diagnostic-only in this revision**. It does not change:

- confidence arithmetic
- strategy selection
- stop/target construction
- risk sizing
- portfolio admission
- order execution
- signal semantics

That separation is deliberate. The first research question is whether structurally-valid SMCs have materially different outcome distributions from structurally-invalid SMCs. A gate should only be enabled after controlled ablation and out-of-sample validation.

## Causal rules

The entry FVG is considered causal only when:

1. it matches the trade direction,
2. it is still fresh/tested,
3. it is close enough to current price under the existing FVG distance policy, and
4. its series index falls between the liquidity sweep and confirming BOS, so the zone can plausibly belong to the sweep→displacement→BOS move.

The current forming bar (shift 0) is excluded from causal-FVG and causal-OB classification to avoid turning incomplete intrabar state into structural evidence.

Distance normalization uses the last closed entry-timeframe bar (ATR shift 1), so the audit classification does not move merely because the current candle is still forming. Causal OB provenance is sourced from the same entry/FVG timeframe; the chart-TF SR context is not treated as causal evidence.

A local order block is treated similarly for provenance telemetry. A higher-timeframe order block is recorded separately and is never mislabeled as causal to the entry-timeframe BOS.

## Displacement provenance

The authoritative inducement engine now exposes the exact displacement bar that triggered the impulse qualification. Structural validity requires the explicit chronological relation:

`displacement bar (older) -> liquidity sweep -> confirming BOS (newer)`

Using the actual bar indices prevents a generic `impulseFound=true` flag from being mistaken for proof that the displacement caused the later sweep/BOS chain.

## Audit output

SMC-selected setups are written to:

`MedisTouch_SMC_Structures_<SYMBOL>.csv`

The rows include structural state, each chain component, HTF structure context, causal FVG/OB bar indices, protected/invalidation levels, and a reason code.

The audit file is separate from the legacy signal CSV so existing signal schemas are not silently changed.

## Promotion gate

The EA now exposes:

`InpRequireSMCStructuralValidity=false`

When this switch is **off**, the validator remains diagnostic-only exactly as above.

When this switch is **on**, a setup that has already been selected as `STRATEGY_SMC` is rejected unless `smc_structural_valid` is true. The rejection happens before SMC setup construction, so invalid SMC structure cannot proceed to the risk or execution layers. There is no silent fallback to a different strategy after an SMC structural rejection.

This is an experiment switch, not a claim that the gate has been validated. Before enabling it for production, compare:

- baseline selected SMCs
- structurally-valid SMCs
- structurally-invalid SMCs
- baseline versus the opt-in structural gate

using the same data split, execution model, spread/slippage assumptions, stop policy, and Dynamic Stop version.

Required evidence remains temporal holdout / walk-forward validation plus sensitivity testing. No confidence-threshold tuning is part of this stage.
