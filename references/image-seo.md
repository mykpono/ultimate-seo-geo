<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Image SEO — Optimization Framework
## Updated: March 2026

---

## Why Image SEO Matters

Images are both a discoverability channel (Google Images, visual search) and a Core Web Vitals factor (CLS, LCP). Poor image optimization is one of the most common causes of:
- Slow LCP (Largest Contentful Paint)
- High CLS (Cumulative Layout Shift)
- Missed Google Images rankings
- Reduced AI citation selection (multi-modal content is 156% more likely to be cited)

---

## Complete Image Audit Checklist

### Alt Text

| Check | Standard | Pass/Fail Signal |
|---|---|---|
| All `<img>` elements have alt attribute | Yes (even if `alt=""` for decorative) | Missing alt = ❌ |
| Alt text is descriptive | 10–125 characters, natural language | "image", "photo", "pic" = ❌ |
| Keyword used naturally if relevant | Once, naturally placed | Keyword stuffing alt = ❌ |
| Decorative images use empty alt | `alt=""` (not removed entirely) | Absent alt on decorative = ⚠️ |

**Good alt text examples:**
```html
<!-- Product -->
<img src="wool-yarn.jpg" alt="Hand-dyed merino wool yarn in deep burgundy, 100g skein">

<!-- Article hero (author byline context) -->
<img src="jane-smith.jpg" alt="Jane Smith, registered nutritionist and author">

<!-- Decorative divider -->
<img src="divider.svg" alt="">

<!-- BAD — keyword stuffed -->
<img src="shoes.jpg" alt="shoes buy shoes cheap shoes online shoe store shoes sale">
```

### File Format Decision Tree

```
Is this a photo or complex image?
├── YES → WebP (default) | AVIF (if 92%+ browser support acceptable)
│         Both support transparency; AVIF ~20% smaller than WebP
└── NO (logo, icon, illustration, simple graphic)
    ├── Simple, few colors, transparency needed → SVG (vector, scalable, tiny file)
    └── Complex illustration, fallback needed → WebP with PNG fallback
```

**Format comparison (2026):**
| Format | Browser Support | Compression vs. JPEG | Best For |
|---|---|---|---|
| **WebP** | 97%+ | 25-35% smaller | Default for all photos |
| **AVIF** | 92%+ | 40-50% smaller | Maximum compression priority |
| **JPEG XL** | Emerging (Chrome roadmap restored late 2025) | 60%+ smaller | Monitor; not production-ready yet |
| **SVG** | Universal | N/A (vector) | Logos, icons, simple graphics |
| **PNG** | Universal | Larger than WebP | Fallback only; avoid for photos |

### File Size Thresholds

| Image Type | Target | Warning | Hard Stop |
|---|---|---|---|
| Thumbnail / avatar | < 30KB | 50KB | 100KB |
| Content / inline image | < 100KB | 150KB | 200KB |
| Hero / banner image | < 200KB | 300KB | 400KB |
| Full-width background | < 300KB | 500KB | 800KB |

**Tools to check**: Google PageSpeed Insights → "Serve images in next-gen formats"; Squoosh (squoosh.app) for manual optimization; Cloudinary/Imgix for automated CDN optimization.

### Responsive Images

```html
<!-- Standard responsive image with srcset -->
<img
  src="article-hero-800.webp"
  srcset="article-hero-400.webp 400w,
          article-hero-800.webp 800w,
          article-hero-1200.webp 1200w"
  sizes="(max-width: 600px) 100vw,
         (max-width: 1200px) 75vw,
         800px"
  alt="[descriptive alt text]"
  width="800"
  height="450"
>
```

**Key rules:**
- Always declare `width` and `height` attributes (prevents CLS — browser reserves space before image loads)
- `sizes` attribute tells browser the rendered width at different viewport sizes
- `srcset` provides multiple resolutions; browser picks the optimal one

### Loading Strategy

| Image Position | Loading Strategy | Code |
|---|---|---|
| Above fold / LCP image | **Eager** + fetchpriority high | `loading="eager" fetchpriority="high"` |
| First viewport but not LCP | Eager (default) | (no loading attribute needed) |
| Below fold | Lazy | `loading="lazy"` |
| Decorative | Lazy | `loading="lazy" alt=""` |

**Critical mistake to avoid**: Adding `loading="lazy"` to the LCP image (the largest image in the viewport on page load). This tells the browser to delay loading the most important image, directly harming LCP score.

```html
<!-- CORRECT: Hero image (LCP candidate) -->
<img src="hero.webp" alt="..." width="1200" height="600"
     loading="eager" fetchpriority="high">

<!-- CORRECT: Below-fold gallery image -->
<img src="gallery-3.webp" alt="..." width="400" height="300"
     loading="lazy" decoding="async">
```

---

## CLS Prevention (Images)

CLS (Cumulative Layout Shift) from images is one of the most common CWV failures. Root cause: browser doesn't know image dimensions until it loads, so content shifts when image appears.

**Fix**: Always declare `width` and `height` on `<img>` elements.

```html
<!-- BAD: No dimensions → layout shift when image loads -->
<img src="product.webp" alt="Blue wool scarf">

<!-- GOOD: Dimensions declared → browser reserves space -->
<img src="product.webp" alt="Blue wool scarf" width="400" height="300">
```

This works even if CSS resizes the image — the browser uses the aspect ratio from the declared dimensions.

---

## Image SEO for Google Images

Google Images is a meaningful traffic source for visual content categories (recipes, products, travel, fashion, home decor, design).

**To rank in Google Images:**
1. **Placement**: Put images near the text they illustrate — Google uses surrounding text to understand image content
2. **Filename**: Descriptive filename before uploading: `hand-dyed-merino-wool-burgundy.webp` not `IMG_4821.jpg`
3. **Alt text**: Descriptive, contextual (see above)
4. **Structured data**: Add `ImageObject` schema for standalone image pages; `image` property on Article/Product schema
5. **Image Quality**: Sharp, clear, high-resolution — low-quality images appear in lower-quality results
6. **Page Context**: Ensure the page topic matches the image topic

---

## Image SEO for AI Citations

Multi-modal content (text + images) is cited 156% more often than text-only content in AI search.

**AI image optimization:**
- Compress for speed (FCP < 0.4s correlates with 3× more AI citations)
- Add descriptive filenames + alt text (AI crawlers read alt text)
- Include images that are genuinely illustrative (charts, diagrams, original photography outperform stock photos)
- Video + images together is strongest signal (78% of cited sources combine multiple media types)

---

## Audit Output Format

```
## Image SEO Score: XX/100

| Dimension | Pages Checked | Issues Found | Score |
|---|---|---|---|
| Alt Text Coverage | XX | XX missing | XX/30 |
| File Format | XX | XX not WebP/AVIF | XX/20 |
| File Size | XX | XX oversized | XX/20 |
| Responsive Images | XX | XX missing srcset | XX/15 |
| CLS Prevention | XX | XX missing dimensions | XX/10 |
| LCP Image | XX | XX misconfigured | XX/5 |

## Priority Fixes
1. [Highest impact issue + exact fix]
2. ...
```
