"""Tests for owl.analysis: hand-computed cases and the D12 coverage simulation."""

from __future__ import annotations

import math
import random
import time

import pytest

from owl.analysis import (
    cost_pct_change,
    holm,
    log_cost_ratios,
    mean_pass_hat_k,
    pass_hat_k,
    rate_differences,
    sign_flip_p,
    task_bootstrap_ci,
)


# Covers: R26
def test_sign_flip_hand_computed():
    assert sign_flip_p([0.2, 0.4, 0.6]) == pytest.approx(0.25)
    assert sign_flip_p([1, -1]) == pytest.approx(1.0)


# Covers: R26
def test_equal_values_no_interval_and_p_one():
    assert sign_flip_p([0.0] * 12) == 1.0
    assert task_bootstrap_ci([0.0] * 12, seed=1) is None
    assert task_bootstrap_ci([0.3, 0.3, 0.3], seed=1) is None


# Covers: R26
def test_sign_flip_monte_carlo_is_seeded():
    xs = [1.0] * 25
    assert sign_flip_p(xs, seed=3) == sign_flip_p(xs, seed=3)
    assert sign_flip_p(xs, seed=3) < 0.001


# Covers: R26, R28
def test_bootstrap_deterministic_by_seed():
    xs = [0.1, -0.2, 0.43, 0.0, 0.31, -0.17, 0.05, 0.27, -0.33, 0.12, 0.6, -0.04]
    a = task_bootstrap_ci(xs, seed=7, b=2000)
    assert a == task_bootstrap_ci(xs, seed=7, b=2000)
    assert a != task_bootstrap_ci(xs, seed=8, b=2000)
    assert a is not None and a[0] < sum(xs) / len(xs) < a[1]


# Covers: R26
def test_constant_double_cost_is_plus_100_percent():
    variant = [[0.2, 0.4], [1.0], [0.5, 0.5, 0.5]]
    ref = [[0.1, 0.2], [0.5], [0.25, 0.25, 0.25]]
    r = log_cost_ratios(variant, ref)
    assert all(x == pytest.approx(math.log(2)) for x in r)
    assert cost_pct_change(r) == pytest.approx(100.0)


# Covers: R26, R28
def test_rate_differences():
    assert rate_differences([[1, 1, 0, 0], [0, 0]], [[1, 0, 0, 0], [0, 0]]) == [
        pytest.approx(0.25),
        0.0,
    ]


# Covers: R27
def test_holm_hand_computed():
    got = holm([0.01, 0.04, 0.03, 0.005])
    assert got == pytest.approx([0.03, 0.06, 0.06, 0.02])


# Covers: R27
def test_holm_family_of_ten():
    p = [0.001, 0.004, 0.005, 0.01, 0.02, 0.03, 0.04, 0.2, 0.5, 0.9]
    adj = holm(p)
    assert adj[0] == pytest.approx(0.01)  # 10 * 0.001
    assert adj[1] == pytest.approx(0.036)  # 9 * 0.004
    assert adj[2] == pytest.approx(0.04)  # 8 * 0.005
    assert adj[3] == pytest.approx(0.07)  # 7 * 0.01
    assert adj == sorted(adj)  # monotone step-down
    assert all(a >= x for a, x in zip(adj, p, strict=True))
    assert adj[-1] == pytest.approx(1.0)  # 2*0.5 = 1.0 propagates
    # with alpha = 0.05 only the first three differ
    assert [a < 0.05 for a in adj].count(True) == 3
    # first step demands p < alpha / 10
    assert holm([0.006] + [0.9] * 9)[0] == pytest.approx(0.06)
    # capped at 1
    assert holm([0.6, 0.7]) == pytest.approx([1.0, 1.0])


# Covers: R29
def test_pass_hat_k():
    assert pass_hat_k(4, 5, 3) == pytest.approx(0.4)
    assert pass_hat_k(5, 5, 5) == 1.0
    assert pass_hat_k(0, 5, 3) == 0.0
    assert pass_hat_k(2, 2, 3) is None
    assert mean_pass_hat_k([(4, 5), (5, 5), (1, 2)], 3) == pytest.approx(0.7)
    assert mean_pass_hat_k([(1, 2)], 3) is None


# --- Coverage simulation (D12 generator) -------------------------------------------

_TASKS = 12
_K = 5
_REPS = 200
_B = 2000
_THRESHOLD = 0.88


def _coverage(name: str, make_values, truth: float, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    covered = degenerate = 0
    for rep in range(_REPS):
        xs = make_values(rng)
        ci = task_bootstrap_ci(xs, seed=seed * 1000 + rep, b=_B)
        if ci is None:
            degenerate += 1
            ci = (xs[0], xs[0])
        covered += ci[0] - 1e-12 <= truth <= ci[1] + 1e-12
    cov, deg = covered / _REPS, degenerate / _REPS
    return cov, deg


def _cost_values(delta: float):
    def make(rng: random.Random) -> list[float]:
        out = []
        for _ in range(_TASKS):
            mu = rng.gauss(math.log(0.13), 0.8)
            d_i = rng.gauss(delta, 0.2)
            ref = [[math.exp(mu + rng.gauss(0, 0.4)) for _ in range(_K)]]
            var = [[math.exp(mu + d_i + rng.gauss(0, 0.4)) for _ in range(_K)]]
            out.extend(log_cost_ratios(var, ref))
        return out

    return make


def _success_values(p_ref: list[float], p_var: list[float]):
    def make(rng: random.Random) -> list[float]:
        return [
            sum(rng.random() < pv for _ in range(_K)) / _K
            - sum(rng.random() < pr for _ in range(_K)) / _K
            for pr, pv in zip(p_ref, p_var, strict=True)
        ]

    return make


def _behavior_values(rng: random.Random) -> list[float]:
    out = []
    for _ in range(_TASKS):
        w = rng.betavariate(0.3, 6)
        a = sum(rng.random() < w for _ in range(_K)) / _K
        b = sum(rng.random() < w for _ in range(_K)) / _K
        out.append(a - b)
    return out


_P_REF = [0.95] * 8 + [0.5] + [0.1] * 3
_P_DROP = [0.95] * 8 + [0.4] + [0.0] * 3  # -0.10 on the 4 tasks under the ceiling, floor 0
_SCENARIOS = {
    "cost_null": (_cost_values(0.0), 0.0),
    "cost_1.5x": (_cost_values(math.log(1.5)), math.log(1.5)),
    "success_null": (_success_values(_P_REF, _P_REF), 0.0),
    "success_drop": (
        _success_values(_P_REF, _P_DROP),
        sum(v - r for v, r in zip(_P_DROP, _P_REF, strict=True)) / _TASKS,
    ),
    "behavior_sparse": (_behavior_values, 0.0),
}


# Covers: R26, R28
@pytest.mark.parametrize("name", list(_SCENARIOS))
def test_bootstrap_coverage(name, record_property):
    make, truth = _SCENARIOS[name]
    start = time.perf_counter()
    cov, deg = _coverage(name, make, truth, seed=20260101 + list(_SCENARIOS).index(name))
    record_property("coverage", cov)
    record_property("degenerate_fraction", deg)
    record_property("seconds", round(time.perf_counter() - start, 2))
    assert cov >= _THRESHOLD, f"{name}: coverage {cov:.3f} (degenerate {deg:.3f})"
