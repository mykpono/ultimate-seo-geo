<!-- Updated: 2026-08-23 | Review: 2027-02-23 -->
<!-- 2026-08-23 review: re-read end to end 2026-08-23: the International Targeting report and its country-targeting setting were removed 2022-09-22; hreflang errors are no longer reported in Search Console -->

# International SEO & Hreflang
## Updated: August 2026

---


**Contents:** Updated: August 2026 · When International SEO Applies · Site Structure Options · Hreflang — Complete Implementation Guide · Language & Region Code Reference · Critical Rules & Validation Checklist · Common Issues & Fixes · Content Strategy for International SEO · Geo-Targeting in Google Search Console · Audit Output Format · International SEO Assessment

## When International SEO Applies

Apply this framework when a site:
- Serves content in multiple languages (e.g., English + French + German)
- Targets the same language in multiple regions (e.g., en-US, en-GB, en-AU)
- Has separate URLs or domains for different countries
- Experiences unexpected international traffic that isn't being converted

---

## Site Structure Options

Choose the structure based on authority, budget, and operational constraints:

| Structure | Example | Pros | Cons |
|---|---|---|---|
| **ccTLD** (country-code top-level domain) | `example.fr`, `example.de` | Strongest geo-targeting signal; user trust | Most expensive; authority split across domains |
| **Subdomain** | `fr.example.com`, `de.example.com` | Easier to set up; can separate GA properties | Weaker than ccTLD; authority somewhat isolated |
| **Subdirectory** | `example.com/fr/`, `example.com/de/` | Concentrates domain authority; easiest to manage | Weakest geo-targeting signal of the three |

**Google's official position**: No ranking difference between structures if implemented correctly with hreflang. Choose based on operational needs.

---

## Hreflang — Complete Implementation Guide

### What Hreflang Does

Hreflang tells Google:
1. That multiple versions of a page exist for different languages/regions
2. Which version to show to which user

It does NOT affect rankings — it controls which version appears for which audience.

### Implementation Method Selection

| Method | Best For | Limitations |
|---|---|---|
| **HTML `<link>` tags** | Sites with <50 language variants; HTML pages only | Must be in `<head>`; all variants on every page |
| **HTTP response headers** | Non-HTML files (PDFs, XML, documents) | Requires server configuration access |
| **XML Sitemap** | Large sites (50+ variants); cross-domain setups | Sitemap must be submitted and processed first |

### HTML Implementation

```html
<head>
  <!-- Self-referencing tag (REQUIRED) -->
  <link rel="alternate" hreflang="en-US" href="https://example.com/en-us/page/">

  <!-- Other language/region variants -->
  <link rel="alternate" hreflang="en-GB" href="https://example.com/en-gb/page/">
  <link rel="alternate" hreflang="fr"    href="https://example.com/fr/page/">
  <link rel="alternate" hreflang="de"    href="https://example.com/de/page/">
  <link rel="alternate" hreflang="pt-BR" href="https://example.com/pt-br/page/">

  <!-- Fallback for unmatched languages/regions (REQUIRED) -->
  <link rel="alternate" hreflang="x-default" href="https://example.com/page/">
</head>
```

### XML Sitemap Implementation (Large Sites)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://example.com/en-us/page/</loc>
    <xhtml:link rel="alternate" hreflang="en-US" href="https://example.com/en-us/page/"/>
    <xhtml:link rel="alternate" hreflang="en-GB" href="https://example.com/en-gb/page/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://example.com/page/"/>
  </url>
  <url>
    <loc>https://example.com/en-gb/page/</loc>
    <xhtml:link rel="alternate" hreflang="en-US" href="https://example.com/en-us/page/"/>
    <xhtml:link rel="alternate" hreflang="en-GB" href="https://example.com/en-gb/page/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://example.com/page/"/>
  </url>
</urlset>
```

---

## Language & Region Code Reference

### Language Codes (ISO 639-1 — always 2 letters)

| Language | Correct Code | Common Error |
|---|---|---|
| English | `en` | `eng` ❌ |
| French | `fr` | `fra` ❌ |
| German | `de` | `deu` ❌ |
| Spanish | `es` | `esp` ❌ |
| Portuguese | `pt` | `por` ❌ |
| Japanese | `ja` | `jp` ❌ |
| Chinese (Simplified) | `zh-Hans` | `zh-cn` ❌ |
| Chinese (Traditional) | `zh-Hant` | `zh-tw` ❌ |

### Region Codes (ISO 3166-1 Alpha-2 — always uppercase when used)

| Region | Correct Code | Common Error |
|---|---|---|
| United States | `en-US` | `en-us` ❌ |
| United Kingdom | `en-GB` | `en-UK` ❌, `en-uk` ❌ |
| Australia | `en-AU` | `en-au` ❌ |
| Brazil | `pt-BR` | `pt-br` ❌, `pt-BRZ` ❌ |
| Canada (English) | `en-CA` | `en-ca` ❌ |

**Region codes are case-sensitive in implementation.** While Google claims to handle case-insensitivity, use the correct casing to avoid processing errors.

---

## Critical Rules & Validation Checklist

### The 5 Rules of Hreflang

1. **Self-referencing**: Every page must include an hreflang tag pointing to itself
2. **Return tags**: If page A links to page B, page B MUST link back to page A (bidirectional)
3. **x-default**: Must exist on every page set to designate the fallback URL
4. **Canonical URLs only**: Hreflang tags must use the canonical URL (not redirects, not parameter variants)
5. **Consistent URLs**: Every reference to a URL must be exactly identical (trailing slash, protocol, www)
6. **Canonical stays within the language**: each language version must canonicalize to **itself**, or at worst to the closest substitute language — never across languages to a single "main" version. Rule 4 says hreflang must point at canonical URLs; this is the distinct failure it does not cover. A French page carrying `<link rel="canonical" href="…/en/page">` tells Google the French page is a duplicate of the English one, which collapses the whole language cluster to one indexed URL and silently voids the hreflang set — the tags are syntactically valid and do nothing. This is the most common way a technically correct hreflang implementation produces no result.

**Symptom to look for**: hreflang validates cleanly, return tags are bidirectional, yet only one language version appears in any SERP and the others show "Duplicate, Google chose different canonical" in Search Console.

### Validation Checklist

- [ ] Every page has a self-referencing hreflang tag
- [ ] All pages in a set have return tags for every other variant
- [ ] x-default defined on every page set
- [ ] Language codes are ISO 639-1 (2 letters)
- [ ] Region codes are uppercase ISO 3166-1 (en-GB not en-uk)
- [ ] All URLs are canonical, absolute, and consistent (https not http; www or non-www, not both)
- [ ] Protocol consistent: no hreflang pointing to HTTP on HTTPS sites
- [ ] Trailing slash consistent: if canonical is `/page/`, hreflang uses `/page/`
- [ ] No hreflang on pages with noindex (contradictory signals)
- [ ] Sitemap-declared hreflang URLs match page-declared tags

---

## Common Issues & Fixes

| Issue | Detection | Fix |
|---|---|---|
| Missing self-reference | Crawl → check each page's hreflang set | Add `<link rel="alternate" hreflang="[lang]" href="[this-page]">` |
| Missing return tags | Crawl all variants; check for reciprocal links | Add missing reciprocal hreflang to every variant |
| Wrong region code casing | Code audit | Replace `en-uk` with `en-GB`; `pt-br` with `pt-BR` |
| Hreflang on non-canonical | Check canonical vs. hreflang URL | Move hreflang to canonical page; 301 non-canonical |
| HTTP/HTTPS mismatch | Audit hreflang href values | Update all hreflang to use https:// |
| Trailing slash inconsistency | Compare hreflang hrefs vs. canonical hrefs | Standardize to one format everywhere |
| Too many languages in one tag | N/A | Correct: separate `<link>` per language (not comma-separated) |

---

## Content Strategy for International SEO

### Translation vs. Transcreation

| Approach | When to Use | Risk |
|---|---|---|
| **Direct translation** | Technical documentation, legal content | May miss cultural nuances; keyword intent differs by market |
| **Transcreation** | Marketing content, landing pages | Higher quality; keyword research needed per market |
| **Machine translation (MT)** | Never for primary content | Google's guidance: MT without human review = thin content risk |

### Keyword Research Per Market

Keywords differ significantly across markets — never assume direct translation:
- "apartment" (US) vs. "flat" (UK) vs. "appartement" (French) — entirely different terms
- Search volume, competition, and user intent can vary dramatically
- Local competitors will rank for local variants even if your translations are correct

**Required per market**: Dedicated keyword research using native speakers or local market data.

### Duplicate Content Across Languages

**Not a penalty** if hreflang is implemented correctly. Google understands these are alternate versions. The risk is when:
- Machine-translated content is thin (no unique value vs. source)
- Pages have no unique local signals (prices in wrong currency, local examples missing)
- Content is identical except for a place name

---

## Geo-Targeting in Google Search Console

> **There is no country-targeting setting any more.** The International Targeting report — which
> carried both the country selector and the hreflang error report — was **deprecated in August 2022
> and removed on 22 September 2022**. Do not send anyone to "GSC → Legacy Tools → International
> Targeting"; it does not exist, and neither does the setting it contained.

**What replaced it: nothing, and nothing is needed.** Google withdrew country targeting because it
was judged to add little value. The signals that actually determine geo-targeting are:

1. **Hreflang** — the primary mechanism, and still fully supported. Google confirmed at removal that
   its multilingual/multiregional recommendations were unchanged
2. **ccTLD** — `example.de` is inferred automatically; nothing to configure
3. **Server location / CDN, local links, local currency and address signals** — secondary

**Hreflang errors are no longer reported in Search Console.** Validate them yourself with
`scripts/hreflang_checker.py`, which covers all 8 rules including the cross-language canonical case
Search Console never surfaced anyway.

---

## Audit Output Format

```
## International SEO Assessment

### Site Structure: [ccTLD / Subdomain / Subdirectory / Mixed]

### Hreflang Implementation Status
| Check | Status | Pages Affected |
|---|---|---|
| Self-referencing tags | ✅/❌ | XX |
| Return tags complete | ✅/❌ | XX |
| x-default present | ✅/❌ | XX |
| Language code format | ✅/❌ | XX |
| URL consistency | ✅/❌ | XX |

### Critical Issues
[List issues with exact fix for each]

### Opportunity: Untapped Markets
[Based on GSC international traffic data — regions generating traffic without localized content]
```
