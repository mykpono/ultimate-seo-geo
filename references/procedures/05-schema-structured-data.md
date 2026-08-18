> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 5. Schema / Structured Data

Always use **JSON-LD** (`<script type="application/ld+json">`). Schema improves AI citation likelihood ~2.5× (Google/Microsoft, March 2025).

### Schema Audit — Step by Step

1. **Check existing schema** — Fetch page source, search `application/ld+json`. **Caveat:** `web_fetch`, `curl`, and raw HTML cannot reliably detect schema on CMS sites — many plugins (Yoast, RankMath, AIOSEO) inject JSON-LD via client-side JavaScript that won't appear in static source. If raw HTML shows no schema on a CMS site, verify with Rich Results Test (renders JS) or browser console (`document.querySelectorAll('script[type="application/ld+json"]')`) before reporting "no schema found."
2. **Validate** — Test at search.google.com/test/rich-results. Fix errors before adding new schema.
3. **Identify missing schema** — Compare to Essential Schema table below.
4. **Generate missing schema** — Use JSON-LD templates in `references/schema-types.md`.
5. **Check retired types** — See § 19. Remove truly retired schema (SpecialAnnouncement, ClaimReview, etc.). Do NOT remove HowTo or FAQPage — rich results removed but schema still valid for Bing and AI systems.
6. **FAQPage status** — Google retired FAQ rich results for ALL sites on May 7, 2026 (supersedes the Aug 2023 gov/health restriction). Do not recommend new FAQPage for Google rich results. Keep existing FAQPage. Use **QAPage** for genuine user-generated Q&A pages.
   - **Routing: not scored for Google rich results. Scored under § 3 GEO citability.** FAQPage carries no severity in this section — it is neither a defect nor a rich-result opportunity, so it does not appear on the severity ladder here. The finding is not dropped: § 3 step 3 scores the Q&A content as a Citability signal, and § 3 step 4 covers visible-HTML parity for the answer text.

### Priority Schema by Site Type

| Site Type | Essential Schema |
|---|---|
| **Publisher / Blog** | Article/BlogPosting, Person, ProfilePage (author pages), Organization, WebSite, BreadcrumbList |
| **Forum / Community** | DiscussionForumPosting, Person, Organization |
| **SaaS** | WebApplication/SoftwareApplication, Organization, WebSite |
| **E-commerce** | Product + Offer, AggregateRating, Organization, BreadcrumbList, ProductGroup (variants), OfferShippingDetails |
| **Local Business** | LocalBusiness (most specific subtype), Organization, AggregateRating |
| **Personal Site** | Person, ProfilePage, WebSite, Article |

### Validation Checklist

1. `@context` = `"https://schema.org"` (https, not http)
2. `@type` is valid and not retired (§ 19)
3. All required properties present
4. All URLs are absolute (not relative)
5. Dates in ISO 8601 (`YYYY-MM-DD`)
6. No placeholder text — all values are real, accurate data

For e-commerce schema additions (ProductGroup, Certification, OfferShippingDetails), recent schema types (2024–2026), and AEO schema (Sitelinks Searchbox, Speakable, Knowledge Panel sameAs), see `references/schema-types.md`.

→ See `references/schema-types.md` | Run `scripts/validate_schema.py`

