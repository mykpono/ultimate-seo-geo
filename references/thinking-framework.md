# 10-Principle Thinking Framework

## PERCEIVE → ANALYZE → VALIDATE → ACT

A structured reasoning methodology applied to every SEO/GEO recommendation. Ensures findings are grounded in first-principle observations, not pattern-matching heuristics.

---

## Phase 1: PERCEIVE

Observe the raw signals before interpreting them. Separate data from assumptions.

| # | Principle | Application |
|---|-----------|-------------|
| P1 | **Observe before concluding** | Record what the page/site actually shows — HTML source, headers, schema, rendered DOM — before diagnosing issues. |
| P2 | **Distinguish signal from noise** | Not every deviation from "best practice" is a problem. A missing meta description on a page ranking #1 is noise, not signal. |
| P3 | **Quantify where possible** | Prefer measurable signals (LCP = 4.2s, 3/10 pages have schema) over qualitative judgments ("the site feels slow"). |

## Phase 2: ANALYZE

Apply structured reasoning to the observed signals.

| # | Principle | Application |
|---|-----------|-------------|
| A1 | **First-principle observation** | For each finding, state the raw observation that triggered it. What specific element, metric, or absence did you see? Trace the recommendation back to an observable fact, not a checklist item. |
| A2 | **Dependency relationship** | Map how this finding connects to others. Does fixing X unblock Y? Does Z make this finding irrelevant? Every recommendation exists in a graph, not a flat list. |
| A3 | **Causal vs. correlational** | Distinguish between "this causes ranking loss" (confirmed mechanism) and "sites that rank well tend to have this" (correlation only). Label accordingly. |

## Phase 3: VALIDATE

Challenge every recommendation before including it.

| # | Principle | Application |
|---|-----------|-------------|
| V1 | **Falsifiability check** | Define what evidence would prove the recommendation wrong. If no conceivable evidence could disprove it, the recommendation is unfalsifiable opinion, not actionable guidance. |
| V2 | **Leading indicator** | Identify what metric or signal to monitor after implementation. If you can't name a measurable leading indicator, the recommendation lacks accountability. |

## Phase 4: ACT

Structure the output for maximum implementation velocity.

| # | Principle | Application |
|---|-----------|-------------|
| T1 | **Specificity over generality** | Name the exact page, element, file, or configuration. "Improve content quality" fails; "Add author bio with credentials to /blog/therapy-guide" passes. |
| T2 | **Sequence by dependency** | Order actions so that prerequisite fixes come first. Don't recommend "submit sitemap" before "fix canonical conflicts that would corrupt the sitemap." |

---

## Applying the Framework to Findings

Every recommendation produced under this framework carries four fields beyond the standard Finding format:

| Field | Question It Answers |
|-------|-------------------|
| **First-Principle Observation** | What raw, observable fact triggered this recommendation? |
| **Dependency Relationship** | What other findings does this block, enable, or depend on? |
| **Falsifiability** | What evidence would prove this recommendation wrong or unnecessary? |
| **Leading Indicator** | What metric should improve within 2–8 weeks if the fix works? |

### Example

```
Finding: Missing author attribution on all blog posts
Evidence: 12/12 blog posts lack byline, author schema, or /about link
Impact: Weak E-E-A-T signal; AI engines cannot attribute expertise → lower citation probability
Fix: Add visible author name + link to author bio page on each post; add Person schema with sameAs

First-Principle Observation: Raw HTML of /blog/* pages contains no <author>, rel="author",
  Person schema, or visible byline text in any inspected element.
Dependency Relationship: Blocks "improve E-E-A-T score" (§6). Enables Person schema (§5)
  once author pages exist. Independent of technical fixes.
Falsifiability: If posts rank and get cited without attribution, author signals are not
  a factor for this site's niche. Monitor for 60 days post-implementation.
Leading Indicator: AI citation rate for blog content (check Perplexity/ChatGPT monthly);
  GSC impressions for blog queries within 4–8 weeks.

Confidence: Confirmed
```

---

## When to Apply

- **Full audits (Mode 1):** Apply to all Critical and High findings. Medium findings get abbreviated treatment (Falsifiability + Leading Indicator only).
- **Scoped tasks:** Apply to findings in the scoped area.
- **Mode 2 plans:** Dependency Relationship field drives the dependency-graph action plan sequencing.
- **Mode 3 execute:** Leading Indicator field defines the verification metric post-implementation.
