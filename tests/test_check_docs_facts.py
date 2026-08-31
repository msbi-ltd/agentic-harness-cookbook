import textwrap

from scripts.check_docs_facts import check, parse_facts_table

DOC = textwrap.dedent("""
    # Some doc with a facts table

    ```facts-table
    | kind           | symbol                    | source     | expect |
    |----------------|---------------------------|------------|--------|
    | symbol-present | MAX_RETRIES               | config.py  |        |
    | symbol-absent  | DEBUG_BACKDOOR            | config.py  |        |
    | numeric        | timeout = (\\d+)          | config.py  | 30     |
    ```
""")


def _write(tmp_path, doc, source_text="MAX_RETRIES = 5\ntimeout = 30\n"):
    (tmp_path / "config.py").write_text(source_text)
    doc_path = tmp_path / "DOC.md"
    doc_path.write_text(doc)
    return doc_path


def test_all_claims_hold(tmp_path):
    doc_path = _write(tmp_path, DOC)
    code, report = check(doc_path, tmp_path)
    assert code == 0, report
    assert "held" in report


def test_false_numeric_claim_is_a_verdict(tmp_path):
    doc_path = _write(tmp_path, DOC, source_text="MAX_RETRIES = 5\ntimeout = 99\n")
    code, report = check(doc_path, tmp_path)
    assert code == 1
    assert "timeout" in report


def test_absent_symbol_that_is_actually_present_is_a_verdict(tmp_path):
    doc_path = _write(
        tmp_path, DOC, source_text="MAX_RETRIES = 5\ntimeout = 30\nDEBUG_BACKDOOR = 1\n"
    )
    code, _ = check(doc_path, tmp_path)
    assert code == 1


def test_missing_source_file_is_could_not_assess(tmp_path):
    doc_path = tmp_path / "DOC.md"
    doc_path.write_text(DOC)  # no config.py written
    code, report = check(doc_path, tmp_path)
    assert code == 2
    assert "config.py" in report


def test_missing_doc_is_could_not_assess(tmp_path):
    code, _ = check(tmp_path / "nope.md", tmp_path)
    assert code == 2


def test_malformed_row_is_could_not_assess_not_silently_dropped(tmp_path):
    bad = textwrap.dedent("""
        ```facts-table
        | kind    | symbol | source |
        |---------|--------|--------|
        | numeric | x = 1  |        |
        ```
    """)
    (tmp_path / "config.py").write_text("x = 1\n")
    doc_path = tmp_path / "DOC.md"
    doc_path.write_text(bad)
    code, report = check(doc_path, tmp_path)
    assert code == 2
    assert "column" in report or "regex" in report or "empty" in report


def test_numeric_without_capture_group_is_malformed():
    rows, malformed = parse_facts_table(
        "```facts-table\n| kind | symbol | source | expect |\n"
        "| numeric | timeout | config.py | 30 |\n```"
    )
    assert rows == []
    assert any("capture group" in m for m in malformed)


def test_no_table_is_not_an_error(tmp_path):
    doc_path = tmp_path / "DOC.md"
    doc_path.write_text("# no fenced table here\n")
    code, _ = check(doc_path, tmp_path)
    assert code == 0
