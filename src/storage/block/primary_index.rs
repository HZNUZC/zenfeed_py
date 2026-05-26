use std::collections::HashMap;

pub struct PrimaryIndex {
    p_index: HashMap<u64, usize>
}

impl PrimaryIndex {
    
    pub fn new() -> PrimaryIndex { PrimaryIndex { p_index: HashMap::new() } }

    pub fn write(&mut self, feed_id: u64, line: usize) {
        self.p_index.insert(feed_id, line);
    }

    pub fn read(&self, feed_id: u64) -> Option<usize> {
        self.p_index.get(&feed_id).copied()
    }

}