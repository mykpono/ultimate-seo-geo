"""check_version_sync.py must read the README version badges.

They sat at 1.16.0 from that release through 1.20.2 because the checker never
looked at them. The script works on paths relative to the working directory,
so each test runs it inside a copy of the files it reads.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_version_sync.py"
FILES = [
    "SKILL.md",
    "AGENTS.md",
    "README.md",
    ".claude-plugin/marketplace.json",
    "plugins/ultimate-seo-geo/README.md",
    "plugins/ultimate-seo-geo/.claude-plugin/plugin.json",
    "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md",
    "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/AGENTS.md",
]


def _copy_tree(tmp_path: Path) -> None:
    for rel in FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)


def _run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, capture_output=True, text=True)


def test_repo_versions_agree_including_badges(tmp_path):
    _copy_tree(tmp_path)
    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout
    assert "README.md badge" in result.stdout
    assert "plugin README.md badge" in result.stdout


def test_stale_readme_badge_fails(tmp_path):
    _copy_tree(tmp_path)
    readme = tmp_path / "plugins/ultimate-seo-geo/README.md"
    text = readme.read_text(encoding="utf-8")
    stale = re.sub(r"badge/version-[^/]*?-green", "badge/version-1.16.0-green", text, count=1)
    readme.write_text(stale, encoding="utf-8")

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "1.16.0" in result.stdout
    assert "plugin README.md badge" in result.stdout
