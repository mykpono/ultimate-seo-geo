<!-- Updated: 2026-08-11 | Review: 2027-02-11 -->

# Schema.org Types — Status & Recommendations
## Updated: August 2026 (Schema.org v29.4)

**Contents:** Active Schema Types · Restricted Schema Types · Deprecated Schema Types · Schema Templates · Validation Checklist · Testing Tools · E-commerce Schema Additions · Recent Schema Additions · AEO Schema

Always use **JSON-LD** (`<script type="application/ld+json">`). Google's documentation explicitly recommends JSON-LD over Microdata and RDFa.

**AI Search Note:** Content with proper schema has ~2.5× higher chance of appearing in AI-generated answers (confirmed Google/Microsoft, March 2025).

---

## ACTIVE — Recommend freely

| Type | Use Case | Key Properties |
|---|---|---|
| Organization | Company info | name, url, logo, contactPoint, sameAs |
| LocalBusiness | Physical businesses | name, address, telephone, openingHours, geo, priceRange |
| SoftwareApplication | Desktop/mobile apps | name, operatingSystem, applicationCategory, offers, aggregateRating |
| WebApplication | Browser-based SaaS | name, applicationCategory, offers, browserRequirements, featureList |
| Product | Products | name, image, description, sku, brand, offers, review, certification (April 2025) |
| ProductGroup | Product variants | name, productGroupID, variesBy, hasVariant |
| Offer | Pricing | price, priceCurrency, availability, url, validFrom |
| Service | Service businesses | name, provider, areaServed, description, offers |
| Article | Blog posts, news | headline, author, datePublished, dateModified, image, publisher |
| BlogPosting | Blog content | Same as Article + blog context |
| NewsArticle | News content | Same as Article + news context |
| Review | Individual reviews | reviewRating, author, itemReviewed, reviewBody |
| AggregateRating | Rating summaries | ratingValue, reviewCount, bestRating, worstRating |
| BreadcrumbList | Navigation path | itemListElement with position, name, item |
| WebSite | Site-level | name, url, potentialAction (SearchAction for sitelinks) |
| WebPage | Page-level | name, description, datePublished, dateModified |
| Person | Author/team | name, jobTitle, url, sameAs, image, worksFor |
| ProfilePage | Author profile pages | mainEntity (Person), name, url, description, sameAs |
| ContactPage | Contact pages | name, url |
| VideoObject | Video content | name, description, thumbnailUrl, uploadDate, duration, contentUrl |
| ImageObject | Image content | contentUrl, caption, creator, copyrightHolder |
| Event | Events | name, startDate, endDate, location, organizer, offers |
| JobPosting | Job listings | title, description, datePosted, hiringOrganization, jobLocation |
| Course | Educational content | name, description, provider, hasCourseInstance |
| QAPage | Genuine user Q&A pages | mainEntity (Question + Answer), dateCreated, author |
| DiscussionForumPosting | Forum threads | headline, author, datePublished, text, url |
| LoyaltyProgram | Membership pricing | membershipPointsEarned, eligibleQuantity (added June 2025) |

---

## NO GOOGLE RICH RESULTS — Keep as AI/entity signal, don't add for Google rich results

These types no longer generate Google rich results but are still valid Schema.org markup. **Do NOT recommend removing them** — they still help Bing, AI systems, and content understanding.

| Type | Status | Since | Keep? | Notes |
|---|---|---|---|---|
| **FAQPage** | Google retired FAQ rich results for ALL sites | May 7, 2026 | **Yes — keep as AI/entity signal** | Supersedes the Aug 2023 gov/health restriction. No Google SERP feature benefit for any site. Still provides signal to non-Google AI systems. **Not scored for Google rich results — scored under § 3 GEO citability.** Use **QAPage** for genuine user Q&A pages. Tooling sunset followed in phases — see below. |
| **HowTo** | Google rich results removed | September 2023 | **Yes — keep** | Bing still renders HowTo rich results; AI systems parse it for citations; valid structured data |
| **Quiz** (practice problems) | Google retired the practice problem rich result | January 2026 | **Yes — keep** | `Quiz` is the real `@type` behind Google's "practice problem" feature (there is no `PracticeProblem`/`PracticeProblems` type — both 404 on schema.org). Still a valid schema.org type under `LearningResource`. |
| **Dataset** | Scope clarified, not retired | November 5, 2025 | **Yes — keep** | Consumed by Dataset Search, not general Google Search. Markup remains fully supported — never flag as retired. |
| **Sitelinks Search Box** | Removed from Search UI | Jan 2026 | Optional | WebSite SearchAction no longer shows in results but causes no harm |

> **Decision tree for FAQPage (post May 2026):**
> - **Adding new FAQPage for Google rich results?** → No benefit. Retired for all sites May 7, 2026.
> - **Existing FAQPage on site?** → Keep. Not scored for Google rich results; scored under § 3 GEO citability. Still aids non-Google AI systems.
> - **Genuine user Q&A page?** → Use **QAPage** (the correct type for real user-generated Q&A).
> - **Removing FAQPage?** → Do not recommend removal. Causes no harm.
>
> **FAQ tooling sunset phases.** Google removed the FAQ documentation itself on June 15, 2026, so the
> phase dates below can no longer be confirmed against Google Search Central and are recorded here from
> **secondary reporting only** (Search Engine Journal, May 2026) — treat as unverified:
> - *Reported June 2026* — FAQ search appearance filter, rich result report, and Rich Results Test support removed.
> - *Reported August 2026* — Search Console API stops returning FAQ data.
>
> Only the May 7, 2026 rich-result withdrawal is confirmed by Google's own changelog.
>
> **Status: CLOSED as unanswerable from available evidence (2026-08-23).**
>
> The reported August 2026 API sunset was investigated and **could not be confirmed or refuted**.
> Treat the phase dates above as secondary reporting permanently — not as a question awaiting an
> answer. Nothing further is pending.
>
> **What was established.** Google's changelog carries exactly two FAQ entries: **May 8, 2026**
> (deprecation notice; feature gone from Search as of May 7) and **June 15, 2026** (FAQ documentation
> removed). **Neither mentions Search Console, the Rich Results Test, or the Search Console API.**
> The June and August phase dates exist only in secondary reporting, and the primary source that
> would have carried them was deleted.
>
> **Why it cannot be settled here.** Confirming it requires an authenticated `searchAppearance`
> query against a property that earned FAQ rich results before May 7, 2026. That is a property
> requirement, not a tooling gap — no amount of work on this repo produces the data. The procedure
> is preserved below for anyone who has such a property; running it is optional, and the conclusion
> does not change until someone does.
>
> ⚠ **Known trap — do not "confirm" this by accident.** Searching Google's changelog for FAQ plus
> Search Console API returns text that reads like confirmation:
> *"we'll also be removing support for that feature in Search Console rich result reporting, the Rich
> Result Test, and the list of Search appearance filters"* and *"The Search Console API will continue
> to support the practice problem type through January 2026."*
> **Those sentences are about the practice-problem deprecation, not FAQ.** That deprecation has an
> identical phased shape (SERP feature → Search Console + Rich Results Test → API last) and
> near-identical boilerplate, so it misattributes easily — and it is the likeliest reason the
> secondary reporting states the FAQ phases so confidently. Check which feature an entry names before
> treating it as evidence. **This is the standing rule; it outlives the question.**
>
> **The procedure, if you ever have the data** — two windows, run together. The single-query framing
> is circular: whether a property *had* FAQ impressions is only answerable through the same API, and
> Search Console's FAQ search-appearance filter was itself removed in June 2026.
>
> ```bash
> # 1. Historical — did this property ever earn FAQ rich results?
> python scripts/gsc_query.py sc-domain:example.com --dimension searchAppearance \
>     --start-date 2026-01-01 --end-date 2026-05-06 --json
>
> # 2. Current — does the API still return FAQ at all?
> python scripts/gsc_query.py sc-domain:example.com --dimension searchAppearance --days 90 --json
> ```
>
> | Window 1 (historical) | Window 2 (current) | Conclusion |
> |---|---|---|
> | FAQ row present | FAQ row present | API sunset did not happen, or has not yet |
> | FAQ row present | FAQ row absent | **Sunset confirmed** for this property |
> | FAQ row absent | FAQ row absent | Ambiguous — either the property never earned FAQ results, or removal reached historical data |
> | FAQ row absent | FAQ row present | Contradictory; re-check the date range |
>
> Disambiguating row 3 is the only part that works without credentials: FAQ rich results required
> `FAQPage` markup, so a site that never carried it certainly never earned them. Run
> `python scripts/validate_schema.py saved-page.html --json` against **archived** copies of pages that
> ranked before May 2026 — markup removed since would make an eligible property look ineligible. The
> hit is the `[info]` line about the FAQ withdrawal; the output never prints the literal string
> `FAQPage`.
>
> **Actionable regardless, and the reason this matters at all**: any dashboard, BigQuery export or
> scheduled job still querying FAQ rich-result data should be checked against live responses. The
> documented failure mode is **silent nulls rather than an error** — a pipeline that "still runs" is
> not evidence the data is still arriving. This holds whether or not the sunset is ever confirmed,
> which is why closing the question costs nothing operationally.

## RETIRED — Safe to remove (no longer processed)

These types are truly retired — search engines no longer process them at all. Safe to remove, but low priority (they cause no harm if left in place).

| Type | Status | Removed | Notes |
|---|---|---|---|
| **SpecialAnnouncement** | Deprecated | July 31, 2025 | COVID-era, no longer processed |
| **ClaimReview** | Retired from rich results | June 2025 | Fact-check markup no longer generates rich results |
| **EstimatedSalary** | Retired from rich results | June 2025 | Removed |
| **LearningVideo** | Retired from rich results | June 2025 | Use VideoObject instead |
| **VehicleListing** | Retired from rich results | June 2025 | Discontinued |
| **CourseInfo** | Merged into Course | June 2025 | Use Course instead |
| **EnergyConsumptionDetails** | Replaced by Certification | April 24, 2025 | Migrate to the `Certification` type |

**Not in this table, despite common belief:** `Dataset` (scope-limited to Dataset Search, still fully
supported) and `Quiz` / "practice problems" (the rich result ended, the schema.org type did not). Both
are listed under RICH RESULTS REMOVED above — never flag either as retired.

## YMYL-SENSITIVE — Require verified credentials before recommending

**Never recommend these schema types unless the site has verified professional credentials.** Suggesting authority-claiming schema to sites without credentials risks Google manual action for misleading structured data.

| Type | Requires | Risk if Misused |
|---|---|---|
| **MedicalWebPage** | Licensed medical practitioners or published medical reviewers | Manual action for misleading health claims |
| **MedicalCondition** | Medical authority (clinic, hospital, licensed provider) | YMYL scrutiny; may hurt instead of help |
| **MedicalOrganization** | Licensed medical organization | Misleading authority claim |
| **LegalService** | Licensed legal practitioners | Misleading professional credentials |
| **FinancialProduct** | Licensed financial institution | YMYL financial authority claim |
| **Physician** | Licensed medical practitioner | False credential representation |

> **Safe alternatives for health/legal/finance content**: Use `Article`, `WebPage`, or `WebSite` with strong E-E-A-T signals in content (author bio with credentials, citations to authoritative sources, medical/legal disclaimers). These provide structured data value without claiming professional authority the site may not have.

---

## Schema Templates

### Article / BlogPosting

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "@id": "[page-url]#article",
  "headline": "[Post Title]",
  "url": "[page-url]",
  "datePublished": "[YYYY-MM-DD]",
  "dateModified": "[YYYY-MM-DD]",
  "author": {
    "@type": "Person",
    "@id": "[site-url]/#person",
    "name": "[Author Name]"
  },
  "publisher": {
    "@type": "Organization",
    "@id": "[site-url]/#organization",
    "name": "[Site Name]",
    "logo": {
      "@type": "ImageObject",
      "url": "[logo-url]"
    }
  },
  "image": {
    "@type": "ImageObject",
    "url": "[feature-image-url]"
  },
  "description": "[Meta description / excerpt]",
  "isPartOf": {
    "@type": "WebSite",
    "@id": "[site-url]/#website"
  },
  "inLanguage": "en"
}
```

### Organization

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "[site-url]/#organization",
  "name": "[Company Name]",
  "url": "[site-url]",
  "logo": {
    "@type": "ImageObject",
    "url": "[logo-url]"
  },
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "email": "[contact@email.com]"
  },
  "sameAs": [
    "[LinkedIn URL]",
    "[Twitter/X URL]",
    "[Facebook URL]",
    "[YouTube URL]"
  ]
}
```

### Person (Author/Founder)

```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "@id": "[site-url]/#person",
  "name": "[Full Name]",
  "url": "[author-page-url]",
  "jobTitle": "[Title]",
  "description": "[Brief bio with credentials]",
  "image": {
    "@type": "ImageObject",
    "url": "[headshot-url]"
  },
  "worksFor": {
    "@id": "[site-url]/#organization"
  },
  "knowsAbout": ["[Topic 1]", "[Topic 2]", "[Topic 3]"],
  "sameAs": [
    "[LinkedIn URL]",
    "[GitHub URL]",
    "[Wikipedia URL]",
    "[Twitter/X URL]",
    "[author-page-url]"
  ]
}
```

### WebSite (with SearchAction)

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": "[site-url]/#website",
  "url": "[site-url]/",
  "name": "[Site Name]",
  "description": "[Site description]",
  "inLanguage": "en",
  "publisher": { "@id": "[site-url]/#organization" }
}
```

### FAQPage (no Google rich results since May 2026; keep as AI/entity signal only)

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is [topic]?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "[Direct answer in 1-3 sentences, 50-150 words]"
      }
    },
    {
      "@type": "Question",
      "name": "[Second question]",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "[Direct answer]"
      }
    }
  ]
}
```

### BreadcrumbList

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Home", "item": "[site-url]/"},
    {"@type": "ListItem", "position": 2, "name": "[Category]", "item": "[category-url]"},
    {"@type": "ListItem", "position": 3, "name": "[Page Title]", "item": "[page-url]"}
  ]
}
```

### LocalBusiness

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "[Business Name]",
  "url": "[site-url]",
  "telephone": "[+1-555-000-0000]",
  "email": "[email]",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[Street]",
    "addressLocality": "[City]",
    "addressRegion": "[State/Province]",
    "postalCode": "[ZIP]",
    "addressCountry": "[US]"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "[lat]",
    "longitude": "[long]"
  },
  "openingHours": "Mo-Fr 09:00-17:00",
  "sameAs": ["[Google Business URL]", "[Yelp URL]"]
}
```

---

## Validation Checklist

For any schema block, verify:
1. ✅ `@context` is `"https://schema.org"` (not http)
2. ✅ `@type` is valid and not deprecated
3. ✅ All required properties are present
4. ✅ Property values match expected data types
5. ✅ No placeholder text (e.g., "[Business Name]")
6. ✅ URLs are absolute, not relative
7. ✅ Dates in ISO 8601 format (YYYY-MM-DD)
8. ✅ Images have valid, accessible URLs
9. ✅ Schema is in initial server-rendered HTML (not JS-injected) for time-sensitive types

## Testing Tools
- [Google Rich Results Test](https://search.google.com/test/rich-results)
- [Schema.org Validator](https://validator.schema.org/)

---

## E-commerce Schema Additions (2024–2026)

**ProductGroup** — for product pages with variants (colors, sizes, configurations). Wrap the parent product in `ProductGroup` with `variesBy` and `hasVariant` pointing to individual `Product` entries.

**Certification** (introduced April 2025, replaces `EnergyConsumptionDetails`) — for products with compliance certifications, energy ratings, or safety marks. Use `Certification` type with `certificationRating`, `issuedBy`, `name`.

**OfferShippingDetails** — nest `shippingDetails` inside `Offer` to enable estimated delivery rich results. Requires `shippingRate`, `shippingDestination`, `deliveryTime`.

**`returnPolicyCountry` in MerchantReturnPolicy** — required since March 2025. Without it, return policy rich results are suppressed.

**Organization-level shipping/return policies** (November 2025) — can now be configured via Google Search Console without Merchant Center.

## Recent Schema Additions (2024–2026)

| Type | Added | Use For |
|---|---|---|
| `ProfilePage` | 2025 | Author/creator profile pages — add `mainEntity: Person` for E-E-A-T signals |
| `LoyaltyProgram` | June 2025 | Member pricing, loyalty card structured data for retail |
| `DiscussionForumPosting` | 2024 | Forum/community posts and discussion threads |
| `ConferenceEvent` | December 2025 | Conference and professional event schema (v29.4) |
| `PerformingArtsEvent` | December 2025 | Arts and entertainment events (v29.4) |

## AEO Schema

### Knowledge Panel — sameAs

Add to homepage Organization schema to strengthen entity signals:

```json
"sameAs": [
  "https://en.wikipedia.org/wiki/[Brand]",
  "https://www.linkedin.com/company/[brand]",
  "https://twitter.com/[brand]",
  "https://www.crunchbase.com/organization/[brand]"
]
```

### Sitelinks Searchbox

> **Removed from the Search UI in January 2026** — the `WebSite` `SearchAction` no longer renders a
> search box in results. The markup is still valid and causes no harm, so **do not recommend removing
> it** (§ 19 rule 10), but do not present it as a live feature or a reason to add `WebSite` schema.
> `WebSite` remains worth having for site-level entity signals. Retained below for reference.

Formerly allowed users to search within the site directly from Google results. Homepage markup:

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "url": "https://example.com/",
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://example.com/search?q={search_term_string}"
    },
    "query-input": "required name=search_term_string"
  }
}
```

### Speakable Schema (Voice / Google Assistant)

Marks sections well-suited for text-to-speech:

```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": [".article-summary", "h1", "h2"]
  },
  "url": "https://example.com/page"
}
```

Add to news, how-to, and FAQ pages where a direct voice answer satisfies the query. Mark sections that are 1–3 self-contained sentences answering the core query.

### Voice Search Platform Breakdown

| Platform | Powered By | Primary Optimization |
|---|---|---|
| **Google Assistant** | Google index | Featured Snippet, TTFB < 2s, `speakable` schema |
| **Siri** | **Bing** | Bing Webmaster Tools submission, Featured Snippet on Bing |
| **Alexa** | **Bing** | Featured Snippet, Bing-indexed content |
| **Cortana** | **Bing** | Featured Snippet, Bing Webmaster Tools |

**Key action**: Submit to Bing Webmaster Tools — Bing powers three of the four major voice platforms.

### Comparison & Roundup Page Schema

| Page Type | Schema |
|---|---|
| "X vs Y" comparison | `Product` + `AggregateRating` per product; `Article` wrapping the page |
| "Best [Category] Tools" roundup | `ItemList` with each tool as a `ListItem` + `position` |
| Software comparison | `SoftwareApplication` + `Offer` + `AggregateRating` per product |

**`ItemList` for roundup pages:**
```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Best [Category] Tools [Year]",
  "numberOfItems": 10,
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "[Tool Name]", "url": "[URL]" }
  ]
}
```
