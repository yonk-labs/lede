use skimr::clean::clean_text;

#[test]
fn empty_returns_empty() {
    assert_eq!(clean_text(""), "");
}

#[test]
fn strips_bold_markdown() {
    assert_eq!(clean_text("**bold** text"), "bold text");
}

#[test]
fn strips_underline_and_headers() {
    assert_eq!(clean_text("# Header\n__under__"), "header\nunder");
}

#[test]
fn removes_filler_word() {
    assert_eq!(clean_text("this is basically bad"), "this is bad");
}

#[test]
fn removes_crm_boilerplate_calendar_invite() {
    let out = clean_text("Had a call. Calendar invite sent. All good.");
    assert!(out.contains("had a call"), "got: {out:?}");
    assert!(
        !out.to_lowercase().contains("calendar invite"),
        "got: {out:?}"
    );
}

#[test]
fn lowercases_everything() {
    assert_eq!(clean_text("HELLO World"), "hello world");
}

#[test]
fn collapses_spaces() {
    assert_eq!(clean_text("too    many    spaces"), "too many spaces");
}
