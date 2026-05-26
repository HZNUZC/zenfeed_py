pub struct Chunk {
    vals: Vec<String>
}

impl Chunk {
    
    pub fn new() -> Chunk { Chunk { vals: Vec::new() } }

    pub fn from(vals: Vec<String>) -> Chunk { Chunk { vals: vals } }

    pub fn read(&self, line: usize) -> String {
        self.vals[line].clone()
    }

    pub fn write(&mut self, val: String) {
        self.vals.push(val);
    }

}