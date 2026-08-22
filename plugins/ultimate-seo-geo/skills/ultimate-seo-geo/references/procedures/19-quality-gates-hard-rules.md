> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 19. Quality Gates & Hard Rules

Global rules — apply across all sections.

### Audit Self-Evaluation Pass (Evaluator-Optimizer)

After generating any Mode 1 audit output — before delivering it — run this internal evaluation pass. The purpose is to catch quality failures before the user sees them. If any criterion fails, revise before responding.

| # | Criterion | Pass Signal | Fail Action |
|---|---|---|---|
| 1 | Every Critical and High finding has an **Evidence** field from actual script output or verifiable page observation | Evidence: present on each | Add evidence or downgrade severity to Medium |
| 2 | No fabricated metrics | PSI/CrUX/LCP/CLS/INP numbers only appear if `pagespeed.py` returned JSON | Strip invented numbers; replace with "could not retrieve — verify at pagespeed.web.dev" |
| 3 | Health Score is supported by findings distribution | Critical = −15, High = −8, Medium = −3, Low = −1 applied | Recalculate or note discrepancy |
| 4 | Structured format used on every finding | Finding / Evidence / Impact / Fix / Confidence / Falsifiability / Leading Indicator all present. Critical and High findings also include First-Principle Observation and Dependency. | Add missing fields; see `references/thinking-framework.md` |
| 5 | No duplicate findings | Run `finding_verifier.py` if available; manually check if not | Merge duplicates before scoring |
| 6 | Scope respected | Full audit only if user confirmed they own the site; Competitive Mode labeled "External Observation Only" | Re-label or scope down |
| 7 | Fix directives are actionable | Each fix names the specific element, file, or page to change | Rewrite vague fixes ("improve content") with exact instructions |
| 8 | No YMYL-sensitive schema without verified credentials | Never recommend MedicalWebPage, MedicalCondition, LegalService, FinancialProduct, or similar authority-claiming schema unless the site has verified professional credentials (licensed practitioners, published medical reviewers). Suggesting these without credentials risks manual action for misleading structured data. | Remove the recommendation; suggest safer alternatives (Article, WebPage, FAQPage) |
| 9 | No low-value mass changes | Never recommend touching 10+ pages for changes with zero ranking impact (e.g., removing `keywords` meta tags, cosmetic HTML cleanup). Wastes effort and introduces deployment risk. | Remove or downgrade to informational note |
| 10 | No recommending removal of valid schema | Never recommend removing structured data just because one search engine stopped showing rich results for it (e.g., HowTo). Only recommend removing truly retired types no longer processed at all. | Change "remove" to "keep — no rich results but still valid" |
| 10b | No removing FAQ *content* over the rich-result retirement | Rule 10 protects the FAQPage *markup*; this protects the prose. Never recommend deleting, trimming, or consolidating FAQ content **on the grounds that Google withdrew FAQ rich results (May 7, 2026)**. The SERP feature ended; the content still answers user questions and still feeds AI citation (§ 3). **Carve-out:** quality-based pruning is untouched — § 6 may still recommend cutting FAQ blocks that are thin, duplicated, or keyword-stuffed, and `references/ai-generated-content-artifacts.md` may still flag an FAQ answer block that does not stand alone. The test is the *stated reason*: "remove because rich results are gone" is barred, "remove because this answer is thin or duplicated" is allowed. | Restate the recommendation on quality grounds with evidence, or withdraw it |
| 10c | No recommending tactics whose purpose is to manipulate AI answers | On 2026-05-15 Google rewrote its spam policy definition to cover *"attempting to manipulate generative AI responses in Google Search."* Buying or placing citations, seeding recommendation-poisoning listicles, and coordinated posting aimed at capturing an AI citation are now spam, carrying the same penalties as older tactics — demotion, manual action, or deindexing. The June 24 and August 18–21, 2026 spam updates are enforcement passes against it. **Carve-out:** genuine participation and genuine content are untouched. § 3's Quora, Reddit, YouTube and Wikipedia playbooks remain fully in scope, as does original research, and so does earning citations by being the best answer. **The test is the stated purpose, not the channel**: "answer this community's question well, and link the source" is allowed; "post in these threads so the AI cites us" is barred. The same action can pass or fail depending on why it is being recommended. | Withdraw the tactic, or restate it as a genuine contribution with the citation framed as a possible outcome rather than the goal |
| 11 | High-Risk deliverables withheld until confirmation | robots.txt, redirect maps, noindex directives, canonical overrides, and hreflang changes must NOT appear as code/file output before the user explicitly confirms. The response should describe the change and its consequences in plain language only. | Remove the code block; replace with a plain-language description and a confirmation prompt |
| 12 | Assumptions explicitly surfaced | An **Assumptions Audit** section lists every assumption the audit relies on (e.g., "homepage represents site quality", "CMS is server-rendered", "no recent algorithm penalty"). The user can reject or correct any assumption before acting on findings. | Add the section; revise findings that depend on unvalidated assumptions |
| 13 | Every recommendation is falsifiable | Each finding includes a **Falsifiability** field stating what evidence would prove the recommendation wrong. Unfalsifiable recommendations are opinion, not guidance. | Add falsifiability statement or demote to informational note |
| 14 | Mode 2 plans use dependency sequencing | Action items include **Blocked By** and **Unblocks** columns. Plan is topologically sorted — no action scheduled before its blockers. | Reorder the plan; add missing dependency fields |

This pattern is adapted from Anthropic's [Evaluator-Optimizer workflow](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents) — one pass generates, a second pass evaluates before output reaches the user.

**Retired schema (safe to remove)** — Google no longer processes these types at all: SpecialAnnouncement (July 2025), ClaimReview (June 2025), VehicleListing (June 2025), EstimatedSalary (June 2025), LearningVideo (June 2025), EnergyConsumptionDetails (replaced by Certification, April 2025), CourseInfo (June 2025). Note: Dataset is NOT discontinued — it is consumed by Dataset Search, just not by general Google Search (clarified November 5, 2025). Practice Problem is likewise NOT a removable type: its markup is `@type: Quiz`, a still-valid schema.org type — see the next paragraph.

**Rich results removed but schema still valid (do NOT recommend removal)** — HowTo (Sept 2023), FAQPage (May 7, 2026), and Quiz (practice problem feature, January 2026): Google no longer shows rich results for these types, but the schema is still valid structured data. HowTo helps Bing (which still renders HowTo rich results) and AI systems. FAQPage still provides signal to non-Google AI systems. Use **QAPage** for genuine user Q&A pages (not as a "FAQ replacement"). Never recommend removing valid schema just because one search engine stopped displaying rich results for it.

**INP not FID** — FID removed from Chrome's field-data tools (CrUX API, PageSpeed Insights) on September 9, 2024. Lighthouse is a lab tool and never reported FID. Referencing FID confuses users and dates the audit.

**Back-button hijacking** — Google spam policy. Sites that manipulate browser back-button behavior (preventing users from returning to search results) risk manual action. Check for JavaScript `history.pushState` abuse or redirect loops on back navigation.

**Mobile-first is complete** — Mobile Googlebot for ALL sites since July 5, 2024.

**E-E-A-T is universal** — All competitive queries, December 2025.

**AI citation ≠ ranking** — 85% of pages ChatGPT retrieves are never cited. Being retrieved is necessary but not sufficient.

**Mentions > Backlinks for AI** — 0.664 vs. 0.218 correlation. Brand mentions on third-party platforms matter more than link building for AI citation.

**Paid links risk manual action** — violates Google's spam policy. Recommend earning links through content quality instead.

**Fake reviews risk GBP suspension** — Google actively detects fake review patterns. A suspended profile loses all local visibility.

**Programmatic guardrails** — Warn at 100+ pages; hard stop at 500+ or <30% unique content. Google's March 2024 Core Update specifically targets thin scaled content.

**Blocking AI crawlers harms GEO** — Blocking OAI-SearchBot/PerplexityBot removes the site from AI search results entirely.

**GPTBot ≠ training only** — Blocking it also limits ChatGPT Search citation. Users who block GPTBot expecting only training-opt-out lose live search visibility.

