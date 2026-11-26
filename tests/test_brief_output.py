"""scripts/brief.py: run one audit script, keep its full output in a file, print a short view.

The short view exists so an agent does not read megabytes (site_graph.py
--json) or every link (internal_links.py, broken_links.py) when it needs a
score and the first few issues. What matters: every cut says what it cut,
records keep their fields, the full output is saved unchanged, the script's
exit code passes through, and only scripts in scripts/ can be run.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import brief  # noqa: E402


def test_long_lists_are_cut_with_a_count_of_what_was_left_out():
    out = brief.compact({"issues": [f"issue {i}" for i in range(20)]}, max_items=3)
    assert out["issues"] == ["issue 0", "issue 1", "issue 2", "… 17 more items"]


def test_long_strings_say_how_much_was_cut():
    out = brief.compact("x" * 500, max_chars=100)
    assert out.startswith("x" * 100) and out.endswith("[400 more chars]")


def test_url_keyed_maps_are_cut_like_lists_but_records_keep_every_field():
    pages = {f"https://ex.com/p{i}": {"status": 200} for i in range(30)}
    record = {f"field_{i}": i for i in range(25)}
    out = brief.compact({"pages": pages, "summary": record}, max_items=5)

    assert len(out["pages"]) == 6 and out["pages"]["…"] == "25 more keys"
    assert out["summary"] == record


def test_a_very_wide_dict_is_cut_even_without_url_keys():
    wide = {f"k{i}": i for i in range(brief.MAX_RECORD_KEYS + 5)}
    out = brief.compact(wide, max_items=4)
    assert out["…"] == f"{brief.MAX_RECORD_KEYS + 1} more keys"


def test_deep_nesting_folds_with_a_size_note():
    deep = {"a": {"b": {"c": {"d": [1, 2, 3]}}}}
    assert brief.compact(deep, max_depth=3) == {"a": {"b": {"c": "{… 1 keys}"}}}


def test_scalars_and_small_values_pass_through_unchanged():
    value = {"score": 87, "ok": True, "missing": None, "issues": ["one"]}
    assert brief.compact(value) == value


def test_text_output_keeps_head_and_tail():
    text = "\n".join(f"line {i}" for i in range(200))
    out = brief.compact_text(text, head=3, tail=2)
    assert out.splitlines() == ["line 0", "line 1", "line 2", "… 195 lines left out …", "line 198", "line 199"]


@pytest.fixture
def fake_script(tmp_path, monkeypatch):
    """A script in a stand-in scripts/ directory, so no network is touched."""
    monkeypatch.setattr(brief, "SCRIPTS_DIR", str(tmp_path))

    def make(name, body):
        (tmp_path / name).write_text(body, encoding="utf-8")
        return name
    return make


def test_full_output_is_saved_unchanged_and_the_view_is_short(fake_script, tmp_path, capsys):
    payload = {"score": 40, "issues": [f"issue {i}" for i in range(50)]}
    name = fake_script("fake_check.py", f"import json\nprint(json.dumps({payload!r}))\n")
    save = tmp_path / "out" / "full.json"

    code = brief.main(["--max-items", "2", "--save", str(save), name])

    assert code == 0
    assert json.loads(save.read_text()) == payload
    captured = capsys.readouterr()
    shown = json.loads(captured.out)
    assert shown["score"] == 40 and shown["issues"][-1] == "… 48 more items"
    assert "full output in" in captured.err and str(save) in captured.err


def test_the_scripts_exit_code_passes_through(fake_script, tmp_path):
    name = fake_script("failing_check.py", "import sys\nprint('{}')\nsys.exit(2)\n")
    assert brief.main(["--save", str(tmp_path / "f.out"), name]) == 2


def test_arguments_reach_the_script_unchanged(fake_script, tmp_path, capsys):
    name = fake_script("echo_args.py", "import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
    brief.main(["--save", str(tmp_path / "f.out"), name, "https://ex.com/", "--json", "--max-pages", "5"])
    assert json.loads(capsys.readouterr().out) == ["https://ex.com/", "--json", "--max-pages", "5"]


@pytest.mark.parametrize("name", ["../evil.py", "/bin/sh", "brief.py", "not_python.sh", "missing_script.py"])
def test_only_scripts_in_this_directory_can_be_run(name):
    with pytest.raises(SystemExit) as exit_info:
        brief.main([name])
    assert exit_info.value.code == 2


def test_every_real_script_name_is_accepted_by_the_name_rule():
    names = [n for n in os.listdir(os.path.dirname(brief.__file__)) if n.endswith(".py")]
    assert names and all(brief.SCRIPT_NAME.match(n) for n in names)
