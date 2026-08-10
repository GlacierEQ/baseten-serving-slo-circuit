# Issue contract — Serving SLO Circuit

## Problem
Model serving endpoints over-admit traffic when tail latency and error budgets drift without a hard circuit.

## Desired outcome
A bounded, open, testable implementation of **Serving SLO Circuit** that demonstrates Track finite SLO metrics and trip a circuit breaker with explicit recovery gates before re-admission.

## Non-goals
- Baseten affiliation or proprietary integration
- Portfolio-wide scale/performance claims
- UI marketing site

## Acceptance
1. Mechanism module implements allow + refuse with structured receipts
2. pytest behavioral suite green
3. operate.py cold-start produces JSON receipt
4. Non-affiliation disclaimer preserved
