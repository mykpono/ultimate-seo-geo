<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Schema.org Types — Status & Recommendations
## Updated: March 2026 (Schema.org v29.4)

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
| DiscussionForumPosting | Forum threads | headline, author, datePublished, text, url |
| LoyaltyProgram | Membership pricing | membershipPointsEarned, eligibleQuantity (added June 2025) |

---

## RESTRICTED — Only for specific site types

| Type | Restriction | GEO Note |
|---|---|---|
| FAQPage | **Google rich results**: government and healthcare ONLY (restricted Aug 2023) | **Still valid for GEO**: AI engines (ChatGPT, Perplexity, Google AI Overviews) still extract FAQ schema for citations regardless of Google rich results restriction |

> **Decision tree for FAQPage:**
> - **Adding new FAQPage to commercial site for Google rich results?** → Not recommended.
> - **Existing FAQPage on commercial site?** → Flag at Info priority. Removing it removes AI citation upside.
> - **Adding FAQPage specifically for AI/LLM citations?** → Acceptable; clearly a GEO strategy.

---

## DEPRECATED — Never recommend

| Type | Status | Removed | Notes |
|---|---|---|---|
| **HowTo** | Rich results fully removed | September 2023 | Google stopped showing how-to rich results entirely |
| **SpecialAnnouncement** | Deprecated | July 31, 2025 | COVID-era, no longer processed |
| **ClaimReview** | Retired from rich results | June 2025 | Fact-check markup no longer generates rich results |
| **EstimatedSalary** | Retired from rich results | June 2025 | Removed |
| **LearningVideo** | Retired from rich results | June 2025 | Use VideoObject instead |
| **VehicleListing** | Retired from rich results | June 2025 | Discontinued |
| **CourseInfo** | Merged into Course | June 2025 | Use Course instead |
| **Practice Problem** | Retired from rich results | Late 2025 | |
| **Dataset** | Dataset Search discontinued | Late 2025 | |
| **Sitelinks Search Box** | Removed from Search UI | Jan 2026 | WebSite SearchAction no longer shows in results |

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

### FAQPage (use for GEO/AI citation benefit)

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

Allows users to search within the site directly from Google results. Add to homepage:

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
