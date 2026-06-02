mod storage;
mod model;

use pyo3::prelude::*;

#[pymodule]
fn zenfeed(m: &Bound<PyModule>) -> PyResult<()> {
    // initialize module
    m.add_class::<model::Labels>()?;
    m.add_class::<model::Feed>()?;
    m.add_class::<storage::FeedStorage>()?;
    Ok(())
}
