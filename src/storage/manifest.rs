use std::{
    collections::{BTreeMap, HashSet, btree_map::Entry},
    fs,
    io::{BufReader, BufWriter},
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::storage::block::counter::Counter;

#[derive(Serialize, Deserialize)]
pub struct Manifest {
    id_assigner: Counter,
    blocks: BTreeMap<i64, PathBuf>,
    id2key: BTreeMap<u64, i64>,

    #[serde(skip, default)]
    dirty: bool,
}

impl Manifest {

    pub fn new() -> Manifest {
        Manifest {
            id_assigner: Counter::new(),
            blocks: BTreeMap::new(),
            id2key: BTreeMap::new(),
            dirty: false,
        }
    }

    pub fn load(path: &Path) -> Result<Manifest, Box<dyn std::error::Error>> {
        let file = fs::File::open(path)?;
        let reader = BufReader::new(file);
        let m: Manifest = serde_json::from_reader(reader)?;
        Ok(m)
    }

    // 原子写：先写 .tmp，再 rename 覆盖目标文件。
    // POSIX rename 是原子的，避免半截写入导致 manifest 损坏。
    pub fn save(&mut self, path: &Path) -> Result<(), Box<dyn std::error::Error>> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let tmp = path.with_extension("json.tmp");
        {
            let file = fs::File::create(&tmp)?;
            let writer = BufWriter::new(file);
            serde_json::to_writer_pretty(writer, self)?;
        }
        fs::rename(&tmp, path)?;
        self.dirty = false;
        Ok(())
    }

    pub fn assign_id(&mut self) -> u64 {
        self.dirty = true;
        self.id_assigner.assgin() as u64
    }

    pub fn is_empty(&self) -> bool {
        self.blocks.is_empty()
    }

    pub fn first_key(&self) -> Option<i64> {
        self.blocks.keys().next().copied()
    }

    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    // 计算 feed 应该落到哪个 bucket。
    // 返回 (block 文件路径, 是否本次新建)。
    // 新建 bucket 时会自动把 path 插入 blocks 并标 dirty。
    pub fn route(&mut self, time: i64) -> (PathBuf, bool) {
        match self.blocks.entry(time) {
            Entry::Occupied(e) => (e.get().clone(), false),
            Entry::Vacant(e) => {
                let path = PathBuf::from(format!(".zenfeed/data/block_{}.json", time));
                e.insert(path.clone());
                self.dirty = true;
                (path, true)
            }
        }
    }

    pub fn val_get(&self, key: i64) -> Option<PathBuf> {
        self.blocks.get(&key).cloned()
    }

    pub fn time_filter(&self, s2e: (Option<i64>, Option<i64>)) -> HashSet<i64> {

        let mut keys: HashSet<i64> = HashSet::new();

        match s2e {
            (None, None) => {
                self.blocks.keys().for_each(|k| {keys.insert(*k);});
            },
            (Some(s), None) => {
                for b in self.blocks.range(s..) {
                    keys.insert(*b.0);
                }
            },
            (None, Some(e)) => {
                for b in self.blocks.range(..e) {
                    keys.insert(*b.0);
                }
            },
            (Some(s), Some(e)) => {
                for b in self.blocks.range(s..e) {
                    keys.insert(*b.0);
                }
            },
        }

        keys

    }

    pub fn id_key_insert(&mut self, id: u64, key: i64) {
        self.dirty = true;
        self.id2key.insert(id, key);
    }

    pub fn query_id_belonging(&self, id: u64) -> Option<i64> {
        self.id2key.get(&id).copied()
    }

}
