from __future__ import annotations

import argparse
import json
from pathlib import Path

from serving_slo_circuit import Decision, ServingSloCircuit, ServingSloCircuitRequest


def demo_payload() -> dict:
    return {
        "state": "CLOSED",
        "config": {"max_p95_ms": 120.0, "max_error_rate": 0.02, "min_requests": 100, "recovery_windows": 2, "half_open_admission_ratio": 0.05},
        "windows": [{"requests": 1000, "errors": 5, "p95_ms": 90.0}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate model-serving SLO circuit state")
    parser.add_argument("--input", type=Path, help="JSON payload; defaults to deterministic healthy endpoint")
    parser.add_argument("--subject", default="serving-demo")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text()) if args.input else demo_payload()
    receipt = ServingSloCircuit().evaluate(ServingSloCircuitRequest(args.subject, payload, 1.0))
    print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    return 0 if receipt.decision is Decision.ALLOW else 2


if __name__ == "__main__":
    raise SystemExit(main())
