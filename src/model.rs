use pyo3::prelude::*;
use std::collections::HashMap;

#[pyclass]
#[derive(Clone)]
pub struct Feed {
    #[pyo3(get)]
    pub id: u64,

    pub labels: Labels,
    
    #[pyo3(get)]
    pub time: i64,
}

#[derive(Clone)]
#[pyclass]
pub struct Labels {
    pub inner: Vec<(String, String)>,
}

#[pymethods]
impl Feed {
    
    #[new]
    fn new(time: i64) -> Feed {
        Feed { id: 0, labels: Labels::new(), time: time }
    }

    #[staticmethod]
    fn from_dict(labels: HashMap<String, String>, time: i64) -> Feed {
        Feed { id: 0, labels: Labels::from_map(labels), time }
    }

    fn get_labels(&self) -> Option<HashMap<String, String>> {
        self.labels.map()
    }

    fn set_labels(&mut self, source: HashMap<String, String>) {
        self.labels.inner = source.into_iter().collect();
        self.labels.inner.sort(); 
    }

}

impl Feed {
    
    pub fn fs_new(id: u64, labels: Labels, time: i64) -> Feed {
        Feed { id: id, labels: labels, time: time }
    }

}

#[pymethods]
impl Labels {
    
    #[new]
    pub fn new() -> Labels { Labels { inner: Vec::new() } }

    pub fn get(&self, key: &str) -> Option<String> {
        
        let result = self.inner.binary_search_by(|item| item.0.as_str().cmp(key));
        
        match result {
            Ok(index) => return Some(self.inner[index].1.clone()),
            _ => return None,
        }

    }

    pub fn put(&mut self, key: &str, val: &str) {

        // 先用二分找到位置，直接有序插入，避免反复使用排序算法，也避免破坏数据本来的顺序状态
        let result = self.inner.binary_search_by(|item| item.0.as_str().cmp(key));

        match result {
            // 找到了，修改val
            Ok(index) => { self.inner[index].1 = val.to_string() }, 

            // 没找到的时候，二分返回应该插入的位置，直接插入
            Err(index) => {
                self.inner.insert(index, (key.to_string(), val.to_string()));
            },
        }

    }

    #[staticmethod]
    fn from_map(source: HashMap<String, String>) -> Labels {
        
        let mut new_label: Labels = Labels::new();

        // 先直接插入数据
        new_label.inner = source.into_iter().collect();

        // 再排序（元组已实现了Ord trait，并且就是按照第一个元素排序，所以直接调用sort即可）
        new_label.inner.sort();

        new_label
    
    }

    fn map(&self) -> Option<HashMap<String, String>> {

        if self.inner.len() == 0 {
            return None;
        }

        // 构造一个HashMap，并最终返回它
        let r: HashMap<String, String> = self.inner.iter().cloned().collect();

        return Some(r)

    }

    fn watch(&self) {
        
        self.inner.iter().for_each(|item| println!("{}: {}", item.0, item.1));

    }

    // 返回一个长字符串供python侧处理
    fn watch_str(&self) -> String {
        
        let s: Vec<String> = self.inner.iter().cloned().map(|(k, v)| format!("{}: {}", k, v)).collect();

        s.join(" ")

    }

}