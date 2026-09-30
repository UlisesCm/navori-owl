"""Pure statistics for the round report (design D12, R26-R29). Stdlib only."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

_EPS = 1e-12
_EXACT_MAX_N = 20
_MC_SAMPLES = 100_000


def sign_flip_p(values: Sequence[float], seed: int = 0) -> float:
    """Two-sided sign-flip permutation p-value of the sum of ``values``.

    p = #{signs: |sum(s_k x_k)| >= |sum(x)| - 1e-12} / 2^n. Exact enumeration for
    n <= 20, otherwise a seeded Monte Carlo of 100 000 draws. All-equal (e.g. all
    zero) inputs give p = 1.
    """
    n = len(values)
    if n == 0:
        return 1.0
    observed = abs(sum(values)) - _EPS
    if n <= _EXACT_MAX_N:
        sums = [0.0]
        for x in values:
            sums = [s + sign * x for s in sums for sign in (1.0, -1.0)]
        return sum(1 for s in sums if abs(s) >= observed) / len(sums)
    rng = random.Random(seed)
    hits = 0
    for _ in range(_MC_SAMPLES):
        total = sum(x if rng.getrandbits(1) else -x for x in values)
        if abs(total) >= observed:
            hits += 1
    return hits / _MC_SAMPLES


def _quantile(sorted_vals: Sequence[float], q: float) -> float:
    """Type-7 (linear interpolation) quantile of an already sorted sequence."""
    h = (len(sorted_vals) - 1) * q
    lo = math.floor(h)
    hi = math.ceil(h)
    return sorted_vals[lo] + (h - lo) * (sorted_vals[hi] - sorted_vals[lo])


def task_bootstrap_ci(
    values: Sequence[float],
    seed: int,
    b: int = 10_000,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Percentile bootstrap interval of the mean over per-task values.

    Resamples the tasks with replacement (not trials). Returns ``None`` when every
    value is identical (or there are none): the interval would be ``[x, x]`` and
    carries no information, so the caller prints per-arm counts instead.
    """
    n = len(values)
    if n == 0 or all(abs(v - values[0]) <= _EPS for v in values):
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(b))
    tail = (1.0 - level) / 2.0
    return _quantile(means, tail), _quantile(means, 1.0 - tail)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def log_cost_ratios(
    variant: Sequence[Sequence[float]], ref: Sequence[Sequence[float]]
) -> list[float]:
    """Per-task ``ln(mean cost variant / mean cost ref)``; one trial list per task."""
    return [math.log(_mean(v) / _mean(r)) for v, r in zip(variant, ref, strict=True)]


def cost_pct_change(log_ratios: Sequence[float]) -> float:
    """Cost estimate as a percent change: ``100 * (exp(mean r) - 1)``."""
    return 100.0 * (math.exp(_mean(log_ratios)) - 1.0)


def rate_differences(
    variant: Sequence[Sequence[float]], ref: Sequence[Sequence[float]]
) -> list[float]:
    """Per-task difference of mean per-trial rates (behavior violation or success)."""
    return [_mean(v) - _mean(r) for v, r in zip(variant, ref, strict=True)]


def pass_hat_k(c: int, n: int, k: int) -> float | None:
    """pass^k = C(c, k) / C(n, k) for one task; ``None`` (n/a) when n < k."""
    if n < k:
        return None
    return math.comb(c, k) / math.comb(n, k)


def mean_pass_hat_k(cells: Sequence[tuple[int, int]], k: int) -> float | None:
    """Mean pass^k over tasks given ``(c, n)`` cells, skipping n/a tasks."""
    vals = [v for c, n in cells if (v := pass_hat_k(c, n, k)) is not None]
    return _mean(vals) if vals else None


__all__ = [
    "cost_pct_change",
    "holm",
    "log_cost_ratios",
    "mean_pass_hat_k",
    "pass_hat_k",
    "rate_differences",
    "sign_flip_p",
    "task_bootstrap_ci",
]

