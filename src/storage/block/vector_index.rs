use std::{cmp::Reverse};
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
pub struct VectorIndex {
    v_index: Vec<(u64, Vec<f32>)>
}

impl VectorIndex {
    
    pub fn new() -> VectorIndex { VectorIndex { v_index: Vec::new() } }

    pub fn write(&mut self, feed_id: u64, vector: Vec<f32>) {
        
        // 预归一化处理
        let n_vec = to_one(vector);
        
        self.v_index.push((feed_id, n_vec));

    }

    // 计算余弦相似度，返回分数列表
    pub fn search(&self, vector: Vec<f32>, limit: Option<usize>) -> Option<Vec<(u64, i32)>> {

        if self.v_index.len() == 0 {
            return None;
        }

        let mut v: Vec<(u64, i32)> = Vec::new();
        let vector = to_one(vector);

        // 遍历计算每一条feed和查询文本的余弦相似度
        for i in &self.v_index {
            v.push((i.0, (cal_cos(&i.1, &vector) * 100.0).round() as i32));
        }

        v.sort_unstable_by_key(|x| Reverse(x.1));

        if let Some(l) = limit {
            v.truncate(l);
        }

        Some(v)

    }

}

fn to_one(vector: Vec<f32>) -> Vec<f32> {

    let mut m: f32 = vector.iter().map(|f| f * f).sum();
    m = m.sqrt();
        
    let n_vec: Vec<f32> = vector.into_iter().map(|f| f / m).collect();
    
    n_vec

}

fn cal_cos(v1: &[f32], v2: &[f32]) -> f32 {

    let mut count = 0;
    let mut res: f32 = 0.0;

    while count < v1.len() {
        let mul = v1[count] * v2[count];
        res += mul;
        count += 1;
    }

    res

}