mod block;
mod manifest;

use std::{cmp::Reverse, collections::BTreeMap, path::PathBuf};
use pyo3::types::{PyAnyMethods, PyList, PyListMethods};
use pyo3::{Bound, PyRef, PyResult, pyclass, pymethods};
use block::Block;
use manifest::Manifest;

use crate::model::Feed;

const WINDOW: i64 = 90000; 

#[pyclass]
pub struct FeedStorage {

    manifest: Manifest,
    hot_block: Option<Block>,
    hot_block_key: Option<i64>,

}

#[pymethods]
impl FeedStorage {
    
    #[new]
    fn new() -> FeedStorage { 
        FeedStorage { 
            manifest: Manifest::new(),
            hot_block: None, 
            hot_block_key: None 
        } 
    }

    #[staticmethod]
    fn open() -> FeedStorage {
        FeedStorage { 
            manifest: match Manifest::load(&PathBuf::from(".zenfeed/manifest.json")) {
                Ok(m) => {m},
                _ => {Manifest::new()},
            }, 
            hot_block: None, 
            hot_block_key: None 
        }
    }

    fn append(&mut self, feeds: Bound<'_, PyList>) -> PyResult<()> {

        let mut rust_feeds: Vec<Feed> = Vec::new();

        feeds.iter().for_each(|f| {
            match f.extract::<PyRef<Feed>>() {
                Ok(fe) => { rust_feeds.push(Feed::fs_new(self.manifest.assign_id(), fe.labels.clone(), fe.time)); },
                _ => {},
            }
        });

        if rust_feeds.is_empty() {
            return Ok(());
        }

        rust_feeds.sort_unstable_by_key(|f| f.time);

        let t0: i64;
        if self.manifest.is_empty() {
            t0 = rust_feeds[0].time;    // 基准时间
        } else {
            t0 = self.manifest.first_key().unwrap();
        }

        let feed_chunks = rust_feeds.chunk_by(|a, b| feed_belong_cal(t0, a.time) == feed_belong_cal(t0, b.time) );

        for feeds in feed_chunks {

            let key = feed_belong_cal(t0, feeds[0].time);
            let (path, is_new) = self.manifest.route(key);

            // 预处理：建立从id和key的对应关系
            for fd in feeds {
                self.manifest.id_key_insert(fd.id, key);
            }
            
            if !is_new {
                
                if let Some(h) = &mut self.hot_block {
                   
                    if self.hot_block_key != Some(key) {
                       
                        h.save(&self.manifest.val_get(self.hot_block_key.unwrap()).unwrap());
                        *h = Block::load(&path).unwrap();
                        self.hot_block_key = Some(key);
                    
                    }
                    
                    for fd in feeds {
                        h.append(fd.clone(), None);
                    }

                } else {
                    
                    self.hot_block = Some(Block::load(&path).unwrap());
                    self.hot_block_key = Some(key);
                    
                    for fd in feeds {
                        self.hot_block.as_mut().unwrap().append(fd.clone(), None);
                    }

                }

                self.hot_block.as_ref().unwrap().save(&path);
            
            } else {
                
                self.hot_block = Some(Block::new());
                self.hot_block_key = Some(key);
                
                for fd in feeds {
                    self.hot_block.as_mut().unwrap().append(fd.clone(), None);
                }

                self.hot_block.as_ref().unwrap().save(&path);
            
            }

            if self.manifest.is_dirty() {
                self.manifest.save(&PathBuf::from(".zenfeed/manifest.json"));
            }
            
        }

        Ok(())

    }

    fn vector_insert(&mut self, id: u64, vector: Vec<f32>) -> bool {
        let Some(key) = self.manifest.query_id_belonging(id) else {
            return false;
        };
        let Some(path) = self.manifest.val_get(key) else {
            return false;
        };

        if self.hot_block_key != Some(key) || self.hot_block.is_none() {
            if let (Some(h), Some(h_key)) = (self.hot_block.as_ref(), self.hot_block_key) {
                if let Some(h_path) = self.manifest.val_get(h_key) {
                    if h.save(&h_path).is_err() {
                        return false;
                    }
                }
            }

            let Ok(block) = Block::load(&path) else {
                return false;
            };
            self.hot_block = Some(block);
            self.hot_block_key = Some(key);
        }

        let ok = self.hot_block.as_mut().unwrap().vector_insert(id, vector);
        if !ok {
            return false;
        }

        self.hot_block.as_ref().unwrap().save(&path).is_ok()

    }

    fn query(&mut self, f: Option<(String, Option<Vec<String>>)>, s2e: (Option<i64>, Option<i64>), mode: bool, limit: Option<usize>) -> Vec<u64> {

        let mut to_be_queried = self.manifest.time_filter(s2e);

        let mut q_result: Vec<u64> = Vec::new();

        // 构造查询参数
        let mut tmp: Vec<&str>;
        let query_args = match &f {
            Some(f) => {
                if let Some(vals) = &f.1 {
                    tmp = vals.iter().map(|val| val.as_str()).collect();
                    Some((f.0.as_str(), Some(tmp.as_slice())))
                } else {
                    Some((f.0.as_str(), None))
                }
            },
            None => {None},
        };

        // 先看当前的hot block在不在
        if let Some(h_key) = self.hot_block_key {

            if to_be_queried.contains(&h_key) {
                if let Some(r) = self.hot_block.as_ref().unwrap().query(query_args, None, limit, mode) {
                    q_result.extend(r.iter().map(|res| res.1));
                }
            }

            to_be_queried.remove(self.hot_block_key.as_ref().unwrap());
            
        }
        

        // 解决剩下的查询，遍历集合逐个加载
        // 集合中的元素来自manifest，不可能不存在
        for k in to_be_queried {

            let path = self.manifest.val_get(k).unwrap();
            
            // 按理来说，此时不应该有没有未保存的数据
            self.hot_block = Some(Block::load(&path).unwrap());
            self.hot_block_key = Some(k);

            //对于新的hot block 执行查询，并保存结果
            if let Some(r) = self.hot_block.as_ref().unwrap().query(query_args, None, limit, mode) {
                q_result.extend(r.iter().map(|res| res.1));
            }

        }

        q_result

    }

    fn vector_query(&self, vector: Vec<f32>, s2e: (Option<i64>, Option<i64>), limit: Option<usize>) -> Vec<u64> {
        let mut to_be_queried = self.manifest.time_filter(s2e);
        let mut q_result: Vec<(i32, u64)> = Vec::new();

        if let Some(h_key) = self.hot_block_key {
            if to_be_queried.contains(&h_key) {
                if let Some(h) = self.hot_block.as_ref() {
                    if let Some(r) = h.query(None, Some(vector.clone()), limit, false) {
                        q_result.extend(r.into_iter().filter_map(|res| res.0.map(|score| (score, res.1))));
                    }
                }
            }

            to_be_queried.remove(&h_key);
        }

        for k in to_be_queried {
            let Some(path) = self.manifest.val_get(k) else {
                continue;
            };
            let Ok(block) = Block::load(&path) else {
                continue;
            };

            if let Some(r) = block.query(None, Some(vector.clone()), limit, false) {
                q_result.extend(r.into_iter().filter_map(|res| res.0.map(|score| (score, res.1))));
            }
        }

        q_result.sort_unstable_by_key(|res| Reverse(res.0));

        if let Some(l) = limit {
            q_result.truncate(l);
        }

        q_result.into_iter().map(|res| res.1).collect()

    }

    fn get_feeds(&mut self, ids: Vec<u64>) -> Option<Vec<Feed>> {

        if ids.is_empty() {
            return None;
        }

        let mut id_chunks: BTreeMap<i64, Vec<u64>> = BTreeMap::new();
        for id in &ids {
            if let Some(key) = self.manifest.query_id_belonging(*id) {
                id_chunks.entry(key).or_default().push(*id);
            }
        }

        let mut feed_map: BTreeMap<u64, Feed> = BTreeMap::new();
        for (key, chunk) in id_chunks {
                
            // 直接按chunk顺序加载block了，不好优化hot block
            let path = self.manifest.val_get(key).unwrap();
            self.hot_block = Some(Block::load(&path).unwrap());
            self.hot_block_key = Some(key);
            
            let labels = self.hot_block.as_ref().unwrap().read(&chunk);
            for (id, label) in chunk.into_iter().zip(labels.into_iter()) {
                let feed_time = self.hot_block.as_ref().unwrap().read_feed_time(id).unwrap_or(key);
                feed_map.insert(id, Feed::fs_new(id, label, feed_time));
            }

        }

        let mut feeds: Vec<Feed> = Vec::new();
        for id in ids {
            if let Some(feed) = feed_map.get(&id) {
                feeds.push(feed.clone());
            }
        }

        Some(feeds)

    }

}

fn feed_belong_cal(t0: i64, t: i64) -> i64 {
    t0 + ((t - t0) / WINDOW) * WINDOW
}
