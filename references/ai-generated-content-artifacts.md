<!-- Updated: 2026-08-12 | Review: 2027-02-12 -->

# AI-Generated Content Artifacts

**Contents:** Why this is its own reference · Severity model · Integrity artifacts · Structural artifacts · Voice artifacts · Calibrating a prose rule · What deliberately is not here

---

## Why this is its own reference

Every other content reference in this skill asks whether writing is *good*. This
one asks a narrower and more answerable question: does the writing carry
mechanical traces of having been generated rather than written?

The distinction matters because the audience for this skill publishes
LLM-drafted content. The failure mode is not thin content or weak E-E-A-T. It is
a body that renders as one giant code block because a fence never closed, or a
`TITLE:` label from the writer prompt sitting in the published article. Those
are defects with no legitimate reading, and a checklist can catch them.

The rules below come from a production pipeline that has published to five
live blogs continuously, and the hit rates are measured against its corpus of
132 published posts. Numbers are reported so they can be argued with. Where a
threshold is a judgement call it says so.

---

## Severity model

The single most important idea here, and the one that took a shipped mistake to
learn: **separate artifacts from taste.**

| Class | Severity | Toggle | Test |
|---|---|---|---|
| **Integrity artifact** | error | never | Is there any legitimate prose in which this appears on purpose? If no, it is an error. |
| **Structural artifact** | warn | per publisher | Reliably a defect, but a deliberate house style could want it. |
| **Voice artifact** | warn | per publisher | Reasonable publishers disagree. Ships off by default for anyone who has not opted in. |

A rule that hard-blocks on a taste judgement will be disabled wholesale by the
first publisher it annoys, and then it catches nothing. Guards should warn and
offer a one-step override; reserve refusal for the cases where the output is
actually broken.

---

## Integrity artifacts (error)

No legitimate prose use. Safe to block on.

| Rule | Catches |
|---|---|
| Unclosed code fence | A fence opened and never closed, or a fence marker glued mid-line. The published page renders as one code block from that point down. |
| Meta / assistant leak | Writer-contract labels (`TITLE:`, `DESCRIPTION:`, `TAGS:`) surviving into the body, and assistant tells such as "here is your blog post" or "I hope this helps". |
| Unicode math-bold | Bold rendered with unicode math characters (𝗹𝗶𝗸𝗲 𝘁𝗵𝗶𝘀) rather than markdown. Breaks screen readers and search indexing, and no human writer types it. |
| Engagement bait | A speech-bubble emoji leading into a "so what do YOU think?" question. |

Of these, the fence check earns its keep most often. It is the one artifact
whose consequence is visible to every reader of the page.

---

## Structural artifacts (warn)

| Rule | Catches | Notes |
|---|---|---|
| Heading-dependent opener | A section whose first sentence leans on the heading for its referent: "It is..." under a heading "What X is". A heading is a summary; prose should not build off it. | See the calibration section. This rule is the cautionary tale. |
| Bare-noun heading | An H2 of two words or fewer that is not a question and not a conventional section label. "The Pipeline", "Basic Auth", "Try It". | Needs an allowlist. See below. |
| Inline-header bullets | `- **Term:** sentence` lists, the classic generated structure. | Some reference docs legitimately use this shape. |
| Bold overuse | Three or more bold spans in one paragraph, which is mechanical key-phrase bolding rather than emphasis. | |
| Answer block does not stand alone | A lead answer block that omits significant terms from the article title, so lifted out of context it does not say what it is answering. | Directly relevant to citation extraction: an answer block is only useful if it survives being quoted alone. |

**The bare-noun allowlist matters more than the rule.** With no allowlist beyond
`FAQ`, the rule fired on 13.1% of H2s and 62.9% of posts, over half of them a
single templated heading, "Common Pitfalls", which is legitimate. With the
conventional-section allowlist below it fires on 4.5% of H2s and 25% of posts,
and the survivors are the real target.

```
FAQ, FAQs, TL;DR, TLDR, Prerequisites, Requirements, Troubleshooting,
Conclusion, Summary, Next steps, Resources, References, Limitations,
Examples, Pricing, Glossary, Quick reference, Quick answer,
Common pitfalls, Getting started, Get started, See also, Changelog
```

---

## Voice artifacts (warn, off unless opted in)

These are real generated-text tells, and they are also legitimate style choices
for some publishers. Ship them off by default.

| Rule | Catches |
|---|---|
| Em-dash | Em-dashes in prose. A strong tell, and also correct punctuation, which is exactly why it is a toggle. |
| Arrow glyphs | `→ ⇒ ← 👉` standing in for words like "means" or "leads to". |
| Horizontal rules | `---` used as visual punctuation between sections instead of a heading. |
| Emoji decoration | Emoji decorating headings or bullets. |
| Contrast slop | The "not X, it's Y" flourish: a negation immediately reasserted, or a negation plus a dramatic consequence clause. |
| Banned openers | Overused sentence openers: "Here's why", "Let's dive in", "In this article". |
| Banned phrases | A per-publisher list of filler or off-voice phrasing. |

---

## Calibrating a prose rule

Any rule that judges writing should be swept over a real corpus before its
thresholds are fixed, and the hit rate reported. This is cheap to do and it is
the only thing that separates a rule that finds defects from a rule that
describes normal prose.

**Read a high hit rate as a false-positive problem, not as a discovery.** A rule
firing on a third of existing published articles is not revealing that a third
of them are broken. It is telling you the rule matches ordinary writing.

Worked example, and the reason this section exists. The heading-dependent-opener
rule shipped across a five-blog fleet with a fully green unit-test suite. It
then flagged **30% of a 132-post corpus**, most of it legitimate writing. The
tests proved the rule did what its author meant. They could not show it
generalised, because the same author wrote the examples. Retuned against the
corpus, it settled at **12%**, all true positives.

Two rules in this reference were disabled or narrowed on the same evidence:

| Rule | Measured | Decision |
|---|---|---|
| Heading-dependent opener | 30% of posts at first threshold | Retuned to 12%, all true positives |
| Bare-noun heading | 62.9% of posts with a minimal allowlist | Allowlist expanded, now 4.5% of H2s / 25% of posts |
| Answer block present | 130 of 132 posts have no answer block | Shipped **off**. It is an editorial convention, not a defect. |
| Answer block stands alone | 1 of the 2 posts that have a block | Shipped on. Self-gating: only articles that have a block are judged. |

The "answer block present" row is the useful one to sit with. On the corpus
evidence, enabling it would have put an advisory finding on 98.5% of articles
forever. The rule is not wrong. It is a convention that a publisher opts into,
and shipping a convention as a defect is how a checklist loses its credibility.

A suggested addition to the quality gates in
`procedures/19-quality-gates-hard-rules.md`: **no rule that judges writing ships
without a measured hit rate against a real corpus, and any rule above roughly
15% is presumed to be describing normal prose until shown otherwise.**

---

## What deliberately is not here

- **"Does this read like AI" as a global verdict.** Not checkable, and the
  answer changes every model release. Every rule above names a specific
  mechanical trace instead.
- **Perplexity or burstiness scoring, and AI-detector output.** Unreliable at
  the document level and worse at the passage level. A false accusation is more
  costly than a miss.
- **Word-count floors.** Covered in `content-eeat.md`, and `procedures/18-myths.md`
  is right that there is no universal minimum.
- **Per-publisher voice rules.** Banned-phrase lists and house style belong in a
  publisher's own configuration, not in a shared default.
