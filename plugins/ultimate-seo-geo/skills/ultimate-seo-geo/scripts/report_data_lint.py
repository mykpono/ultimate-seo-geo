#!/usr/bin/env python3
"""
Lint a report source (the JSON behind the client report set) against
references/report-template/report-template.md § 10.

The source is what render_report.py renders. Nothing but this checks that
findings and recommendations carry their fields, that every ID they point at
exists, that the blocked-by graph is acyclic, that display-only evidence never
carries a score, that opportunities stay out of the severity list, and that an
absence claim is only made from a complete inventory.

Stdlib only. Exit 0 when clean, 1 on errors (or on warnings with --strict),
2 on usage errors.

Usage:
    python scripts/report_data_lint.py source.json
    python scripts/report_data_lint.py source.json --json --strict
"""

import argparse
import json
import re
import sys

SCHEMA_VERSION = 1

SEVERITIES = ("critical", "high", "medium", "low", "info")
KINDS = ("defect", "risk", "opportunity", "keep")
CONFIDENCE = ("Confirmed", "Likely", "Hypothesis")
EVIDENCE_STATUS = ("weighted", "display_only", "measured", "sampled", "internal", "inferred", "not_measured")
BASIS = ("Documented", "Data-backed", "Test first")
VALIDITY = ("Confirmed", "Revised", "Added", "Dropped")
TIERS = ("Free", "Review", "Gated", "Legal", "Never")
OWNER_ROLES = ("Engineering", "Content", "Product marketing", "Product", "Analytics", "Legal/InfoSec",
               "Leadership", "Sales")
LANES = ("Auto", "Assisted", "Human", "Decision")
EFFORT = ("S", "M", "L")
HORIZONS = ("now", "weeks_1_4", "weeks_3_12", "later")
TRACKS = ("A", "B", "C")
STATUS = ("planned", "in_progress", "shipped", "reverted", "read", "dropped")
SOURCE_KINDS = ("api", "export", "crawl", "sample", "internal", "documentation", "research")

FINDING_REQUIRED = ("id", "kind", "severity", "title", "observation", "evidence", "evidence_status",
                    "confidence", "falsifiability")
FINDING_CONSEQUENCE = ("impact", "fixes", "watch")   # required unless kind == keep
REC_REQUIRED = ("id", "action", "fixes", "basis", "tier", "owner_role", "lane", "effort", "done_when", "horizon")

ABSENCE = re.compile(r"\b(no|zero|missing|absent|not linked|orphan|unlinked|never links|no hub|without a hub)\b", re.I)
STRUCTURE_WORDS = re.compile(r"\b(page type|comparison pages?|alternatives pages?|hub|orphan|section|navigation|"
                             r"equity|breadcrumb)\b", re.I)
CWV_NUMBER = re.compile(r"\b(?:LCP|INP|CLS|TTFB|FCP)\b[^\n.;]{0,25}?\d", re.I)
BACKLINK_NUMBER = re.compile(r"\d[\d,.]*\s*(?:k\s*)?(?:referring domains|backlinks)\b", re.I)
ID_RE = re.compile(r"^[A-Z]{1,2}\d{1,3}[a-z]?$")


class Linter:
    def __init__(self, source: dict):
        self.src = source
        self.errors = []
        self.warnings = []

    def error(self, rule, where, message):
        self.errors.append({"rule": rule, "where": where, "message": message})

    def warn(self, rule, where, message):
        self.warnings.append({"rule": rule, "where": where, "message": message})

    # --- helpers ---------------------------------------------------------------

    def _list(self, key):
        value = self.src.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            self.error("shape", key, f'"{key}" must be a list')
            return []
        return [v for v in value if isinstance(v, dict)]

    @staticmethod
    def _ids(items):
        return {str(i.get("id")) for i in items if i.get("id")}

    def _enum(self, where, field, value, allowed, required=True):
        if value in (None, ""):
            if required:
                self.error("missing-field", where, f'"{field}" is required')
            return
        if value not in allowed:
            self.error("scale", where, f'"{field}" is "{value}"; allowed: {", ".join(allowed)}')

    # --- checks ----------------------------------------------------------------

    def check_shape(self):
        if self.src.get("schema_version") != SCHEMA_VERSION:
            self.error("schema-version", "root", f'schema_version must be {SCHEMA_VERSION}')
        meta = self.src.get("meta") or {}
        for key in ("client", "site", "prepared_for", "prepared_by", "date", "data_window", "version"):
            if not meta.get(key):
                self.error("missing-field", "meta", f'meta.{key} is required')
        if meta.get("site_type") and meta["site_type"] not in ("saas", "ecommerce", "local", "publisher", "docs", "generic"):
            self.error("scale", "meta", f'meta.site_type "{meta["site_type"]}" is not a known site type')

    def check_findings(self):
        findings = self._list("findings")
        seen = set()
        rec_ids = self._ids(self._list("recommendations"))
        finding_ids = self._ids(findings)
        complete = self._inventory_complete()
        for f in findings:
            fid = str(f.get("id") or "?")
            where = f"finding {fid}"
            if fid in seen:
                self.error("duplicate-id", where, "duplicate finding id")
            seen.add(fid)
            for key in FINDING_REQUIRED:
                if f.get(key) in (None, "", []):
                    self.error("missing-field", where, f'"{key}" is required')
            self._enum(where, "kind", f.get("kind"), KINDS)
            self._enum(where, "severity", f.get("severity"), SEVERITIES)
            self._enum(where, "confidence", f.get("confidence"), CONFIDENCE)
            self._enum(where, "evidence_status", f.get("evidence_status"), EVIDENCE_STATUS)
            kind = f.get("kind")
            if kind == "keep":
                if f.get("fixes"):
                    self.error("keep-has-fix", where, "a keep finding carries no fixes")
            else:
                for key in FINDING_CONSEQUENCE:
                    if f.get(key) in (None, "", []):
                        self.error("missing-field", where, f'"{key}" is required for a {kind} finding')
            for rid in f.get("fixes") or []:
                if rid not in rec_ids:
                    self.error("orphan-id", where, f'fixes "{rid}" is not a recommendation id')
            for key in ("depends_on", "blocks"):
                for oid in f.get(key) or []:
                    if oid not in rec_ids and oid not in finding_ids:
                        self.error("orphan-id", where, f'{key} "{oid}" is not a finding or recommendation id')
            if f.get("evidence_status") == "display_only" and f.get("score") is not None:
                self.error("display-only-scored", where, "a display-only finding never carries a score")
            if f.get("evidence_status") == "weighted" and not f.get("machine_source"):
                self.warn("weighted-without-source", where, '"weighted" evidence should name its machine_source')
            text = " ".join(str(f.get(k, "")) for k in ("title", "observation", "evidence"))
            if kind == "opportunity" and STRUCTURE_WORDS.search(text) and ABSENCE.search(text) and complete is False:
                self.error("absence-claim", where, "an absence claim about site structure needs a complete "
                                                   "sitemap or crawl (coverage.graph says the inventory is incomplete)")
            if f.get("evidence_status") == "not_measured" and (CWV_NUMBER.search(text) or BACKLINK_NUMBER.search(text)):
                self.error("unmeasured-number", where, "Core Web Vitals or backlink numbers with evidence_status not_measured")

    def check_recommendations(self):
        recs = self._list("recommendations")
        rec_ids = self._ids(recs)
        finding_ids = self._ids(self._list("findings"))
        decision_ids = self._ids(self._list("decisions"))
        seen = set()
        graph = {}
        for r in recs:
            rid = str(r.get("id") or "?")
            where = f"recommendation {rid}"
            if rid in seen:
                self.error("duplicate-id", where, "duplicate recommendation id")
            seen.add(rid)
            if not ID_RE.match(rid):
                self.warn("id-format", where, "ids look like T1, M6, C4a")
            for key in REC_REQUIRED:
                if r.get(key) in (None, "", []):
                    if key == "fixes" and r.get("status") == "dropped":
                        continue  # a dropped recommendation fixes nothing any more
                    self.error("missing-field", where, f'"{key}" is required')
            self._enum(where, "basis", r.get("basis"), BASIS)
            self._enum(where, "validity", r.get("validity"), VALIDITY, required=False)
            self._enum(where, "tier", r.get("tier"), TIERS)
            self._enum(where, "owner_role", r.get("owner_role"), OWNER_ROLES)
            self._enum(where, "lane", r.get("lane"), LANES)
            self._enum(where, "effort", r.get("effort"), EFFORT)
            self._enum(where, "horizon", r.get("horizon"), HORIZONS)
            self._enum(where, "track", r.get("track"), TRACKS, required=False)
            self._enum(where, "status", r.get("status"), STATUS, required=False)
            for fid in r.get("fixes") or []:
                if fid not in finding_ids:
                    self.error("orphan-id", where, f'fixes "{fid}" is not a finding id')
            for key in ("blocked_by", "unblocks"):
                for oid in r.get(key) or []:
                    if oid not in rec_ids:
                        self.error("orphan-id", where, f'{key} "{oid}" is not a recommendation id')
            graph[rid] = [o for o in (r.get("blocked_by") or []) if o in rec_ids]
            if r.get("lane") == "Decision":
                if not r.get("decision"):
                    self.error("decision-missing", where, "a Decision-lane recommendation names the decision it needs")
                elif r["decision"] not in decision_ids:
                    self.error("orphan-id", where, f'decision "{r["decision"]}" is not listed under decisions')
            sup = r.get("supersedes")
            if sup is not None:
                if not isinstance(sup, dict) or not sup.get("check") or not sup.get("reason"):
                    self.error("supersedes-shape", where, 'supersedes needs {"check", "finding_id", "reason"}')
            if r.get("validity") == "Dropped" and r.get("status") != "dropped":
                self.error("dropped-status", where, 'a Dropped recommendation has status "dropped"')
        cycle = self._find_cycle(graph)
        if cycle:
            self.error("dependency-cycle", "recommendations", "blocked_by cycle: " + " -> ".join(cycle))

    @staticmethod
    def _find_cycle(graph):
        WHITE, GREY, BLACK = 0, 1, 2
        colour = dict.fromkeys(graph, WHITE)
        stack = []

        def visit(node):
            colour[node] = GREY
            stack.append(node)
            for nxt in graph.get(node, []):
                if colour.get(nxt, WHITE) == GREY:
                    return stack[stack.index(nxt):] + [nxt]
                if colour.get(nxt, WHITE) == WHITE:
                    found = visit(nxt)
                    if found:
                        return found
            stack.pop()
            colour[node] = BLACK
            return None

        for node in graph:
            if colour[node] == WHITE:
                found = visit(node)
                if found:
                    return found
        return None

    def check_coverage(self):
        cov = self.src.get("coverage")
        if not isinstance(cov, dict):
            self.error("missing-field", "coverage", "coverage section is required")
            return
        for key in ("sources", "not_examined", "out_of_scope", "assumptions"):
            if not isinstance(cov.get(key), list):
                self.error("missing-field", "coverage", f'coverage.{key} must be a list')
        for s in cov.get("sources") or []:
            if not isinstance(s, dict):
                continue
            where = f'source {s.get("key", "?")}'
            for key in ("key", "name", "kind", "status"):
                if not s.get(key):
                    self.error("missing-field", where, f'"{key}" is required')
            self._enum(where, "kind", s.get("kind"), SOURCE_KINDS)
            self._enum(where, "status", s.get("status"), EVIDENCE_STATUS)
        for n in cov.get("not_examined") or []:
            if isinstance(n, dict) and not n.get("reason"):
                self.error("missing-field", f'not_examined {n.get("name", "?")}', "each not-examined item states a reason")
        if self._inventory_complete() is None and self.src.get("findings"):
            self.warn("no-graph", "coverage", "coverage.graph absent: no completeness verdict; absence claims cannot be checked")

    def _inventory_complete(self):
        graph = (self.src.get("coverage") or {}).get("graph")
        if not isinstance(graph, dict):
            return None
        sm = graph.get("sitemap") or {}
        cr = graph.get("crawl") or {}
        return bool(sm.get("complete")) or bool(cr.get("complete"))

    def check_score(self):
        score = self.src.get("health_score")
        if score is None:
            return
        if not isinstance(score, dict):
            self.error("score-shape", "health_score", 'health_score is {"overall", "source", ...} or absent')
            return
        if score.get("overall") is not None and not str(score.get("source", "")).startswith("generate_report.py"):
            self.error("score-source", "health_score", "a /100 needs source generate_report.py; otherwise omit overall")

    def check_decisions(self):
        for d in self._list("decisions"):
            where = f'decision {d.get("id", "?")}'
            for key in ("id", "question", "owner_role"):
                if not d.get(key):
                    self.error("missing-field", where, f'"{key}" is required')
            self._enum(where, "owner_role", d.get("owner_role"), OWNER_ROLES, required=False)

    def run(self):
        self.check_shape()
        self.check_findings()
        self.check_recommendations()
        self.check_coverage()
        self.check_score()
        self.check_decisions()
        return {"errors": self.errors, "warnings": self.warnings,
                "findings": len(self._list("findings")), "recommendations": len(self._list("recommendations"))}


def lint(source: dict) -> dict:
    return Linter(source).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lint a report source against report-template.md § 10")
    parser.add_argument("source", help="report source JSON")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    args = parser.parse_args(argv)
    try:
        with open(args.source, encoding="utf-8") as fh:
            source = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"cannot read {args.source}: {exc}"}) if args.json else f"error: cannot read {args.source}: {exc}")
        return 2
    if not isinstance(source, dict):
        print("error: the source must be a JSON object")
        return 2
    result = lint(source)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for e in result["errors"]:
            print(f"error   [{e['rule']}] {e['where']}: {e['message']}")
        for w in result["warnings"]:
            print(f"warning [{w['rule']}] {w['where']}: {w['message']}")
        print(f"{len(result['errors'])} error(s), {len(result['warnings'])} warning(s); "
              f"{result['findings']} findings, {result['recommendations']} recommendations")
    if result["errors"] or (args.strict and result["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
