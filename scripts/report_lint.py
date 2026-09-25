#!/usr/bin/env python3
"""
Lint a written SEO audit report against the § 2 report contract.

The agent writes the final report by hand, so nothing but this checks that it
follows the template the skill documents:

- structure: title, metadata line, Health Score section, required sections
- findings: every documented field present, severity and confidence on their
  scales, each finding under the section its severity belongs to
- the score: a /100 only with a generate_report.py source, never the retired
  deduction formula; "not scored" gives a reason
- with --summary (the generate_report.py --json file): the headline score,
  category table and measured-check count match the summary, and no
  Core Web Vitals or backlink numbers appear for checks that never ran
- one action: a full audit's Executive Summary names exactly one "Next
  action:", not a list
- numbers with no source: click, impression, session and CTR figures when no
  Search Console data reached the summary, and forecasts ("+20% traffic")
  with no basis on the line, are warned about; a line that says "cannot
  compute" is the correct way to write a number the data cannot support

Stdlib only. Exit 0 when clean, 1 on errors (or on warnings with --strict),
2 on usage errors.

Usage:
    python scripts/report_lint.py report.md
    python scripts/report_lint.py report.md --summary summary.json --json
    python scripts/report_lint.py excerpt.md --excerpt
"""

import argparse
import json
import re
import sys

# Mirrors generate_report.py (SEVERITY_SCALE, CONFIDENCE_LABELS, CHECK_GROUPS,
# MIN_MEASURED_FOR_GATE). Kept here so the linter runs without the report
# pipeline's dependencies; tests/test_report_lint.py pins the two copies together.
SEVERITY_SCALE = ("critical", "high", "medium", "low", "info")
CONFIDENCE_LABELS = ("Confirmed", "Likely", "Hypothesis")
GROUP_LABELS = {
    "content": "Content quality / E-E-A-T",
    "technical": "Technical SEO",
    "on_page": "On-page SEO",
    "links": "Link authority",
    "schema": "Schema / structured data",
    "performance": "Core Web Vitals",
    "geo": "AI search readiness (GEO)",
    "images": "Images",
    "local": "Local SEO",
}
GROUP_STATUSES = ("Strong", "Needs work", "Gap", "Not measured", "Not applicable")
MIN_MEASURED = 5

# Section heading keyword -> the severity a finding under it must carry.
# None: any severity (tag views and the full list).
REQUIRED_SECTIONS = {
    "Executive Summary": None,
    "Critical": "critical",
    "High Priority": "high",
    "Medium Priority": "medium",
    "Low Priority": "low",
    "Quick Wins": None,
    "Opportunity Signals": None,
    "Assumptions Audit": None,
    "Full Findings": None,
}
SEVERITY_SECTIONS = {k: v for k, v in REQUIRED_SECTIONS.items() if v}

FIELDS = ("Finding", "Evidence", "Impact", "Fix", "Confidence", "Severity", "Falsifiability",
          "Leading Indicator", "First-Principle Observation", "Dependency")
REQUIRED_FIELDS = ("Evidence", "Impact", "Fix", "Confidence", "Severity", "Falsifiability", "Leading Indicator")
CRITICAL_HIGH_FIELDS = ("First-Principle Observation", "Dependency")

AUDIT_TITLE = re.compile(r"^# SEO Audit Report\s+[—-]\s+\S")
COMPETITIVE_TITLE = re.compile(r"^# Competitive SEO Observation\s+[—-]\s+\S")
GEO_TITLE = re.compile(r"^# GEO Audit\s+[—-]\s+\S")
SCORE_HEADING = re.compile(r"^## SEO Health Score:\s*(.*)$")
FIELD_LINE = re.compile(r"^(%s):\s*(.*)$" % "|".join(re.escape(f) for f in FIELDS))
RETIRED_FORMULA = re.compile(r"positive_signals|deficit_signals|Critical\s*[−-]15\s*×")
CWV_NUMBER = re.compile(r"\b(?:LCP|INP|CLS|TTFB|FCP)\b[^\n.;]{0,25}?\d|PageSpeed[^\n.;]{0,30}?score[^\n.;]{0,5}\d",
                        re.I)
BACKLINK_NUMBER = re.compile(r"\d[\d,.]*\s*(?:k\s*)?(?:referring domains|backlinks)\b", re.I)
# Traffic claims: a count of clicks / impressions / sessions / visits, or a CTR percentage.
TRAFFIC_NUMBER = re.compile(
    r"\b\d[\d,.]*\s*(?:k\b)?\+?\s*(?:monthly\s+|organic\s+|monthly organic\s+)?"
    r"(?:clicks?|impressions|sessions|visits|visitors)\b|\bCTR\b[^\n.;|]{0,20}?\d[\d.]*\s*%|\d[\d.]*\s*%\s*CTR\b", re.I)
# ...that are really thresholds ("fewer than 100 visits") or click depth ("3 clicks from the homepage").
TRAFFIC_EXEMPT = re.compile(
    r"(?:<|>|≤|≥|\bunder|\bover|\bbelow|\babove|at least|at most|fewer than|less than|more than|minimum|threshold)"
    r"\s*\d[\d,.]*\s*(?:k\b)?\+?\s*(?:monthly\s+|organic\s+)*(?:clicks?|impressions|sessions|visits|visitors)"
    r"|\bclicks?\s+(?:from|of|away from|deep|to reach)\b|\bwithin\s+\d+\s+clicks?\b|\bclick depth\b"
    r"|cannot compute|not measured", re.I)
# Forecasts: "increase traffic by 30%", "+15–30% CTR", "20% more clicks".
PROJECTION = re.compile(
    r"\b(?:increase|boost|lift|grow|improve|raise|gain|drive|double|recover)\w*\b[^\n.;|]{0,50}?\bby\s+\d[\d–-]*\s*%"
    r"|\+\d[\d–-]*\s*%\s*(?:more\s+)?(?:CTR|traffic|clicks|conversions|sessions|rankings?|visibility|impressions)\b"
    r"|\b\d[\d–-]*\s*%\s*more\s+(?:traffic|clicks|conversions|sessions|impressions|visitors)\b", re.I)
# A forecast that names where its number came from is sourced.
PROJECTION_BASIS = re.compile(r"\b(?:source|basis|based on|per|from (?:your|the site's|this property's)|median|measured|"
                              r"study|studies|benchmark|Search Console|GSC|GA4|cannot compute)\b", re.I)
NEXT_ACTION = re.compile(r"^Next action:\s*(.*)$", re.I)
ENUMERATED = re.compile(r"(?:^|\s)(?:\(?\d+[.)]|[a-c]\))\s+\S")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⚡]️?")
# Agents often bold field labels ("**Finding:**", "**Fix**:") or list them ("- Evidence:").
LABEL_MARKUP = re.compile(r"\*\*|__")
LIST_MARKER = re.compile(r"^[-*+]\s+")


def _clean(text: str) -> str:
    return EMOJI.sub("", text).strip()


class Linter:
    def __init__(self, text: str, summary=None, excerpt: bool = False):
        self.lines = text.splitlines()
        self.summary = summary
        self.excerpt = excerpt
        self.errors = []
        self.warnings = []
        self.findings = []
        self.kind = None
        self.score = None

    def error(self, rule: str, line, message: str):
        self.errors.append({"rule": rule, "line": line, "message": message})

    def warn(self, rule: str, line, message: str):
        self.warnings.append({"rule": rule, "line": line, "message": message})

    # --- parsing ------------------------------------------------------------------

    def _content(self):
        """Lines with their 1-based numbers, code fence markers dropped."""
        return [(n, line) for n, line in enumerate(self.lines, 1) if not line.strip().startswith("```")]

    def _parse_findings(self):
        """Collect Finding blocks.

        A block runs from a Finding: line to the next Finding: line or heading, so
        blank lines between fields do not split it. Its section is the enclosing
        "## " heading: a "### Finding 1: ..." subheading stays under "## High Priority".
        """
        section = None
        current = None
        last_field = None
        for n, raw in self._content():
            line = LIST_MARKER.sub("", LABEL_MARKUP.sub("", raw.strip()))
            if raw.startswith("#"):
                if raw.startswith("## "):
                    section = _clean(raw[3:])
                current = last_field = None
                continue
            if not line:
                last_field = None
                continue
            # "Confidence: Confirmed | Severity: High" holds two fields; a "|" inside
            # a value ("Home | Brand") does not start one.
            parts = [p.strip() for p in line.split(" | ")] if FIELD_LINE.match(line) else [line]
            matched = False
            for part in parts:
                m = FIELD_LINE.match(part)
                if not m:
                    if matched and current is not None and last_field:
                        current["fields"][last_field] += " | " + part
                    continue
                matched = True
                name, value = m.group(1), m.group(2).strip()
                if name == "Finding":
                    current = {"line": n, "section": section, "fields": {}}
                    self.findings.append(current)
                if current is not None:
                    current["fields"][name] = value
                    last_field = name
            if not matched and current is not None and last_field:
                # A wrapped line or a numbered list straight after "Fix:" belongs to that field.
                current["fields"][last_field] = (current["fields"][last_field] + " " + line).strip()

    # --- checks -------------------------------------------------------------------

    def check_title(self):
        content = self._content()
        first = next(((n, l) for n, l in content if l.strip()), (1, ""))
        if AUDIT_TITLE.match(first[1]):
            self.kind = "audit"
        elif COMPETITIVE_TITLE.match(first[1]):
            self.kind = "competitive"
        elif GEO_TITLE.match(first[1]):
            self.kind = "geo"
        else:
            self.error("title", first[0], 'The report must start with "# SEO Audit Report — <site>", '
                                           '"# GEO Audit — <site>" or "# Competitive SEO Observation — <site>".')
            return
        meta = next(((n, l) for n, l in content if n > first[0] and l.strip()), (first[0], ""))
        wanted = {
            "audit": ("Date:", "Audited Pages:", "Confidence:"),
            "geo": ("Date:", "Pages Reviewed:"),
            "competitive": ("Date:", "Pages Reviewed:", "External Observation Only"),
        }[self.kind]
        missing = [w.rstrip(":") for w in wanted if w not in meta[1]]
        if missing:
            self.error("metadata", meta[0], f"Metadata line after the title is missing: {', '.join(missing)}.")

    def check_score(self):
        content = self._content()
        heading = next(((n, SCORE_HEADING.match(l)) for n, l in content if SCORE_HEADING.match(l)), None)
        for n, line in content:
            if RETIRED_FORMULA.search(line):
                self.error("retired-formula", n, "The deduction formula is retired; the Health Score comes "
                                                 "only from generate_report.py (§ 2).")
        if self.kind in ("competitive", "geo"):
            # Competitive Mode has no score at all; a GEO audit has its own GEO Score (§ 3)
            # but never the site-wide SEO Health Score.
            for n, line in content:
                if re.search(r"\b\d{1,3}/100\b", line) and re.search(r"health score", line, re.I):
                    self.error(f"{self.kind}-score", n, "This report type carries no SEO Health Score.")
            return
        if heading is None:
            if not self.excerpt:
                self.error("score-missing", None, 'No "## SEO Health Score:" heading (a score or "not scored").')
            return
        n, m = heading
        value = m.group(1).strip()
        section = self._section_lines(n)
        scored = re.match(r"^(\d{1,3})/100\b", value)
        if scored:
            self.score = int(scored.group(1))
            if not any(re.match(r"^Source:\s*generate_report\.py\b", l.strip()) for _, l in section):
                self.error("score-source", n, 'A /100 score needs a "Source: generate_report.py — ..." line; '
                                              'without a script run the report must say "not scored".')
        elif value.lower().startswith("not scored"):
            self.score = "not scored"
            reason = re.search(r"[—-]\s*\S", value) or any(
                re.match(r"^Reason:\s*\S", l.strip()) for _, l in section)
            if not reason:
                self.error("score-reason", n, '"not scored" needs a reason ("Reason: ...").')
        else:
            self.error("score-format", n, f'Health Score must be "NN/100" or "not scored", got "{value}".')
            return
        self._check_category_table(section, scored is not None)
        self._check_against_summary(n, section)

    def _section_lines(self, start: int):
        out = []
        for n, line in self._content():
            if n <= start:
                continue
            if line.startswith("## "):
                break
            out.append((n, line))
        return out

    def _table_rows(self, section):
        rows = []
        for n, line in section:
            cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
            if cells and cells[0] not in ("Category", "") and not set(cells[0]) <= set("-: "):
                rows.append((n, cells))
        return rows

    def _check_category_table(self, section, scored: bool):
        rows = self._table_rows(section)
        if not rows:
            if not self.excerpt:
                self.error("category-table", None, "The Health Score section has no category table.")
            return
        labels = set(GROUP_LABELS.values())
        for n, cells in rows:
            cells = [LABEL_MARKUP.sub("", c).strip() for c in cells]
            if cells[0] not in labels:
                self.error("category-label", n, f'Unknown category "{cells[0]}"; use the § 2 category names.')
            status = cells[-1]
            if status not in GROUP_STATUSES:
                self.error("category-status", n, f'Status "{status}" is not one of {", ".join(GROUP_STATUSES)}.')
            if scored and len(cells) >= 4:
                m = re.match(r"^(\d{1,3})/100$", cells[1])
                if m:
                    score = int(m.group(1))
                    expected = "Strong" if score >= 80 else "Needs work" if score >= 50 else "Gap"
                    if status != expected:
                        self.error("category-status", n, f"{cells[0]}: {score}/100 is {expected}, not {status}.")

    def _check_against_summary(self, heading_line: int, section):
        if self.summary is None:
            if self.score not in (None, "not scored"):
                self.warn("unverified-score", heading_line, "No --summary given: the score and category table "
                                                            "cannot be checked against generate_report.py.")
            return
        summary = self.summary
        measured = summary.get("measured_categories") or 0
        if self.score == "not scored":
            if measured >= MIN_MEASURED:
                self.warn("score-available", heading_line, f"The summary measured {measured} weighted checks and "
                                                           f"scored {summary.get('overall')}; the report says not scored.")
            return
        if measured < MIN_MEASURED:
            self.error("score-thin", heading_line, f"The summary measured only {measured} weighted check(s) "
                                                   f"(need {MIN_MEASURED}); the report must say not scored.")
        if self.score != summary.get("overall"):
            self.error("score-mismatch", heading_line, f"Report says {self.score}/100; the summary's overall is "
                                                       f"{summary.get('overall')}.")
        groups = summary.get("group_scores")
        if not isinstance(groups, dict):
            self.error("summary-version", None, "The summary has no group_scores; regenerate it with "
                                                "generate_report.py (schema_version 2 or later).")
            return
        by_label = {g.get("label"): g for g in groups.values()}
        for n, cells in self._table_rows(section):
            group = by_label.get(cells[0])
            if group is None or len(cells) < 4:
                continue
            expected_score = "—" if group.get("score") is None else f"{group['score']}/100"
            if cells[1] not in (expected_score, "-" if group.get("score") is None else expected_score):
                self.error("category-mismatch", n, f"{cells[0]}: report says {cells[1]}, summary says {expected_score}.")
            if cells[-1] != group.get("status"):
                self.error("category-mismatch", n, f"{cells[0]}: report says {cells[-1]}, "
                                                   f"summary says {group.get('status')}.")
            share = re.match(r"^([\d.]+)%$", cells[2])
            if share and abs(float(share.group(1)) - float(group.get("share") or 0)) > 0.15:
                self.error("category-mismatch", n, f"{cells[0]}: report share {cells[2]}, "
                                                   f"summary share {group.get('share')}%.")

    def check_sections(self):
        if self.kind != "audit" or self.excerpt:
            return
        headings = [_clean(l.lstrip("#")) for _, l in self._content() if l.startswith("## ")]
        for keyword in REQUIRED_SECTIONS:
            if not any(keyword.lower() in h.lower() for h in headings):
                self.error("section-missing", None, f'Missing section "## {keyword}".')

    def check_findings(self):
        if self.kind == "audit" and not self.findings and not self.excerpt:
            self.warn("no-findings", None, "No findings in Finding: / Evidence: / ... format.")
        seen = {}
        for f in self.findings:
            fields, n = f["fields"], f["line"]
            label = fields.get("Finding", "")[:60]
            if self.kind == "competitive":
                for name in ("Evidence", "Impact", "Fix", "Confidence"):
                    if not fields.get(name):
                        self.error("finding-field", n, f'"{label}": missing {name}.')
                continue
            severity = _clean(fields.get("Severity", "")).lower()
            if fields.get("Severity") and severity not in SEVERITY_SCALE:
                self.error("severity", n, f'"{label}": severity "{fields["Severity"]}" is not one of '
                                          f'{", ".join(s.title() for s in SEVERITY_SCALE)}.')
            # "Likely (inferred from source analysis)" is a label with its reason.
            confidence = fields.get("Confidence", "")
            if confidence and not re.match(r"^(%s)(?:$|[\s(—–:-])" % "|".join(CONFIDENCE_LABELS), confidence):
                self.error("confidence", n, f'"{label}": confidence "{confidence}" is not one of '
                                            f'{", ".join(CONFIDENCE_LABELS)}.')
            required = REQUIRED_FIELDS + (CRITICAL_HIGH_FIELDS if severity in ("critical", "high") else ())
            missing = [name for name in required if not fields.get(name)]
            if missing:
                self.error("finding-field", n, f'"{label}": missing {", ".join(missing)}.')
            section = f["section"] or ""
            expected = next((sev for key, sev in SEVERITY_SECTIONS.items() if key.lower() in section.lower()), None)
            if expected and severity in SEVERITY_SCALE and severity != expected:
                self.error("severity-section", n, f'"{label}" is {severity} but sits under "{section}".')
            if expected:
                key = re.sub(r"\W+", " ", fields.get("Finding", "").lower()).strip()
                if key in seen:
                    self.warn("duplicate", n, f'"{label}" repeats the finding at line {seen[key]}.')
                seen.setdefault(key, n)

    def check_evidence_integrity(self):
        if self.summary is None:
            unmeasured = None
        else:
            unmeasured = set(self.summary.get("unmeasured") or [])
            categories = self.summary.get("categories") or {}
            for key, value in categories.items():
                if isinstance(value, dict) and value.get("score") is None and value.get("status") in (
                        "Not measured", "Not run"):
                    unmeasured.add(key)
        rules = (("pagespeed", CWV_NUMBER, "Core Web Vitals / PageSpeed numbers", "pagespeed.py"),
                 ("link_profile", BACKLINK_NUMBER, "backlink or referring-domain counts", "link_profile.py"))
        for check, pattern, what, script in rules:
            hits = [n for n, line in self._content() if pattern.search(line)]
            if hits and unmeasured is None:
                self.warn("unverified-metric", hits[0], f"{what} on {len(hits)} line(s) cannot be verified "
                                                        f"without --summary; state them only if {script} ran.")
                continue
            for n in hits:
                if check in unmeasured:
                    self.error("unmeasured-metric", n, f"{what} appear, but {check} was not measured in the "
                                                       f"summary. Write \"not measured — run {script}\" instead.")

    def check_next_action(self):
        """A full audit's Executive Summary names one next action (§ 2), not a to-do list."""
        if self.kind != "audit" or self.excerpt:
            return
        content = self._content()
        start = next((n for n, l in content if l.startswith("## ") and "executive summary" in l.lower()), None)
        if start is None:
            return  # check_sections reports the missing section
        section = self._section_lines(start)
        hit = None
        for i, (n, raw) in enumerate(section):
            m = NEXT_ACTION.match(LIST_MARKER.sub("", LABEL_MARKUP.sub("", raw.strip())))
            if m:
                hit = (i, n, m.group(1).strip())
                break
        if hit is None:
            self.error("next-action", start, 'The Executive Summary needs one "Next action: <one change, the page or '
                                             'template, the finding it closes>" line.')
            return
        i, n, value = hit
        following = []
        for _, raw in section[i + 1:]:
            if not raw.strip():
                break
            following.append(raw.strip())
        listed = sum(1 for line in following if LIST_MARKER.match(line) or re.match(r"^\d+[.)]\s", line))
        if not value and not listed:
            self.error("next-action", n, '"Next action:" is empty; name the one change to make first.')
        elif len(ENUMERATED.findall(" " + value)) >= 2 or listed >= 2 or (not value and listed):
            self.error("next-action-list", n, '"Next action:" lists several actions; name one. The rest belong '
                                              "in the priority sections.")

    def check_unsourced_numbers(self):
        """Traffic figures and forecasts with nothing behind them (warnings: the lint cannot see GA4)."""
        search_console = bool((self.summary or {}).get("search_console"))
        traffic = [n for n, line in self._content()
                   if TRAFFIC_NUMBER.search(line) and not TRAFFIC_EXEMPT.search(line)]
        if traffic and not search_console:
            where = ("the summary has no Search Console data" if self.summary is not None
                     else "no --summary to check them against")
            self.warn("unverified-traffic", traffic[0],
                      f"Click / impression / session / CTR figures on {len(traffic)} line(s) (first at line {traffic[0]}), "
                      f"and {where}. State them only if Search Console or GA4 data was read; otherwise write "
                      '"cannot compute from this data" and name what would supply it.')
        for n, line in self._content():
            if PROJECTION.search(line) and not PROJECTION_BASIS.search(line):
                self.warn("unsourced-projection", n, "A forecast with no basis on the line. Name its source "
                                                     '("based on this property\'s median CTR at position 3") or '
                                                     'write "cannot compute from this data".')

    def run(self) -> dict:
        self._parse_findings()
        self.check_title()
        if self.kind:
            self.check_score()
            self.check_sections()
            self.check_findings()
            self.check_evidence_integrity()
            self.check_next_action()
            self.check_unsourced_numbers()
        by_line = lambda item: (item["line"] is None, item["line"] or 0)  # noqa: E731
        return {
            "type": self.kind,
            "score": self.score,
            "findings": len(self.findings),
            "errors": sorted(self.errors, key=by_line),
            "warnings": sorted(self.warnings, key=by_line),
        }


def lint(text: str, summary=None, excerpt: bool = False) -> dict:
    return Linter(text, summary=summary, excerpt=excerpt).run()


def _format(result: dict, path: str) -> str:
    out = []
    for level, items in (("error", result["errors"]), ("warning", result["warnings"])):
        for item in items:
            where = f"{path}:{item['line']}" if item["line"] else path
            out.append(f"{where}: {level} [{item['rule']}] {item['message']}")
    out.append(f"{len(result['errors'])} error(s), {len(result['warnings'])} warning(s); "
               f"{result['findings']} finding(s); report type: {result['type'] or 'unrecognised'}")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Lint a written SEO audit report against the § 2 report contract.")
    parser.add_argument("report", help="Markdown report file, or - for stdin")
    parser.add_argument("--summary", metavar="PATH", help="generate_report.py --json summary to check the score against")
    parser.add_argument("--excerpt", action="store_true",
                        help="Lint findings and score only; skip required sections (for partial reports and examples)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings as well as errors")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    try:
        text = sys.stdin.read() if args.report == "-" else open(args.report, encoding="utf-8").read()
    except OSError as exc:
        parser.error(f"cannot read report: {exc}")
    summary = None
    if args.summary:
        try:
            with open(args.summary, encoding="utf-8") as fh:
                summary = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read summary: {exc}")
        if not isinstance(summary, dict):
            parser.error("summary must be a JSON object")

    result = lint(text, summary=summary, excerpt=args.excerpt)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else _format(result, args.report))
    failed = result["errors"] or (args.strict and result["warnings"])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
