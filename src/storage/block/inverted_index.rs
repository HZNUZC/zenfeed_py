use std::collections::{HashMap, HashSet, hash_map::Entry};
use serde::{Deserialize, Serialize};

// SingleInvertedIndex
#[derive(Serialize, Deserialize)]
pub struct InvertedIndex {
    i_index: HashMap<String, Vec<u64>>
}

impl InvertedIndex {
    
    pub fn new() -> InvertedIndex { InvertedIndex { i_index: HashMap::new() } }

    pub fn from(map: HashMap<String, Vec<u64>>) -> InvertedIndex { InvertedIndex { i_index: map } }

    pub fn write(&mut self, label_val: String, feed_id: u64) {

        match self.i_index.entry(label_val) {
            Entry::Occupied(mut e) => { e.get_mut().push(feed_id); },
            Entry::Vacant(e) => { e.insert(vec![feed_id]); },
        }

    }

    pub fn read_a_label(&self, label_val: &str) -> Option<&[u64]>{
        
        match self.i_index.get(&label_val.to_string()) {
            None => None,
            Some(v) => Some(v.as_slice()),
        }

    }

    pub fn filter_by_equal(&self, label_vals: &[&str], mode: bool) -> Vec<u64> {

        let input: HashSet<String> = label_vals.iter().map(|i| i.to_string()).collect();

        let mut v: Vec<&String> = Vec::new();

        for i in self.i_index.keys() {
            
            if mode {
                if input.contains(i) {
                    v.push(i);
                }
                continue;
            }

            if !input.contains(i) {
                v.push(i);
            }

        }

        let mut res: Vec<Vec<u64>> = Vec::new();

        for item in v {
            match self.i_index.get(item) {
                None => {},
                Some(l) => { res.push(l.clone()); },
            }
        }
    
        res.concat()

    }

}
