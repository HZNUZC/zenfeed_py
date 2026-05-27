mod chunk;
mod inverted_index;
mod primary_index;
mod vector_index;
mod counter;

use std::collections::{HashMap, HashSet, hash_map::Entry};
use chunk::Chunk;
use inverted_index::InvertedIndex;
use primary_index::PrimaryIndex;
use vector_index::VectorIndex;
use counter::Counter;
use crate::model::{Feed, Labels};

enum BlockStatus {
    Hot,
    Cold,
}

struct Block {

    // 计数器，用于分配行号
    counter: Counter,

    // 存储单元及索引
    chunks: HashMap<String, chunk::Chunk>,
    primary_index: primary_index::PrimaryIndex,
    inverted_index: HashMap<String, inverted_index::InvertedIndex>,
    vector_index: vector_index::VectorIndex,

    // 时间范围
    time_span: (i64, i64),

    // 活跃状态
    status: BlockStatus,

}

impl Block {
    
    fn new() -> Block { Block { counter: Counter::new(), chunks: HashMap::new(), primary_index: PrimaryIndex::new(), inverted_index: HashMap::new(), vector_index: VectorIndex::new(), time_span: (0, 0), status: BlockStatus::Hot } }

    fn append(&mut self, feed: Feed, vector: Vec<f32>) {

        // step 1: 先拿到行号，拆分feed，并构造一个用于后续补新chunk的vec
        let line = self.counter.get_line();
        let feed_id = feed.id;
        let feed_labels = feed.labels;
        let feed_time = feed.time;
        
        let mut vals = Vec::new();
        loop {
            if line == 0 {
                break;
            }
            if vals.len() >= line - 1 {
                break;
            }
            vals.push("".to_string());
        };

        // step 2: 写入PrimaryIndex
        self.primary_index.write(feed_id, line);

        // step 3: 遍历feed标签，创建&插入chunk
        let keys: HashSet<String> = self.chunks.keys().cloned().collect();
        let mut label_keys: HashSet<String> = HashSet::new();
        feed_labels.inner.iter().for_each(|item| {label_keys.insert(item.0.clone());});
        for i in keys.difference(&label_keys) {
            self.chunks.get_mut(i).unwrap().write("".to_string());
        }

        for label in feed_labels.inner {
            
            // 复制一份key
            let key_copy = label.0.clone();
            let val_copy = label.1.clone();

            // 创建chunk
            match self.chunks.entry(label.0) {
                
                Entry::Occupied(mut e) => { 
                    e.get_mut().write(label.1);
                },
                
                // 插入一个新chunk
                Entry::Vacant(e) => {
                    // 复制一份vals
                    let mut vals_copy = vals.clone();

                    vals_copy.push(label.1);
                    e.insert(Chunk::from(vals_copy));
                },

            }

            // 写入InvertedIndex
            match self.inverted_index.entry(key_copy) {

                Entry::Occupied(mut e) => { 
                    e.get_mut().write(val_copy, feed_id);
                },
                
                // 创建一个新的Index
                Entry::Vacant(e) => { 
                    let map = HashMap::from([(val_copy, vec![feed_id])]);
                    e.insert(InvertedIndex::from(map));
                },

            }

        }

        // step 4: 有向量存向量
        if vector.len() != 0 {
            self.vector_index.write(feed_id, vector);
        }

    }

    fn query(&self, f: Option<(&str, Option<&[&str]>)>, vector: Option<Vec<f32>>, limit: usize, mode: bool) -> Option<Vec<(Option<i32>, u64)>> {
        
        let mut result: Vec<(Option<i32>, u64)> = Vec::new();

        if f == None && vector == None {
            return None;
        }

        let mut v_res = Vec::new();
        if let Some(v) = vector {
            if let Some(v_r) = self.vector_index.search(v, None) {
                v_res = v_r;
            }
        }

        let mut f_res: Vec<u64> = Vec::new();
        if let Some(filt) = f {
            match self.inverted_index.get(filt.0) {
                Some(ff) => { 
                    if let Some(r) = filt.1 {
                        f_res = ff.filter_by_equal(r, mode);
                    } else {
                        f_res = ff.filter_by_equal(&[], false);
                    }
                },
                None => {},
            }
        }

        if v_res.len() == 0 && f_res.len() == 0 {
            return None;
        }

        let v_set: HashSet<u64> = v_res.iter().cloned().map(|val| val.0).collect();
        let f_set: HashSet<u64> = f_res.iter().copied().collect();
        let res_set: HashSet<u64>;

        if v_res.len() != 0 && f_res.len() != 0 {
            res_set = v_set.intersection(&f_set).copied().collect();
            for i in v_res {
                if res_set.contains(&i.0) {
                    result.push((Some(i.1), i.0));
                }
            }
        } else {
            for i in v_res {
                result.push((Some(i.1), i.0));
            }
            for i in f_res {
                    result.push((None, i));
            }
        }

        result.truncate(limit);
        Some(result)

    }

    fn read(&self, ids: &[u64]) -> Vec<Labels> {

        let lines = self.primary_index.read_slice(ids);
        
        let mut labels: Vec<Labels> = Vec::new();
        for line in lines {
            let mut label = Labels::new();
            self.chunks.iter().for_each(|c| {
                let s = c.1.read(line);
                // 只读取有效标签值
                if !s.is_empty() {
                    label.inner.push((c.0.clone(), s));
                }
            });
            label.inner.sort();
            labels.push(label);
        }

        labels

    }

}
