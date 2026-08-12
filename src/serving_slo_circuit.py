"""Serving SLO Circuit.

A deterministic CLOSED/OPEN/HALF_OPEN circuit for model-serving admission. It
trips on finite tail-latency/error evidence and requires explicit healthy probe
windows before traffic is re-admitted.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REFUSE = "REFUSE"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True)
class ServingSloCircuitRequest:
    subject_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    budget: float = 1.0
    grant_id: str | None = None
    not_after: float | None = None


@dataclass(frozen=True)
class ServingSloCircuitReceipt:
    decision: Decision
    reasons: tuple[str, ...]
    digest: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"decision": self.decision.value, "reasons": list(self.reasons), "digest": self.digest, "metrics": self.metrics}


class CircuitError(ValueError):
    pass


class ServingSloCircuit:
    MIN_BUDGET = 0.0

    @staticmethod
    def _num(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CircuitError(f"{label}_invalid")
        value = float(value)
        if not math.isfinite(value):
            raise CircuitError(f"{label}_not_finite")
        if minimum is not None and value < minimum:
            raise CircuitError(f"{label}_below_minimum")
        if maximum is not None and value > maximum:
            raise CircuitError(f"{label}_above_maximum")
        return value

    @classmethod
    def _config(cls, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise CircuitError("config_missing")
        min_requests = int(cls._num(raw.get("min_requests"), "min_requests", minimum=1))
        recovery_windows = int(cls._num(raw.get("recovery_windows"), "recovery_windows", minimum=1))
        return {
            "max_p95_ms": cls._num(raw.get("max_p95_ms"), "max_p95_ms", minimum=0.001),
            "max_error_rate": cls._num(raw.get("max_error_rate"), "max_error_rate", minimum=0, maximum=1),
            "min_requests": min_requests,
            "recovery_windows": recovery_windows,
            "half_open_admission_ratio": cls._num(raw.get("half_open_admission_ratio", 0.05), "half_open_admission_ratio", minimum=0, maximum=1),
        }

    @classmethod
    def _window(cls, raw: Any, index: int) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise CircuitError(f"window_{index}_not_object")
        requests = int(cls._num(raw.get("requests"), f"window_{index}_requests", minimum=0))
        errors = int(cls._num(raw.get("errors"), f"window_{index}_errors", minimum=0))
        if errors > requests:
            raise CircuitError(f"window_{index}_errors_exceed_requests")
        return {
            "requests": requests,
            "errors": errors,
            "p95_ms": cls._num(raw.get("p95_ms"), f"window_{index}_p95_ms", minimum=0),
            "error_rate": 0.0 if requests == 0 else errors / requests,
        }

    @staticmethod
    def _healthy(window: dict[str, Any], config: dict[str, Any]) -> bool:
        return (
            window["requests"] >= config["min_requests"]
            and window["p95_ms"] <= config["max_p95_ms"]
            and window["error_rate"] <= config["max_error_rate"]
        )

    @staticmethod
    def _breaches(window: dict[str, Any], config: dict[str, Any]) -> list[str]:
        if window["requests"] < config["min_requests"]:
            return ["insufficient_evidence"]
        reasons: list[str] = []
        if window["p95_ms"] > config["max_p95_ms"]:
            reasons.append("tail_latency_budget_exceeded")
        if window["error_rate"] > config["max_error_rate"]:
            reasons.append("error_budget_exceeded")
        return reasons

    def evaluate(self, req: ServingSloCircuitRequest) -> ServingSloCircuitReceipt:
        reasons: list[str] = []
        if not str(req.subject_id or "").strip():
            reasons.append("subject_id_missing")
        if isinstance(req.budget, bool) or not isinstance(req.budget, (int, float)) or not math.isfinite(float(req.budget)) or float(req.budget) <= self.MIN_BUDGET:
            reasons.append("budget_non_positive_or_invalid")
        payload = req.payload if isinstance(req.payload, dict) else {}
        if not isinstance(req.payload, dict):
            reasons.append("payload_not_object")
        state = CircuitState.OPEN
        admission_ratio = 0.0
        transition = "REFUSED_INPUT"
        windows: list[dict[str, Any]] = []
        try:
            config = self._config(payload.get("config"))
            state = CircuitState(str(payload.get("state", "CLOSED")).upper())
            raw_windows = payload.get("windows")
            if not isinstance(raw_windows, list) or not raw_windows:
                raise CircuitError("windows_missing")
            windows = [self._window(row, i) for i, row in enumerate(raw_windows)]
            latest = windows[-1]
            breaches = self._breaches(latest, config)
            if state is CircuitState.CLOSED:
                if breaches:
                    state = CircuitState.OPEN
                    transition = "TRIP_OPEN"
                    reasons.extend(breaches)
                else:
                    transition = "STAY_CLOSED"
                    admission_ratio = 1.0
            elif state is CircuitState.OPEN:
                healthy_tail = windows[-config["recovery_windows"]:]
                if len(healthy_tail) >= config["recovery_windows"] and all(self._healthy(w, config) for w in healthy_tail):
                    state = CircuitState.HALF_OPEN
                    transition = "ENTER_HALF_OPEN"
                    admission_ratio = config["half_open_admission_ratio"]
                else:
                    transition = "STAY_OPEN"
                    reasons.append("recovery_evidence_incomplete")
            else:
                if breaches:
                    state = CircuitState.OPEN
                    transition = "HALF_OPEN_FAILED"
                    reasons.extend(breaches)
                else:
                    healthy_tail = windows[-config["recovery_windows"]:]
                    if len(healthy_tail) >= config["recovery_windows"] and all(self._healthy(w, config) for w in healthy_tail):
                        state = CircuitState.CLOSED
                        transition = "RECOVER_CLOSED"
                        admission_ratio = 1.0
                    else:
                        transition = "STAY_HALF_OPEN"
                        admission_ratio = config["half_open_admission_ratio"]
        except (CircuitError, ValueError) as exc:
            reasons.append(str(exc))
        decision = Decision.ALLOW if admission_ratio > 0 and not reasons else Decision.REFUSE
        metrics = {
            "state": state.value,
            "transition": transition,
            "admission_ratio": admission_ratio,
            "latest": windows[-1] if windows else None,
            "window_count": len(windows),
        }
        body = {"subject_id": req.subject_id, "decision": decision.value, "reasons": reasons, "metrics": metrics}
        return ServingSloCircuitReceipt(decision, tuple(reasons or ["slo_circuit_admission_allowed"]), _digest(body), metrics)


Mechanism = ServingSloCircuit
