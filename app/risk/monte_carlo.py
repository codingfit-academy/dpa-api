"""
Monte Carlo 불확실성 전파 (PDF §불확실성 정량화).
계수 β를 정규근사 N(β_hat, SE²)로 샘플링하여 RR/p의 분위값을 구함.
"""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Dict, List

from .effects import Effect
from .math_core import absolute_prob_from_hazard, rr_from_effects

[0.2, 0.5, 0.1]

def _quantile(xs: List[float], q: float) -> float:
    if not xs:
        return float("nan")
    arr = sorted(xs)
    pos = (len(arr) - 1) * q
    base = int(pos)
    rest = pos - base
    if base + 1 >= len(arr):
        return arr[base]
    return arr[base] + rest * (arr[base + 1] - arr[base])


def monte_carlo_ci(
    effects: List[Effect],
    exposures: Dict[str, float],
    lambda0_per_day: float,
    delta_t_days: float,
    n: int = 5000,
    seed: int | None = None,
) -> Dict[str, Dict[str, float]]:
    """β를 정규분포로 가정하고 RR / p의 (2.5, 50, 97.5) 분위값을 반환."""
    rng = random.Random(seed)
    rr_samples: List[float] = []
    p_samples: List[float] = []

    for _ in range(n):
        sampled = []
        for e in effects:
            beta_s = e.beta + (e.se * rng.gauss(0.0, 1.0) if e.se > 0 else 0.0)
            sampled.append(replace(e, beta=beta_s))
        rr = rr_from_effects(sampled, exposures)
        p = absolute_prob_from_hazard(lambda0_per_day, rr, delta_t_days)
        rr_samples.append(rr)
        p_samples.append(p)

    return {
        "rr": {
            "p2_5": _quantile(rr_samples, 0.025),
            "p50": _quantile(rr_samples, 0.5),
            "p97_5": _quantile(rr_samples, 0.975),
        },
        "p": {
            "p2_5": _quantile(p_samples, 0.025),
            "p50": _quantile(p_samples, 0.5),
            "p97_5": _quantile(p_samples, 0.975),
        },
    }
