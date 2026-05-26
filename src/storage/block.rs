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
use crate::model::{Feed,};

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

}
