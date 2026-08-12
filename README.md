# Serving SLO Circuit

Independent GlacierEQ portfolio implementation aligned to **Baseten** operating themes.

> **Not affiliated.** This repository is not affiliated with, endorsed by, employed by, or deployed at Baseten. No proprietary access, production deployment, customer impact, or company partnership is claimed.

## Purpose

Stop model-serving endpoints from continuing to admit full traffic after tail latency or error budgets are already broken.

## Implemented circuit

`ServingSloCircuit` is a deterministic **CLOSED → OPEN → HALF_OPEN → CLOSED** state machine driven by finite request-window evidence.

- `CLOSED`: healthy windows preserve full admission; latency, error, or insufficient-evidence breaches trip `OPEN`.
- `OPEN`: traffic remains refused until the configured number of consecutive healthy recovery windows exists.
- `HALF_OPEN`: only a bounded probe admission ratio is allowed; a breach immediately reopens the circuit; sufficient healthy probes recover `CLOSED`.
- malformed windows, non-finite metrics, and `errors > requests` fail closed.

The receipt exposes state, transition, admission ratio, latest observed window, reason codes, and a deterministic digest.

## Run

```bash
python -m pytest -q
python scripts/operate.py
```

Build and install:

```bash
python -m pip install build
python -m build
python -m pip install dist/*.whl
serving-slo-circuit
```

## Proof surface

- `src/serving_slo_circuit.py` — stateful SLO circuit
- `src/serving_slo_cli.py` — installable execution surface
- `tests/test_serving_slo_circuit.py` — trip/recovery/probe/evidence behavior
- `tests/test_adversarial.py` — fail-closed adversarial coverage
- `.github/workflows/tests.yml` — tests + cold-start + wheel build/install + installed CLI
- `machine/` — existing Helix control-plane and promotion surfaces remain preserved

## Current boundary

The circuit consumes supplied SLO windows; it does not control Baseten infrastructure or claim production traffic results. The next depth step is a permitted metrics adapter plus a disposable HTTP inference service where the circuit can actually throttle/re-admit request traffic under induced latency and failure.
