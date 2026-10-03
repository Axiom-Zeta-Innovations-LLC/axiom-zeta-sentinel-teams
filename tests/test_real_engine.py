"""Exercises the compiled Rust engine (the other tests use a fake).

Runs in a subprocess so the fake module installed by conftest can't leak in.
Skipped if the extension isn't built, unless REQUIRE_REAL_ENGINE=1 (use that in CI).
"""
import os
import subprocess
import sys
import textwrap

import pytest

SCRIPT = textwrap.dedent(
    """
    import json, random
    from axiom_zeta_sentinel_core import DriftEngine

    def run(seed, windows):
        e = DriftEngine(18, 18, 10, seed)
        return [e.stabilize(w, None) for w in windows]

    rng = random.Random(3)
    stable = [[0.5 + rng.gauss(0, 0.03) for _ in range(48)] for _ in range(25)]
    rng = random.Random(3)
    shifted = [[(0.5 if k < 12 else 0.9) + rng.gauss(0, 0.03) for _ in range(48)] for k in range(25)]

    a = run(7, stable)
    b = run(7, stable)
    s = run(7, shifted)
    print(json.dumps({
        "deterministic": [x["drift_score"] for x in a] == [x["drift_score"] for x in b],
        "bounded": all(0.0 <= x["drift_score"] <= 1.0 and len(x["stabilized_vector"]) == 24 for x in a + s),
        "stable_max": max(x["drift_score"] for x in a[6:]),
        "shift_min": min(x["drift_score"] for x in s[12:]),
        "baseline_ready": a[-1]["baseline_ready"],
    }))
    """
)


def _run():
    return subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, timeout=300)


def test_real_engine_behaviour():
    proc = _run()
    if proc.returncode != 0:
        if "No module named 'axiom_zeta_sentinel_core'" in proc.stderr and os.getenv("REQUIRE_REAL_ENGINE") != "1":
            pytest.skip("Rust extension not built (run: cd rust && maturin develop --release)")
        pytest.fail(proc.stderr)

    import json

    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["deterministic"], "same seed + same input must give identical scores"
    assert result["bounded"]
    assert result["baseline_ready"] == 1.0
    assert result["stable_max"] < 0.45, "stable stream should not go red"
    assert result["shift_min"] >= 0.45, "a clear level shift must go red"
