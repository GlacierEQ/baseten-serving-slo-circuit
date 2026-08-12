from __future__ import annotations

from serving_slo_circuit import CircuitState, Decision, ServingSloCircuit, ServingSloCircuitRequest


CONFIG = {"max_p95_ms": 120.0, "max_error_rate": 0.02, "min_requests": 100, "recovery_windows": 2, "half_open_admission_ratio": 0.05}


def window(*, requests=1000, errors=5, p95=90.0):
    return {"requests": requests, "errors": errors, "p95_ms": p95}


def evaluate(state: str, windows: list[dict]):
    return ServingSloCircuit().evaluate(ServingSloCircuitRequest("endpoint-a", {"state": state, "config": CONFIG, "windows": windows}, 1.0))


def test_closed_healthy_endpoint_stays_fully_admitted() -> None:
    receipt = evaluate("CLOSED", [window()])
    assert receipt.decision is Decision.ALLOW
    assert receipt.metrics["state"] == CircuitState.CLOSED.value
    assert receipt.metrics["transition"] == "STAY_CLOSED"
    assert receipt.metrics["admission_ratio"] == 1.0


def test_tail_latency_breach_trips_open() -> None:
    receipt = evaluate("CLOSED", [window(p95=180.0)])
    assert receipt.decision is Decision.REFUSE
    assert receipt.metrics["state"] == "OPEN"
    assert receipt.metrics["transition"] == "TRIP_OPEN"
    assert "tail_latency_budget_exceeded" in receipt.reasons


def test_error_budget_breach_trips_open() -> None:
    receipt = evaluate("CLOSED", [window(errors=50)])
    assert receipt.decision is Decision.REFUSE
    assert "error_budget_exceeded" in receipt.reasons


def test_insufficient_evidence_does_not_fail_open() -> None:
    receipt = evaluate("CLOSED", [window(requests=20, errors=0)])
    assert receipt.decision is Decision.REFUSE
    assert receipt.metrics["state"] == "OPEN"
    assert "insufficient_evidence" in receipt.reasons


def test_open_requires_two_healthy_windows_before_probe_admission() -> None:
    one = evaluate("OPEN", [window()])
    assert one.decision is Decision.REFUSE
    assert one.metrics["transition"] == "STAY_OPEN"
    two = evaluate("OPEN", [window(), window(p95=95.0)])
    assert two.decision is Decision.ALLOW
    assert two.metrics["state"] == "HALF_OPEN"
    assert two.metrics["admission_ratio"] == 0.05


def test_half_open_recovers_only_after_healthy_probe_windows() -> None:
    receipt = evaluate("HALF_OPEN", [window(), window(p95=100.0)])
    assert receipt.decision is Decision.ALLOW
    assert receipt.metrics["state"] == "CLOSED"
    assert receipt.metrics["transition"] == "RECOVER_CLOSED"


def test_half_open_failure_reopens_immediately() -> None:
    receipt = evaluate("HALF_OPEN", [window(), window(errors=40)])
    assert receipt.decision is Decision.REFUSE
    assert receipt.metrics["state"] == "OPEN"
    assert receipt.metrics["transition"] == "HALF_OPEN_FAILED"


def test_invalid_window_errors_over_requests_is_refused() -> None:
    receipt = evaluate("CLOSED", [window(requests=100, errors=101)])
    assert receipt.decision is Decision.REFUSE
    assert "window_0_errors_exceed_requests" in receipt.reasons
