# Listing writing guide

## Field limits

| Store | Field | Limit | Indexed for search | Change needs a new build |
| --- | --- | --- | --- | --- |
| Google Play | Title | 30 chars | yes | no |
| Google Play | Short description | 80 chars | yes | no |
| Google Play | Full description | 4000 chars | yes | no |
| Google Play | Release notes ("What's new") | 500 chars | no | per release |
| App Store | Name | 30 chars | yes | with a version |
| App Store | Subtitle | 30 chars | yes | with a version |
| App Store | Keywords | 100 bytes | yes | with a version |
| App Store | Promotional text | 170 chars | no | no (edit any time) |
| App Store | Description | 4000 chars | no | with a version |
| App Store | What's New | 4000 chars | no | per version |

App Store Connect measures keywords in bytes: ASCII letters are 1 byte, accented Latin
letters 2, CJK and most other scripts 3. The checker counts UTF-8 bytes for keywords and
characters everywhere else. App Store Connect is the final judge; re-check there if a
locale is within a few bytes of the limit.

## Policy traps (common rejections)

- **Google Play metadata policy:** no ranking or performance claims ("best", "#1", "top"),
  no price or promotion ("free", "sale", "50% off"), no emoji, repeated special characters
  or ALL CAPS in the title, icon or developer name. No keyword stuffing anywhere; no
  unattributed testimonials.
- **App Review 2.3.7:** the name and subtitle must not contain prices, terms or descriptions
  that are not the name; keywords must not contain competitor app names or trademarks.
- **App Review 2.3.10:** do not mention other platforms ("Android", "Google Play") in App
  Store metadata. The reverse is good practice on Google Play too.
- Do not promise features that are not in the build being reviewed.

Known false positives in the checker: brand names that contain a flagged word ("New Day
Journal", "Top Hat Tours"), acronyms not in its list. Accept them knowingly.

## Structure that converts

**Title / name:** `Brand: core keyword phrase` or `Brand - core benefit`. Keep the brand
first; it is what returning users search.

**Short description / subtitle:** one benefit, concrete verb. "Track spending and stick to
your budget" beats "The ultimate finance companion".

**Full description:**

1. Two-line hook: what it does and for whom (shown before "Read more").
2. 4-8 feature lines, each starting with the user benefit.
3. Proof that is true and verifiable: offline support, privacy (what stays on device),
   platforms, sync, accessibility.
4. Subscription terms if any (price, period, auto-renewal, how to cancel); required by
   both stores when the app sells subscriptions.
5. Support contact or URL.

**App Store keywords:**

- Brainstorm 30+ terms, remove those already in the name and subtitle, remove "app",
  duplicates and plural forms, then fill 95-100 bytes ordered by relevance.
- Use single words when possible: Apple combines words across the name, subtitle and
  keyword field ("budget" + "planner" matches "budget planner").
- Localize: each locale has its own 100 bytes. Several App Store regions also index a
  second locale (for example English (UK) in some countries); use that space for
  extra terms.

**Release notes:** "New: shared budgets sync in real time. Fixed: receipts scanning on
Android 10." Name the user-visible change; keep internal ticket numbers out.

## Localization checklist

- Translate meaning and search intent, not words; ask a native speaker for keywords.
- German, Finnish and Russian titles run long: plan a shorter variant.
- Japanese, Chinese and Korean keywords: 33 characters can already reach 100 bytes.
- Keep brand names and trademarks untranslated unless the brand is localized.
