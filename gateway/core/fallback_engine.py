from __future__ import annotations
import math
from statistics import mean, pstdev

class DriftEngine:
    """Pure-Python fallback engine (MVP deploy without Rust toolchain).

    Implements the same interface as the Rust `axiom_zeta_sentinel_core.DriftEngine`:
    learns a per-instance baseline over `baseline_windows` calls, then scores drift
    by mean/scale shift relative to that baseline. Stabilized vector is a bounded
    24-D projection of the incoming metric window.
    """
    def __init__(self, nx=18, ny=18, n_fields=10, seed=42, baseline_windows=5):
        self.baseline_windows = int(baseline_windows or 5)
        self._windows: list[list[float]] = []
        self._baseline_mean: float | None = None
        self._baseline_std: float = 1.0
        self._ema = 0.0
    def reset_baseline(self):
        self._windows=[]; self._baseline_mean=None; self._baseline_std=1.0; self._ema=0.0
    def stabilize(self, metric_window, embedding=None):
        w=[float(x) for x in (metric_window or [0.0])]
        if self._baseline_mean is None:
            self._windows.append(w)
            flat=[x for win in self._windows for x in win]
            if len(self._windows) >= self.baseline_windows:
                self._baseline_mean=mean(flat)
                self._baseline_std=pstdev(flat) or 1.0
            drift=0.0
        else:
            m=mean(w); s=pstdev(w) if len(w)>1 else 0.0
            std=self._baseline_std or 1.0
            level_shift=abs(m-self._baseline_mean)/std
            scale_shift=abs(s-std)/std if std else 0.0
            drift=max(0.0, min(1.0, (level_shift*0.7 + scale_shift*0.3)/3.0))
        self._ema=0.9*self._ema+0.1*drift
        # bounded 24-D stabilized vector: normalized window resampled
        out=[]
        for i in range(24):
            idx=round(i*(len(w)-1)/23) if len(w)>1 else 0
            out.append(float(math.tanh(w[idx]/ (abs(self._baseline_mean or 1.0)+1.0) )) if w else 0.0)
        return {"stabilized_vector": out, "drift_score": float(drift), "euler_chi":0.0,"genus":0.0,"beta0":1.0,"beta1":0.0,"energy_level":float(mean([abs(x) for x in w]) if w else 0.0),"stress_level":float(drift),"drift_ema":float(self._ema),"drift_trend":float(drift-self._ema),"topology_volatility":0.0,"surgery_rate":0.0,"surgery_total":0.0,"baseline_ready":1.0 if self._baseline_mean is not None else 0.0,"baseline_drift":float(drift),"level_shift":float(abs(mean(w)-(self._baseline_mean or mean(w))) if w else 0.0),"scale_shift":0.0,"psi":float(drift),"embedding_shift":0.0,"hrm_score":float(drift)}
