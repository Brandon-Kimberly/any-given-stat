import numpy as np
import pytest

from ags import lab2


def test_ols_recovers_coefficients_and_standard_errors():
    rng = np.random.default_rng(0)
    x = rng.normal(size=2000)
    X = np.column_stack([np.ones_like(x), x])
    y = 2 + 3 * x + rng.normal(scale=1.0, size=x.size)
    beta, se = lab2.ols(X, y)
    assert beta == pytest.approx([2, 3], abs=0.1)
    # se(slope) ~ sigma / sqrt(n * var(x)) = 1 / sqrt(2000)
    assert se[1] == pytest.approx(1 / np.sqrt(2000), rel=0.1)


def test_score_bets_only_past_the_threshold():
    f = {
        "vegas": np.array([3.0, 3.0, -2.0, 0.0]),
        "result": np.array([10.0, 0.0, -10.0, 5.0]),
    }
    pred = np.array([7.0, 7.0, -2.5, np.nan])
    s = lab2.score(pred, f, np.ones(4, bool), threshold=3.0)
    # Games 1 and 2 qualify (|edge| 4); game 3's edge is 0.5; game 4 has no prediction.
    assert (s["bets"], s["wins"], s["games"]) == (2, 1, 3)


def test_every_variant_uses_known_features():
    known = set(lab2.LABELS)
    for cols in lab2.VARIANTS.values():
        assert set(cols) <= known
    assert lab2.FROZEN["variant"] in lab2.VARIANTS
