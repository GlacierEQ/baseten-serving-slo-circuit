# DEV_UP_INSTRUCTIONS — implementation record

**Repository:** `GlacierEQ/baseten-serving-slo-circuit`  
**Independent company lens:** Baseten  
**Innovation:** Serving SLO Circuit

## Mission

Prevent model-serving endpoints from failing open when tail latency and error budgets degrade.

## Implemented

The generic scaffold has been replaced by a stateful CLOSED/OPEN/HALF_OPEN circuit.

`src/serving_slo_circuit.py` now:

- validates finite request-window evidence;
- trips open on latency/error breaches or insufficient evidence;
- holds traffic closed until multiple healthy recovery windows exist;
- permits only a bounded probe ratio in HALF_OPEN;
- immediately reopens on a failed probe window;
- recovers full admission only after the configured healthy evidence threshold;
- emits state/transition/admission metrics and deterministic receipts.

`src/serving_slo_cli.py` and `scripts/operate.py` execute the mechanism directly. The project is packaged with the `serving-slo-circuit` console command.

## Verification contract

Behavioral tests cover healthy closed state, latency trip, error trip, insufficient evidence, open-state recovery threshold, half-open recovery, failed probes, and impossible error counts. Existing adversarial coverage remains active.

CI must pass tests, cold-start, wheel build/install and installed CLI execution before Helix promotion evidence can be minted.

## Truth boundary

No Baseten affiliation, proprietary access, production deployment, customer impact, or company partnership is claimed. A real metrics/traffic adapter remains a further end-to-end deployment step.
