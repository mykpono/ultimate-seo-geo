<!-- Updated: 2026-09-17 | Review: 2027-03-17 -->

# Page Types — Content-Type Taxonomy

The labels `scripts/page_type_classifier.py` assigns to every known URL, the funnel stage each maps to, and the page types each kind of site is expected to have. **This file is pinned to the script by `tests/test_page_type_parity.py`**: change a label, an intent stage or an expected-types row here and in `PAGE_TYPES` / `EXPECTED_BY_SITE_TYPE` in the same commit, or CI fails.

## How classification works

1. **URL rules first, in table order, first match wins.** Two kinds:
   - **Section** patterns are tested against the *first path segment only* (`/blog/`), or the second when the first is a locale code (`/en/blog/`). A word deep in a path is not a section: `/docs/pricing` is documentation, `/category/integration` is an archive.
   - **Path** patterns are tested against the whole path and query. They are content shapes that legitimately live under any section (`x-vs-y`, `what-is-`, `for-marketers`, `/page/2`) and they **win over the section label**, which is kept as `secondary_label`. A comparison post under `/blog/` therefore counts as a comparison *and* as blog output.
2. **Fetched pages add content signals** (H1 or title pattern, JSON-LD `@type`, call-to-action anchor). Each source votes at most once per label.
3. **Confidence** follows the finding contract: **Confirmed** when the URL rule and a page signal agree; **Likely** on a URL rule alone, or two independent page signals; **Hypothesis** on one page signal. `pain_point_problem` is capped at Hypothesis.
4. **Site-type remap:** on a `saas` site `ecom_product` (`/products/x`) is relabelled `product_feature`.
5. **Absence claims are gated.** The matrix is built from sitemap URLs plus crawled pages, so it can be complete without fetching everything. A `missing_page_type` finding is only made when `sitemap.complete` or `crawl.complete` is true in the graph; otherwise a single Info `coverage_inconclusive` finding lists what was not seen and why.

## Page type taxonomy

| Label | Intent | Section URL signals | Path (slug) URL signals | Secondary signals (fetched page) | Meaning |
|---|---|---|---|---|---|
| **homepage** | nav | — | `/` | — | The site root. |
| **comparison** | BOFU | /vs/, /compare/, /comparisons/, /versus/ | `x-vs-y`, `x-versus-y`, `/vs/`, `/compare/` | H1/title: `\bvs\.?\s`, `\bversus\b`, `\bcompared\b` | Head-to-head X vs Y pages. Most-cited content type in AI answers (~33%). |
| **alternatives** | BOFU | /alternatives/, /competitors/ | `x-alternative(s)`, `x-competitor(s)`, `/alternatives/` | H1/title: `\balternatives?\b`, `\bcompetitors\b` | '[competitor] alternatives' lists; the most-searched BOFU pattern in SaaS. |
| **pricing** | BOFU | /pricing/, /plans/, /prices/, /pricing-plans/ | — | H1/title: `\bpricing\b`, `\bplans\b` | Plans and prices. |
| **case_study** | BOFU | /case-study/, /case-studies/, /customers/, /success-stories/, /customer-stories/, /testimonials/, /clients/ | — | H1/title: `\bcase study\b`, `\bhow \S+ (?:uses|used|achieved|in…` | Named customer outcomes. |
| **integration** | MOFU | /integrations/, /apps/, /connectors/, /marketplace/, /plugins/, /add-ons/ | — | H1/title: `\bintegrat(?:e|ion|ions)\b` | One page per connected tool. |
| **persona_icp** | MOFU | /teams/, /roles/, /who-we-serve/, /personas/, /who-its-for/ | `/for/<role>`, `for-<role>` (role lexicon: marketers, developers, founders, sales teams, …) | H1/title: `\bfor\s+(?:marketers|marketing\ te…` | 'For [role]' pages aimed at a buyer persona or ICP. |
| **industry_market** | MOFU | /industry/, /industries/, /markets/, /verticals/, /sectors/ | `/for/<industry>`, `for-<industry>` (industry lexicon: healthcare, fintech, retail, …) | H1/title: `\b(?:for|in)\s+(?:the\s+)?(?:healt…` | 'For [industry]' vertical pages. |
| **solution_use_case** | MOFU | /solutions/, /use-cases/, /workflows/, /for/ | `/for/<anything>`, `/use-cases/` | — | Jobs-to-be-done landing pages. |
| **pain_point_problem** | TOFU | /problems/, /challenges/ | `why-is-…`, `why-my-…`, `how-to-fix-…`, `how-to-stop-…` | H1/title: `^how to (?:fix|stop|reduce|prevent…`, `^why (?:is|are|does|do) (?:my|your…`, `\b(?:biggest|common) (?:problems|c…` | Problem-first pages ('why is my X slow'). New heuristic: capped at Hypothesis. |
| **product_feature** | MOFU | /features/, /product/, /platform/, /capability/, /capabilities/, /modules/ | — | schema: SoftwareApplication, WebApplication; CTA: `\b(?:start|begin) (?:your )?`, `\bbook a demo\b` | Feature, product or platform pages. |
| **glossary_definition** | TOFU | /glossary/, /dictionary/, /definitions/, /wiki/, /what-is/ | `what-is-…`, `what-are-…` | H1/title: `^what (?:is|are) (?:a |an |the )?`, `\bdefinition\b`, `\bglossary\b`; schema: DefinedTerm, DefinedTermSet | Definitions and 'what is X' explainers. |
| **pillar_guide** | TOFU | /guides/, /learn/, /academy/, /handbook/, /playbooks/, /resources/guides/ | `ultimate-guide…`, `complete-guide…`, `beginners-guide…` | H1/title: `\b(?:ultimate|complete|definitive|…`, `^(?:a |the )?guide to\b` | Long-form cluster anchors. |
| **tool_template** | TOFU | /tools/, /templates/, /calculators/, /generators/, /checklists/, /free-tools/ | `free-x-tool`, `x-calculator`, `x-generator` | H1/title: `\b(?:calculator|template|generator…` | Free tools, templates, calculators. |
| **docs_help** | support | /docs/, /documentation/, /help/, /help-center/, /support/, /kb/, /knowledge-base/, /developers/, … | — | schema: TechArticle | Documentation, help centre, API reference, tutorials. |
| **community_qa** | support | /questions/, /community/, /forum/, /forums/, /discussions/, /answers/, /q-and-a/, /qa/ | — | schema: QAPage, DiscussionForumPosting | Q&A, forums, community threads. |
| **faq** | support | /faqs/, /frequently-asked-questions/ | — | H1/title: `\bfaqs?\b`, `\bfrequently asked\b` | FAQ hubs. |
| **author** | trust | /authors/, /writers/, /contributors/, /profile/, /people/, /experts/ | — | schema: ProfilePage; schema: Person without Article | Author and profile pages (E-E-A-T attribution). |
| **tag_archive** | meta | /tags/, /topics/, /category/, /categories/, /archives/, /label/, /series/ | `/page/N`, `?page=N` | schema: CollectionPage | Tag, topic and category archives; paginated lists. |
| **blog_article** | TOFU | /blog/, /articles/, /news/, /insights/, /posts/, /stories/, /journal/, /magazine/, … | `/YYYY/MM/…` | schema: Article, BlogPosting, NewsArticle | Articles, news, changelog entries, dated posts. |
| **landing_campaign** | BOFU | /lp/, /landing/, /campaigns/, /demo/, /trial/, /free-trial/, /signup/, /sign-up/, … | — | schema: Event | Demo, trial, signup, webinar, event and campaign pages. |
| **ecom_category** | MOFU | /collections/, /category/, /categories/shop/, /c/, /shop/, /catalog/, /catalogue/, /brands/, … | — | schema: ItemList, CollectionPage, OfferCatalog | Shop collections and categories. |
| **ecom_product** | BOFU | /products/, /p/, /item/, /items/, /dp/, /sku/, /buy/, /shop/products/ | — | schema: Product, ProductGroup, IndividualProduct; CTA: `\badd to (?:cart|bag|basket)`, `\bbuy now\b` | Individual products. |
| **location_service** | BOFU | /locations/, /services/, /areas/, /areas-served/, /service-areas/, /near-me/, /branches/, /stores/, … | `x-near-me` | H1/title: `\bin [A-Z][a-zA-Z]+(?:, [A-Z]{2})?…`, `\bnear (?:you|me)\b`; schema: Service; schema: any LocalBusiness subtype (`jsonld.LOCAL_BUSINESS_TYPES`) | Service and location pages (local SEO). |
| **about_company** | trust | /about/, /about-us/, /company/, /team/, /leadership/, /our-story/, /mission/, /careers/, … | — | H1/title: `^about\b`, `^our (?:story|team|mission)\b`; schema: AboutPage | About, team, careers, security, partners. |
| **contact** | trust | /contact/, /contact-us/, /get-in-touch/, /talk-to-sales/, /talk-to-us/, /talk-to-a-human/, /book-a-call/, /book/ | — | H1/title: `^contact\b`, `\bget in touch\b`; schema: ContactPage | Contact and sales-contact pages. |
| **legal** | meta | /privacy/, /privacy-policy/, /terms/, /terms-of-service/, /terms-of-use/, /legal/, /cookies/, /cookie-policy/, … | — | H1/title: `\bprivacy policy\b`, `\bterms (?:of|and) (?:service|use|…` | Privacy, terms, cookies, accessibility. |
| **generic** | meta | — | — | — | Fallback when no rule matches. |

Intent stages: `nav` (homepage), `TOFU`, `MOFU`, `BOFU`, `support`, `trust`, `meta` (archives, legal, unclassified).

## Expected page types by site type

Derived from the site architectures in `references/industry-templates.md`. A missing **money** type (alternatives, case_study, comparison, ecom_category, ecom_product, location_service, pricing, product_feature, solution_use_case) is a **Medium** finding tagged `opportunity`; any other missing type is **Low**. `docs` and `generic` sites have no expectations.

| Site type | Expected page types |
|---|---|
| **saas** | pricing, product_feature, comparison, alternatives, solution_use_case, integration, case_study, docs_help, blog_article, about_company |
| **ecommerce** | ecom_category, ecom_product, comparison, pillar_guide, blog_article, faq, about_company, contact |
| **local** | location_service, about_company, contact, faq, blog_article |
| **publisher** | blog_article, author, tag_archive, pillar_guide, about_company |
| **docs** | — |
| **generic** | — |

## Site-type detection (`--site-type auto`)

Checked in this order; pass `--site-type` to override.

| Result | Rule |
|---|---|
| `docs` | Host starts with `docs.`, `developers.`, `developer.`, `help.`, `support.`, `learn.` or `kb.`; or ≥ 50% of ≥ 20 URLs are `docs_help` |
| `publisher` | ≥ 60% of ≥ 20 URLs are `blog_article`, `tag_archive` or `author` |
| `ecommerce` | Product schema on ≥ 2 fetched pages, or add-to-cart anchors on ≥ 2, or ≥ 5 `/products/` URLs with either signal |
| `local` | LocalBusiness (any subtype) schema on the homepage, or ≥ 3 `location_service` URLs making > 10% of the site |
| `saas` | A pricing page plus any of product/feature, integration or docs pages; or SoftwareApplication / WebApplication schema on the homepage |
| `generic` | Anything else |

## Other findings and thresholds

| Finding | Severity | Rule |
|---|---|---|
| `missing_page_type` | Medium / Low | Expected type with zero URLs, inventory complete |
| `coverage_inconclusive` | Info | Expected types unseen, but sitemap and crawl both incomplete |
| `intent_imbalance` | Low | saas / ecommerce, ≥ 50 funnel URLs (TOFU+MOFU+BOFU), BOFU < 5% of them |
| `unclassified_share` | Info | ≥ 20 URLs and > 40% `generic` — pass `--rules` |
| `type_word_floor` | Low | Family of ≥ 2 fetched pages averaging under half the word floor for its type (`industry-templates.md`) |

All findings from this script are **display-only**: none is weighted in the Health Score (v1.14.0 contract).

## Site-specific rules (`--rules rules.json`)

A JSON list prepended to the defaults, first match wins:

```json
[
  {"label": "community_qa", "pattern": "^/questions/$", "kind": "section"},
  {"label": "comparison", "pattern": "/head-to-head/", "kind": "path"}
]
```

`kind` defaults to `path`. Labels must be from the table above.

## Real-site calibration (2026-09-17)

| Site | Detected | Notes |
|---|---|---|
| posthog.com (13,161 sitemap URLs) | saas | 54% `community_qa` (`/questions/`), 29% docs; all 10 expected SaaS types present |
| developers.cloudflare.com (8,421) | docs | 79% generic because sections are product names; `unclassified_share` fires, as intended |
| smashingmagazine.com (7,886) | publisher | 61% articles, 21% author pages, 6% archives; 16 comparisons found inside dated posts |
| python.org (no sitemap, 40 crawled) | generic | Inventory inconclusive, so no absence findings |

Before this calibration, `/category/pricing` was labelled pricing, `x-in-python` slugs were location pages, and Smashing Magazine was a SaaS site. Section-level matching, dropping the `-in-` pattern and checking publisher before saas fixed all three.
