"""action.yml and scripts/github_action.py: the GitHub Action that gates a build on an audit.

What matters: inputs become generate_report.py arguments without passing
through a shell; a quick check is never gated or reported as a Health Score;
an inconclusive gate warns by default instead of failing; the digest reaches
the job summary; and the outputs say what the summary says. No network:
the audit itself is replaced.
"""

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_report as gr  # noqa: E402
import github_action as ga  # noqa: E402

ACTION = (ROOT / "action.yml").read_text(encoding="utf-8")
EXAMPLES = sorted((ROOT / "examples" / "github-actions").glob("*.yml"))
SMOKE = ROOT / ".github" / "workflows" / "action-smoke.yml"


def args_for(**env):
    base = {"SEO_URL": "https://ex.com/", "SEO_OUTPUT_DIR": "out"}
    base.update({k: str(v) for k, v in env.items()})
    return ga.build_args(base)


# --- inputs to arguments ----------------------------------------------------------


def test_the_default_run_writes_summary_and_digest_and_no_report():
    args, paths = args_for()
    assert args[0] == "https://ex.com/"
    assert args[args.index("--json") + 1] == os.path.join("out", "summary.json")
    assert args[args.index("--digest") + 1] == os.path.join("out", "digest.md")
    assert args[args.index("--format") + 1] == "none"
    assert "--github-annotations" in args
    assert paths["report"] is None and paths["inconclusive"] == "warn"


def test_gates_and_options_are_passed_through():
    args, paths = args_for(SEO_FAIL_UNDER=70, SEO_FAIL_ON="Critical", SEO_REPORT="true",
                           SEO_DIGEST_MAX_FINDINGS=5, SEO_ANNOTATIONS="false", SEO_INCONCLUSIVE="fail")
    assert args[args.index("--fail-under") + 1] == "70"
    assert args[args.index("--fail-on") + 1] == "critical"
    assert args[args.index("--format") + 1] == "html"
    assert args[args.index("--output") + 1] == os.path.join("out", "report.html")
    assert args[args.index("--digest-max-findings") + 1] == "5"
    assert "--github-annotations" not in args
    assert paths["inconclusive"] == "fail"


def test_delay_replaces_polite_and_polite_alone_is_passed():
    assert args_for(SEO_POLITE="true", SEO_DELAY="3")[0][-3:-1] == ["--delay", "3"]
    args, _ = args_for(SEO_POLITE="true")
    assert "--polite" in args and "--delay" not in args


def test_a_missing_previous_summary_is_a_notice_not_an_error(tmp_path, capsys):
    args, _ = args_for(SEO_PREVIOUS=str(tmp_path / "none.json"))
    assert "--previous" not in args
    assert "::notice::" in capsys.readouterr().out
    prev = tmp_path / "summary.json"
    prev.write_text("{}")
    args, _ = args_for(SEO_PREVIOUS=str(prev))
    assert args[args.index("--previous") + 1] == str(prev)


@pytest.mark.parametrize("env, message", [
    ({"SEO_URL": "ex.com"}, "url must start"),
    ({"SEO_URL": "javascript:alert(1)"}, "url must start"),
    ({"SEO_QUICK": "true", "SEO_FAIL_UNDER": "70"}, "fail-under cannot be combined with quick"),
    ({"SEO_QUICK": "true", "SEO_REPORT": "true"}, "not a Health Score"),
    ({"SEO_FAIL_UNDER": "101"}, "fail-under must be"),
    ({"SEO_FAIL_UNDER": "70; rm -rf /"}, "fail-under must be"),
    ({"SEO_FAIL_ON": "info"}, "fail-on must be"),
    ({"SEO_DELAY": "31"}, "delay must be"),
    ({"SEO_DELAY": "soon"}, "delay must be"),
    ({"SEO_QUICK": "maybe"}, "must be true or false"),
    ({"SEO_INCONCLUSIVE": "ignore"}, "inconclusive must be"),
    ({"SEO_DIGEST_MAX_FINDINGS": "0"}, "digest-max-findings"),
])
def test_bad_inputs_are_refused_with_a_reason(env, message):
    full = {"SEO_URL": "https://ex.com/", **env}
    with pytest.raises(ga.InputError, match=message):
        ga.build_args(full)


def test_quick_with_fail_on_is_allowed():
    args, _ = args_for(SEO_QUICK="true", SEO_FAIL_ON="critical")
    assert "--quick" in args and "--fail-on" in args


# --- scores -----------------------------------------------------------------------


def test_the_score_output_follows_the_evidence_rule():
    assert ga.MIN_MEASURED == gr.MIN_MEASURED_FOR_GATE
    assert ga.score_text({"overall": 82, "measured_categories": 9}) == "82"
    assert ga.score_text({"overall": 82, "measured_categories": 3}) == "not scored"
    assert ga.score_text({"overall": None, "measured_categories": 9}) == "not scored"
    assert "not a Health Score" in ga.score_text({"overall": 58, "measured_categories": 13, "scope": "quick"})


# --- a whole run ------------------------------------------------------------------


def fake_audit(summary, code, digest="# Audit digest\n"):
    def call(cmd):
        args = cmd[2:]
        if summary is not None:
            Path(args[args.index("--json") + 1]).write_text(json.dumps(summary))
            Path(args[args.index("--digest") + 1]).write_text(digest)
        return code
    return call


def run_with(tmp_path, summary, code, **env):
    gh_out, step = tmp_path / "out.txt", tmp_path / "step.md"
    full = {"SEO_URL": "https://ex.com/", "SEO_OUTPUT_DIR": str(tmp_path / "rep"),
            "GITHUB_OUTPUT": str(gh_out), "GITHUB_STEP_SUMMARY": str(step), **env}
    with patch.object(ga.subprocess, "call", side_effect=fake_audit(summary, code)):
        rc = ga.run(full)
    outputs = dict(line.split("=", 1) for line in gh_out.read_text().splitlines()) if gh_out.exists() else {}
    return rc, outputs, step.read_text() if step.exists() else ""


def summary_with(result, **extra):
    return {"overall": 74, "measured_categories": 9, "gate": {"result": result, "reasons": ["why"]}, **extra}


def test_a_passing_run_sets_outputs_and_writes_the_digest(tmp_path):
    rc, outputs, step = run_with(tmp_path, summary_with("pass"), 0)
    assert rc == 0
    assert outputs["score"] == "74" and outputs["result"] == "pass" and outputs["exit-code"] == "0"
    assert outputs["summary-path"].endswith("summary.json") and outputs["report-path"] == ""
    assert step.startswith("## SEO audit: gate pass") and "# Audit digest" in step


def test_a_failed_gate_fails_the_step(tmp_path):
    rc, outputs, _ = run_with(tmp_path, summary_with("fail"), 1)
    assert rc == 1 and outputs["result"] == "fail"


def test_an_inconclusive_gate_warns_by_default(tmp_path, capsys):
    rc, outputs, _ = run_with(tmp_path, summary_with("inconclusive"), gr.EXIT_GATE_INCONCLUSIVE)
    assert rc == 0 and outputs["exit-code"] == "3"
    assert "::warning::SEO gate inconclusive" in capsys.readouterr().out


def test_an_inconclusive_gate_can_be_made_to_fail(tmp_path):
    rc, _, _ = run_with(tmp_path, summary_with("inconclusive"), 3, SEO_INCONCLUSIVE="fail")
    assert rc == 3


def test_an_audit_that_wrote_no_summary_is_an_error(tmp_path, capsys):
    rc, outputs, _ = run_with(tmp_path, None, 0)
    assert rc == ga.EXIT_BAD_INPUT and outputs["result"] == "error"
    assert "::error::" in capsys.readouterr().out


def test_bad_input_stops_before_the_audit(tmp_path):
    with patch.object(ga.subprocess, "call") as call:
        assert ga.run({"SEO_URL": "nope"}) == ga.EXIT_BAD_INPUT
    call.assert_not_called()


def test_a_huge_digest_is_cut_to_fit_the_job_summary(tmp_path):
    step = tmp_path / "step.md"
    digest = tmp_path / "d.md"
    digest.write_text("x" * (ga.STEP_SUMMARY_LIMIT + 5000))
    ga.write_step_summary({"GITHUB_STEP_SUMMARY": str(step)}, digest, "pass")
    assert len(step.read_bytes()) < 1024 * 1024 and "cut to fit" in step.read_text()


def test_output_values_stay_on_one_line(tmp_path):
    out = tmp_path / "o.txt"
    ga.write_outputs({"GITHUB_OUTPUT": str(out)}, {"score": "a\nb=c"})
    assert out.read_text() == "score=a b=c\n"


# --- action.yml and the examples --------------------------------------------------


def run_lines(text):
    """Every line of every run: block (single-line or literal block)."""
    lines, out, in_block, indent = text.splitlines(), [], False, 0
    for line in lines:
        stripped = line.lstrip()
        if in_block:
            if stripped and len(line) - len(stripped) <= indent:
                in_block = False
            else:
                out.append(line)
                continue
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
        if m:
            if m.group(2) in ("|", ">", "|-", ">-"):
                in_block, indent = True, len(m.group(1))
            else:
                out.append(m.group(2))
    return out


@pytest.mark.parametrize("path", [ROOT / "action.yml", SMOKE, *EXAMPLES], ids=lambda p: p.name)
def test_no_expression_is_pasted_into_a_shell(path):
    """${{ }} inside run: is a script-injection hole; values must arrive through env:."""
    lines = run_lines(path.read_text(encoding="utf-8"))
    assert not [line for line in lines if "${{" in line]


def test_the_run_line_reader_sees_single_and_block_scripts():
    text = "steps:\n  - run: echo ${{ inputs.a }}\n  - name: b\n    run: |\n      cp x y\n      echo ${{ github.x }}\n    env:\n      A: 1\n"
    assert run_lines(text) == ["echo ${{ inputs.a }}", "      cp x y", "      echo ${{ github.x }}"]
    assert len(run_lines(ACTION)) == 2


def test_every_input_reaches_the_script_and_every_variable_is_an_input():
    inputs = re.findall(r"^  ([a-z][a-z-]+):\n    description:", ACTION.split("\noutputs:")[0], re.M)
    env = dict(re.findall(r"^\s+(SEO_[A-Z_]+): \$\{\{ inputs\.([a-z-]+) \}\}", ACTION, re.M))
    read = set(re.findall(r'"(SEO_[A-Z_]+)"', (ROOT / "scripts" / "github_action.py").read_text()))
    assert "url" in inputs and "python-version" in inputs
    assert set(env.values()) == set(inputs) - {"python-version"}
    assert read <= set(env), f"script reads variables the action never sets: {read - set(env)}"


def test_the_action_outputs_are_the_ones_the_script_writes():
    declared = set(re.findall(r"steps\.audit\.outputs\.([a-z-]+)", ACTION))
    assert declared == {"score", "result", "summary-path", "digest-path", "report-path", "exit-code"}


def test_the_examples_use_the_released_tag_and_real_inputs():
    version = json.loads((ROOT / "plugins" / "ultimate-seo-geo" / ".claude-plugin" / "plugin.json")
                         .read_text())["version"]
    inputs = set(re.findall(r"^  ([a-z][a-z-]+):\n    description:", ACTION.split("\noutputs:")[0], re.M))
    assert EXAMPLES
    for path in EXAMPLES:
        text = path.read_text(encoding="utf-8")
        assert f"mykpono/ultimate-seo-geo@v{version}" in text, path.name
        block = text.split("uses: mykpono/ultimate-seo-geo@")[1].split("\n\n")[0]
        used = set(re.findall(r"^\s{10}([a-z][a-z-]+):", block, re.M))
        assert used and used <= inputs, (path.name, used - inputs)


def test_the_action_and_its_script_stay_out_of_the_plugin():
    plugin_scripts = ROOT / "plugins" / "ultimate-seo-geo" / "skills" / "ultimate-seo-geo" / "scripts"
    assert not (plugin_scripts / "github_action.py").exists()
