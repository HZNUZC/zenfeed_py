pub struct Counter {
    count: usize,
}

// 行号从零开始分配， count代表数量
impl Counter {
    
    pub fn new() -> Counter { Counter { count: 0 } }

    // 自动递增，并且返回一个行号
    pub fn get_line(&mut self) -> usize {
        self.increment();
        self.count - 1
    }

    pub fn get_count(&self) -> usize {
        self.count
    }

    fn increment(&mut self) {
        self.count += 1;
    }

}