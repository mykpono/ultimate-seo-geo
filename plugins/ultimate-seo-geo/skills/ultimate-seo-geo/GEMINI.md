# Ultimate SEO + GEO — Gemini CLI Context

This project is a comprehensive SEO and Generative Engine Optimization (GEO) skill with
35 diagnostic Python scripts, scored audit frameworks, and AI search citation optimization.

## Instructions

All instructions for this skill are in AGENTS.md (compact), SKILL.md (routing shell + guardrails), and `references/procedures/*.md` (detailed §1–§21 procedures).

@AGENTS.md

## Key Commands

```bash
# Full-site audit report (HTML default; add --format xlsx|pdf|all as needed)
python scripts/generate_report.py https://example.com --output report.html

# Install dependencies first
pip install -r requirements.txt

# Run all individual checks
bash scripts/run_individual_checks.sh https://example.com
```

## Reference Files

Domain knowledge lives in `references/`. Step-by-step audit procedures live in `references/procedures/`. Load only what you need per task — see the Routing Index in `AGENTS.md` § 0 and the procedure index in `SKILL.md`.
