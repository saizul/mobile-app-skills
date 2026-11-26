---
name: store-listing-writer
description: Write and check Google Play and App Store listing text - Play title (30), short description (80), full description (4000) and release notes (500); App Store name (30), subtitle (30), keywords (100 bytes), promotional text (170), description and What's New - with a script that validates every field and locale against store limits and flags promotional words, emoji, other-platform mentions, keyword stuffing and wasted keyword bytes. Reads a listing JSON or fastlane metadata folders (supply and deliver). Use when the user asks to write, rewrite, localize or optimize (ASO) a store listing, app title, subtitle, keywords or release notes, or a listing was rejected or cut off in Play Console or App Store Connect.
license: MIT
compatibility: Python 3.8+ standard library only. Works offline; never uploads to Play Console or App Store Connect.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Store listing writer

Write listing copy that fits every field on the first try and does not trip store policy,
then prove it with the checker. The agent drafts; the user publishes.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Write the Play Store / App Store description for my app", "suggest a title and subtitle"
- "Pick App Store keywords", "improve ASO", "translate the listing into German and Japanese"
- Release notes / What's New for a version
- A listing field is too long, got cut off, or was rejected for metadata (promotional
  words in the title, mentions of Android in the App Store listing)
- Repos with `fastlane/metadata/` that need a CI check

## When not to use

- Screenshots, icons and preview videos (design work; this skill only covers text)
- Privacy labels / Data safety form answers: those follow from the app's data flows,
  use `ios-plist-audit` and `android-permissions-audit` to inventory them first
- Release mechanics (tracks, phased release): `release-checklist`

## Workflow

1. **Gather facts before writing.** Ask for (or read from the repo/README): what the app
   does in one sentence, the 3-5 main features, target users, the top 5-10 search terms
   users would type, competitors to avoid naming, supported locales, and what changed in
   this version (for release notes). Never invent features, awards, ratings or user counts.
2. **Print the limits** so drafts are sized correctly:
   ```bash
   python3 scripts/check_listing.py --limits
   ```
3. **Draft per field** following [references/writing-guide.md](references/writing-guide.md):
   - Play title / App Store name: brand + main benefit keyword, no "best", "#1", "free",
     prices, emoji or ALL CAPS.
   - App Store subtitle and Play short description: the main benefit in plain words.
   - App Store keywords: comma-separated, no spaces, no words already in name/subtitle,
     no "app", singular *or* plural, use 95-100 bytes. Non-Latin scripts use 2-3 bytes per
     character.
   - Description: first 2-3 lines must work alone (they are shown before "more"), then
     features as short lines, then trust details (privacy, sync, support). Never mention
     the other platform's store or devices.
   - Release notes: 1-3 user-visible changes, no "bug fixes" alone.
4. **Write the draft to a file** the checker reads: `listing.json` (shape in the script's
   `--help`), or the fastlane layout if the repo uses it (see
   [references/fastlane-layout.md](references/fastlane-layout.md)).
5. **Run the checker (read-only).**
   ```bash
   python3 scripts/check_listing.py listing.json
   python3 scripts/check_listing.py fastlane/metadata --json
   python3 scripts/check_listing.py . --store appstore --fail-on low
   ```
   Exit 1 = findings at or above `--fail-on` (default `medium`), 2 = unreadable input.
6. **Fix and re-run** until there is no `high`/`medium` finding. For `low`/`info` findings,
   decide with the user (for example "New" in a brand name is fine).
7. **Localize** per locale, not word for word: keep each locale's own search terms, re-run
   the checker (German and Japanese often overflow titles and keyword bytes).
8. **Hand over.** The user pastes into Play Console / App Store Connect or runs
   `fastlane supply` / `fastlane deliver` themselves. Do not upload anything.

## Output

```
Google Play (en-US)
  Title (30/30): Pocket Budget: Expense Tracker
  Short description (69/80): Track spending, set budgets and see where your money goes each month.
App Store (en-US)
  Name (13/30): Pocket Budget          Subtitle (27/30): Expense tracker and planner
  Keywords (91/100 bytes): money,spending,finance,receipt,scanner,savings,bills,...
Checker: 0 high, 0 medium, 1 info (keywords: 9 bytes unused)
Files written: fastlane/metadata/android/en-US/*.txt, fastlane/metadata/en-US/*.txt
```
