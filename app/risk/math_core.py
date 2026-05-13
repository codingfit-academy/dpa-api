"""
RR 및 절대확률 계산 (PDF §위험 계산 로직).
- RR(x) = exp( Σ β_i · (x_i - xRef_i) )
- 희귀사건 근사: p ≈ p0 · RR
- 위험률 기반: p(Δt) = 1 - exp(-(λ0 · RR) · Δt)
"""
from __future__ import annotations

import math
from typing import Dict, Iterable

from .effects import Effect


def rr_from_effects(effects: Iterable[Effect], exposures: Dict[str, float]) -> float:
    log_rr = 0.0
    for e in effects:
        x = exposures.get(e.name)
        if x is None:
            continue
        dx = float(x) - float(e.x_ref)
        log_rr += e.beta * dx
    return math.exp(log_rr)


def absolute_prob_from_hazard(lambda0_per_day: float, rr: float, delta_t_days: float) -> float:
    lam = lambda0_per_day * rr
    return 1.0 - math.exp(-lam * delta_t_days)


def absolute_prob_rare_event(p0_per_day: float, rr: float, delta_t_days: float) -> float:
    """희귀사건 근사. p0가 작을 때만 사용."""
    return min(1.0, p0_per_day * rr * delta_t_days)
