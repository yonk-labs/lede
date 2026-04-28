use lede::clean::strip_think;

#[test]
fn empty_returns_empty() {
    assert_eq!(strip_think(""), "");
}

#[test]
fn removes_single_block() {
    assert_eq!(strip_think("<think>reasoning</think>Answer."), "Answer.");
}

#[test]
fn removes_multiple_blocks() {
    let input = "<think>a</think>First.<think>b</think>Second.";
    assert_eq!(strip_think(input), "First.Second.");
}

#[test]
fn no_block_passthrough() {
    assert_eq!(strip_think("Plain text."), "Plain text.");
}

#[test]
fn trims_surrounding_whitespace() {
    assert_eq!(strip_think("   <think>x</think>   Answer.   "), "Answer.");
}

#[test]
fn multiline_block_removed_dotall() {
    let input = "<think>line1\nline2\nline3</think>Final.";
    assert_eq!(strip_think(input), "Final.");
}
