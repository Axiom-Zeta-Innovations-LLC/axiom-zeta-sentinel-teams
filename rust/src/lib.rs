use pyo3::prelude::*;
use pyo3::types::PyDict;

mod engine;

#[pyclass]
pub struct DriftEngine {
    inner: engine::EngineState,
}

#[pymethods]
impl DriftEngine {
    #[new]
    #[pyo3(signature = (nx, ny, n_fields, seed, baseline_windows = 5))]
    pub fn new(nx: usize, ny: usize, n_fields: usize, seed: u64, baseline_windows: u64) -> Self {
        Self {
            inner: engine::EngineState::new(nx, ny, n_fields, seed, baseline_windows),
        }
    }

    /// Forget the learned reference baseline; the next windows re-learn it.
    pub fn reset_baseline(&mut self) {
        self.inner.reset_baseline();
    }

    pub fn stabilize(
        &mut self,
        py: Python<'_>,
        metric_window: Vec<f64>,
        embedding: Option<Vec<f64>>,
    ) -> PyResult<PyObject> {
        if metric_window.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "metric_window must not be empty",
            ));
        }

        let out = self.inner.stabilize(metric_window, embedding);

        let d = PyDict::new(py);
        d.set_item("stabilized_vector", out.stabilized_vector)?;
        d.set_item("drift_score", out.drift_score)?;
        d.set_item("euler_chi", out.euler_chi)?;
        d.set_item("genus", out.genus)?;
        d.set_item("beta0", out.beta0)?;
        d.set_item("beta1", out.beta1)?;
        d.set_item("energy_level", out.energy_level)?;
        d.set_item("stress_level", out.stress_level)?;
        d.set_item("drift_ema", out.drift_ema)?;
        d.set_item("drift_trend", out.drift_trend)?;
        d.set_item("topology_volatility", out.topology_volatility)?;
        d.set_item("surgery_rate", out.surgery_rate)?;
        d.set_item("surgery_total", out.surgery_total)?;
        d.set_item("baseline_ready", out.baseline_ready)?;
        d.set_item("baseline_drift", out.baseline_drift)?;
        d.set_item("level_shift", out.level_shift)?;
        d.set_item("scale_shift", out.scale_shift)?;
        d.set_item("psi", out.psi)?;
        d.set_item("embedding_shift", out.embedding_shift)?;
        d.set_item("hrm_score", out.hrm_score)?;
        Ok(d.into())
    }

    /// Export the reference baseline as a plain dict (JSON-serializable).
    pub fn export_baseline(&self, py: Python<'_>) -> PyResult<PyObject> {
        let b = self.inner.baseline_snapshot();
        let d = PyDict::new(py);
        d.set_item("target_windows", b.target_windows)?;
        d.set_item("windows_seen", b.windows_seen)?;
        d.set_item("samples", b.samples)?;
        d.set_item("emb_sum", b.emb_sum)?;
        d.set_item("emb_count", b.emb_count)?;
        d.set_item("ready", b.ready)?;
        d.set_item("mean", b.mean)?;
        d.set_item("std", b.std)?;
        d.set_item("scale", b.scale)?;
        d.set_item("bins", b.bins)?;
        d.set_item("ref_n", b.ref_n)?;
        d.set_item("embedding", b.embedding)?;
        Ok(d.into())
    }

    /// Restore a baseline previously produced by export_baseline().
    pub fn import_baseline(&mut self, state: &PyDict) -> PyResult<()> {
        fn get<'a, T: FromPyObject<'a>>(d: &'a PyDict, key: &str) -> PyResult<T> {
            match d.get_item(key)? {
                Some(v) => v.extract(),
                None => Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
            }
        }
        let snap = engine::BaselineSnapshot {
            target_windows: get(state, "target_windows")?,
            windows_seen: get(state, "windows_seen")?,
            samples: get(state, "samples")?,
            emb_sum: get(state, "emb_sum")?,
            emb_count: get(state, "emb_count")?,
            ready: get(state, "ready")?,
            mean: get(state, "mean")?,
            std: get(state, "std")?,
            scale: get(state, "scale")?,
            bins: get(state, "bins")?,
            ref_n: get(state, "ref_n")?,
            embedding: get(state, "embedding")?,
        };
        self.inner
            .restore_baseline(snap)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    pub fn health(&self) -> String {
        "ok".to_string()
    }
}

#[pymodule]
fn phase_lock_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<DriftEngine>()?;
    Ok(())
}
