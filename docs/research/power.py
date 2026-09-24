"""Power simulation for paired harness comparisons (A vs B) on binary task success.

Question it answers: with T tasks x k trials per arm, how often does a sign-flip
permutation test over per-task differences d_i = p_B(i) - p_A(i) detect a real
effect at alpha = 0.05 (two-sided)?

Assumptions (an estimate, not a source):
- Base difficulty per task ~ Beta(2, 2), clipped to [0.03, 0.97].
- Constant effect on the logit scale (delta_logit), reported back in percentage points.
- 400 simulations per cell, 2000 sign flips per test.

Origin: navori-evals/docs/research/power.py (2026-09-23), used for doc 02 section 3.4.
Run: python3 power.py   (requires numpy)
"""
import numpy as np

rng = np.random.default_rng(0)


def logit(p):
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def signflip_p(d, B=2000):
    obs = abs(d.mean())
    s = rng.choice([-1, 1], size=(B, len(d)))
    return (np.abs((s * d).mean(1)) >= obs - 1e-12).mean()


def power(T, k, delta_logit, sims=400):
    hits = 0
    eff = []
    for _ in range(sims):
        base = np.clip(rng.beta(2, 2, size=T), 0.03, 0.97)
        pt = expit(logit(base) + delta_logit)
        eff.append((pt - base).mean())
        a = rng.binomial(k, base) / k
        b = rng.binomial(k, pt) / k
        if signflip_p(b - a) < 0.05:
            hits += 1
    return hits / sims, np.mean(eff)


if __name__ == "__main__":
    print("tasks trials  effect:power ...")
    for T in (8, 12, 15, 20):
        for k in (3, 5):
            row = []
            for dl in (0.5, 1.0, 1.5):
                pw, e = power(T, k, dl)
                row.append(f"+{e * 100:.0f}pp:{pw:.2f}")
            print(T, k, " ".join(row))
