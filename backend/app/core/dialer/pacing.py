"""
SmartDialer — Statistical Pacing Engine (Feature C).

Implements the binomial quantile used to answer the question:
  "Given connect_rate p, if I launch m simultaneous calls,
   how many will plausibly answer at the same time?"

Written from scratch.  No import from the credresolve folder.
Rationale is identical to the CredResolve assignment's binomial.py:
the recurrence avoids computing binomial coefficients (no overflow,
no log domain), and every arithmetic step can be explained verbally.

    pmf(0) = (1-p)^m
    pmf(k) = pmf(k-1) * ((m-k+1)/k) * (p/(1-p))

Public API
----------
  recommend(connect_rate, available_agent_slots, risk_alpha) -> PacingRecommendation
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# --------------------------------------------------------------------------- #
# Pure math: no side-effects, no I/O                                           #
# --------------------------------------------------------------------------- #

def _binomial_cdf(k: int, m: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(m, p)."""
    if m < 0:
        raise ValueError("m must be non-negative")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be a probability in [0, 1]")
    if k < 0:
        return 0.0
    if k >= m:
        return 1.0
    if p <= 0.0:
        return 1.0   # all mass at 0
    if p >= 1.0:
        return 0.0   # all mass at m (and k < m here)

    ratio = p / (1.0 - p)
    term  = (1.0 - p) ** m
    total = term
    for i in range(1, k + 1):
        term  *= (m - i + 1) / i * ratio
        total += term
    return min(1.0, total)


def _binomial_quantile(alpha: float, m: int, p: float) -> int:
    """
    Smallest k such that P(X <= k) >= alpha, for X ~ Binomial(m, p).

    Interpretation: "at risk tolerance alpha, at most k calls will
    answer simultaneously out of m launched."
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be strictly between 0 and 1")
    if m <= 0:
        return 0
    if p <= 0.0:
        return 0
    if p >= 1.0:
        return m

    ratio = p / (1.0 - p)
    term  = (1.0 - p) ** m
    total = term
    if total >= alpha:
        return 0
    for k in range(1, m + 1):
        term  *= (m - k + 1) / k * ratio
        total += term
        if total >= alpha:
            return k
    return m


# --------------------------------------------------------------------------- #
# Recommendation dataclass                                                      #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PacingRecommendation:
    """Output of the pacing engine for one scheduling tick."""
    proposed_dials:      int      # max calls to launch
    expected_connects:   float    # expected simultaneous answers (mean = m*p)
    p95_connects:        int      # 95th-percentile simultaneous answers
    connect_rate:        float    # p used in this calculation
    available_slots:     int      # total agent slots (AI + human) available
    risk_alpha:          float    # risk tolerance used
    rationale:           str      # human-readable explanation


# --------------------------------------------------------------------------- #
# Pacing engine                                                                 #
# --------------------------------------------------------------------------- #

class PacingEngine:
    """
    Stateless binomial pacing calculator.

    recommended_dials = largest m such that:
        P(X > available_slots) <= (1 - risk_alpha)
    i.e.  P(X <= available_slots) >= risk_alpha
    where X ~ Binomial(m, connect_rate).

    In plain English: "dial m calls so that the chance of more people
    answering than there are agent slots is below our tolerance."
    """

    # Safety limits applied before the statistical calculation
    MAX_CONCURRENT_DIALS = 50
    MIN_CONNECT_RATE     = 0.05    # floor: avoid division-by-zero / degenerate plans
    MAX_CONNECT_RATE     = 0.95    # cap: we never assume everyone answers

    def recommend(
        self,
        connect_rate: float,
        available_agent_slots: int,
        risk_alpha: float = 0.95,
    ) -> PacingRecommendation:
        """
        Returns the maximum number of simultaneous calls to launch.

        Parameters
        ----------
        connect_rate:          rolling fraction of calls that result in an answer
        available_agent_slots: number of AI + human slots free right now
        risk_alpha:            acceptable probability that connects <= slots
                               (default 0.95 = 5% risk of an abandoned call)
        """
        if available_agent_slots <= 0:
            return PacingRecommendation(
                proposed_dials    = 0,
                expected_connects = 0.0,
                p95_connects      = 0,
                connect_rate      = connect_rate,
                available_slots   = available_agent_slots,
                risk_alpha        = risk_alpha,
                rationale         = "No agent slots available — dialing paused.",
            )

        p = max(self.MIN_CONNECT_RATE, min(self.MAX_CONNECT_RATE, connect_rate))

        # Binary search for the largest m that keeps the p95 within slots
        best_m = 0
        for m in range(1, self.MAX_CONCURRENT_DIALS + 1):
            p95 = _binomial_quantile(risk_alpha, m, p)
            if p95 <= available_agent_slots:
                best_m = m
            else:
                break

        expected = round(best_m * p, 1)
        p95      = _binomial_quantile(risk_alpha, best_m, p) if best_m > 0 else 0

        rationale = (
            f"connect rate {p:.0%} · {available_agent_slots} slot(s) available · "
            f"P95 simultaneous answers = {p95} ≤ slots · "
            f"risk tolerance α={risk_alpha:.0%} · "
            f"proposed {best_m} dial(s)"
        )

        return PacingRecommendation(
            proposed_dials    = best_m,
            expected_connects = expected,
            p95_connects      = p95,
            connect_rate      = p,
            available_slots   = available_agent_slots,
            risk_alpha        = risk_alpha,
            rationale         = rationale,
        )


pacing_engine = PacingEngine()
