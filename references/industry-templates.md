<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Industry-Specific SEO Templates

Site architecture, schema priorities, and content strategy by business type.
Load when § 2 business type detection identifies a specific industry.

---

## SaaS / B2B Software

### Site Architecture

```
/                          ← Homepage (WebApplication/Organization schema)
/features/                 ← Feature hub (internal links to all feature pages)
  /features/[feature]/     ← Individual feature pages
/pricing/                  ← Pricing page (Offer schema, FAQPage for pricing Qs)
/blog/                     ← Blog hub (Article schema, BreadcrumbList)
  /blog/[post-slug]/
/[topic]-software/         ← Category landing pages (TOFU — "best X software")
/[topic]-for-[use-case]/   ← Use-case pages (MOFU)
/[competitor]-alternative/ ← Comparison/alternatives pages (BOFU)
/[competitor]-vs-[brand]/  ← VS pages (BOFU — highest conversion intent)
/case-studies/             ← Social proof hub
  /case-studies/[company]/ ← Individual case studies
/integrations/             ← Integrations hub
  /integrations/[tool]/    ← Per-tool integration pages
/docs/ or /help/           ← Documentation (high long-tail keyword value)
/about/                    ← About (Organization + Person schema)
```

### Essential Schema

| Page Type | Schema |
|---|---|
| Homepage | `WebApplication` or `SoftwareApplication`, `Organization`, `WebSite` (Sitelinks Searchbox) |
| Feature pages | `SoftwareApplication`, `FAQPage` |
| Pricing | `Offer`, `FAQPage` |
| Blog posts | `Article` or `BlogPosting`, `Person` (author), `BreadcrumbList` |
| Case studies | `Article`, `Organization` (customer) |

### Content Priority Order

1. **Comparison/VS pages** (BOFU, 4–7% conversion rate) — highest ROI
2. **Integration pages** (long-tail, high intent, low competition)
3. **Feature pages** (transactional intent, drives trial)
4. **Use-case category pages** (MOFU — "X for [role/industry]")
5. **TOFU pillar content** (definitional guides — "what is X")

### SaaS-Specific DO NOTs

- Never lock documentation behind login — /docs are high-value keyword targets
- Never ignore /[competitor]-alternative pages — most-searched BOFU pattern in SaaS
- Never put pricing as JS-rendered only — critical page for Googlebot and AI crawlers

---

## E-commerce

### Site Architecture

```
/                          ← Homepage (Organization, WebSite schema)
/[category]/               ← Category pages (ItemList, BreadcrumbList)
  /[category]/[subcategory]/
  /[category]/[product]/   ← Product pages (Product, Offer, AggregateRating)
/brands/                   ← Brand hub
  /brands/[brand]/         ← Brand landing pages
/sale/ or /deals/          ← Sale hub (Offer schema, validity dates)
/[product-type]-guide/     ← Buying guides (TOFU — "best running shoes")
/[product]-review/         ← Review pages
/[product-a]-vs-[product-b]/ ← Comparison pages (BOFU)
/blog/                     ← Content hub
/faq/                      ← FAQ hub (FAQPage schema)
/about/                    ← Trust signals
```

### Essential Schema

| Page Type | Schema |
|---|---|
| Product pages | `Product`, `Offer`, `AggregateRating`, `BreadcrumbList` |
| Product with variants | `ProductGroup` (parent) + `Product` per variant, `variesBy` property |
| Products with certs | `Certification` (energy ratings, safety marks) — replaces `EnergyConsumptionDetails` |
| Products with shipping | `OfferShippingDetails` nested in `Offer` |
| Category pages | `ItemList`, `BreadcrumbList` |
| Homepage | `Organization`, `WebSite` (Sitelinks Searchbox) |
| Buying guides | `Article`, `ItemList` |

### ProductGroup Example (Variants)

```json
{
  "@context": "https://schema.org",
  "@type": "ProductGroup",
  "name": "Classic Running Shoe",
  "variesBy": ["color", "size"],
  "hasVariant": [
    {
      "@type": "Product",
      "name": "Classic Running Shoe — Black / US 10",
      "sku": "RS-BLK-10",
      "offers": {
        "@type": "Offer",
        "price": "89.99",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock"
      }
    }
  ]
}
```

### Content Priority Order

1. **Category page optimization** — biggest traffic volume for e-commerce
2. **Product page E-E-A-T + schema** — conversion + rich results
3. **Buying guides** (TOFU — drive top-of-funnel organic)
4. **Comparison pages** (BOFU — highest purchase intent)
5. **Brand pages** (navigational + long-tail)

### E-commerce-Specific DO NOTs

- Never use thin category pages with only a product grid and no text
- Never leave product descriptions as manufacturer copy — duplicate content across competitors
- Never omit `width`/`height` on product images — CLS is a major e-commerce issue

---

## Local Service Business

### Site Architecture

```
/                          ← Homepage (LocalBusiness schema, NAP prominent)
/services/                 ← Service hub
  /services/[service]/     ← Service pages (Service + Offer schema)
/locations/                ← Location hub (for multi-location)
  /locations/[city]/       ← City pages (LocalBusiness with geo coords)
/[service]-in-[city]/      ← Geo+service pages (high local intent)
/about/                    ← Trust signals (team, credentials, history)
/reviews/                  ← Reviews aggregate (AggregateRating schema)
/blog/                     ← Local content hub
/faq/                      ← FAQPage schema
/contact/                  ← Contact (with NAP, embedded map)
```

### Essential Schema

| Page Type | Schema |
|---|---|
| Homepage | `LocalBusiness` (most specific subtype: `Plumber`, `DentalClinic`, etc.), `Organization` |
| Location pages | `LocalBusiness` with `address`, `geo`, `openingHours`, `telephone` |
| Service pages | `Service` with `provider`, `areaServed`, `Offer` |
| FAQ | `FAQPage` |
| About/Team | `Person` (for key staff) |

**Most Specific LocalBusiness Type**: Use the most specific applicable type (e.g., `DentalClinic` not `HealthBusiness`; `Electrician` not `HomeAndConstructionBusiness`). Full list: schema.org/LocalBusiness.

### Location Page Quality Gates

- ≤30 location pages: ensure each has unique local content (address, team, local reviews, locally-relevant body copy)
- 30–50 pages: WARNING — content differentiation review required
- 50+ pages: HARD STOP — each page must justify existence with substantive unique content beyond city name swap

### Content Priority Order

1. **Service + location combination pages** (e.g., "/plumber-in-chicago/") — highest local intent
2. **GBP optimization** — primary traffic driver for local queries
3. **Review accumulation** (threshold: 50 reviews, ≥4.3 stars)
4. **FAQ content** on service pages — PAA capture for local queries
5. **Educational blog** (TOFU — "how to know if your pipes need replacing")

### Local SEO DO NOTs

- Never use the same body copy on multiple location pages with only the city name swapped
- Never omit geo coordinates in LocalBusiness schema (`"geo": {"@type": "GeoCoordinates", ...}`)
- Never ignore NAP consistency — a single mis-spelled street abbreviation can suppress map pack rankings

---

## Publisher / Blog / Media

### Site Architecture

```
/                          ← Homepage (Organization, WebSite schema)
/[topic]/                  ← Topic category pages
  /[topic]/[post-slug]/    ← Article pages (Article/NewsArticle schema)
/author/[name]/            ← Author pages (Person schema, article index)
/about/                    ← Editorial policy, team, mission
/[topic]-guide/            ← Pillar guides
/newsletter/               ← Email capture
/[topic]/page/[N]/         ← Paginated archives (canonical management critical)
```

### Essential Schema

| Page Type | Schema |
|---|---|
| Article pages | `Article` or `NewsArticle` (news) or `BlogPosting` (blog) |
| Author pages | `Person` with `sameAs` to social/Wikipedia |
| Homepage | `Organization` or `NewsMediaOrganization`, `WebSite` |
| Pillar guides | `Article`, `FAQPage`, `BreadcrumbList` |
| Topic pages | `ItemList` (linking to articles) |

### Publisher E-E-A-T Priorities

1. **Named authors on every article** — anonymous bylines are the #1 E-E-A-T failure for publishers
2. **Author pages with credentials** — link from every article to a robust author bio with external links proving expertise
3. **Editorial policy page** — explicitly state editorial standards, fact-checking process, correction policy
4. **Publication + last-updated dates** — required on every article; critical for AI citation freshness scoring
5. **Primary sources + external citations** — link out to original research, official sources; outbound links are a trust signal

### Pagination + Archive Management

- Paginated category pages (page 2, 3...): `rel="prev"` / `rel="next"` are deprecated by Google — use self-referencing canonicals on each paginated page instead
- Deep paginated pages (page 10+): consider noindex to conserve crawl budget
- Never noindex the main category page

### Publisher-Specific DO NOTs

- Never publish AI-generated content without expert review and attribution — post-Dec 2025 E-E-A-T change makes this high-risk for publishers
- Never use `rel="prev"`/`rel="next"` for pagination — Google dropped support; this hint is ignored
- Never block archive/category pages from indexing — these are significant traffic sources

---

## Cross-Industry Notes

### Internal Linking Targets by Site Type

| Site Type | Target Links per Key Page |
|---|---|
| SaaS (feature/pricing pages) | 8–15 inbound internal links |
| E-commerce (category pages) | 5–10 inbound internal links |
| Local (service pages) | 3–7 inbound internal links |
| Publisher (pillar articles) | 10–20 inbound internal links from cluster posts |

### Word Count Floors by Page Type

| Page Type | Word Floor | Rationale |
|---|---|---|
| SaaS feature page | 600–1,000 words | Enough to cover use cases, FAQs, integrations |
| E-commerce category page | 300–500 words | Above-product description; don't over-stuff |
| E-commerce product page | 300–600 words | Unique description + specs + use cases |
| Local service page | 600–800 words | Service details + local signals + FAQs |
| Blog / article | 1,500–2,500 words | Full topic coverage for competitive queries |
| Pillar page | 3,000–5,000 words | Cluster anchor; must cover topic comprehensively |

These are floors based on competitive analysis, not magic numbers. Always audit top-ranking competitors' word counts for a given query.
