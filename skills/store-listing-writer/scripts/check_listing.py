#!/usr/bin/env python3
"""Check Google Play and App Store listing text against store limits and common rejection causes.

Reads a listing JSON file or a fastlane metadata folder (supply for Google Play, deliver
for the App Store) and reports, per locale and field: length against the store limit,
missing required fields, promotional words in titles, emoji, other-platform mentions,
wasted App Store keyword bytes and keyword stuffing.

Listing JSON shape (locale level optional):
  {"play": {"en-US": {"title": "...", "short_description": "...", "full_description": "...",
                      "release_notes": "..."}},
   "appstore": {"en-US": {"name": "...", "subtitle": "...", "keywords": "a,b,c",
                          "promotional_text": "...", "description": "...", "release_notes": "..."}}}

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]

# Limits in characters, except App Store keywords which App Store Connect measures in bytes.
LIMITS = {
    "play": {
        "title": 30,
        "short_description": 80,
        "full_description": 4000,
        "release_notes": 500,
    },
    "appstore": {
        "name": 30,
        "subtitle": 30,
        "keywords": 100,
        "promotional_text": 170,
        "description": 4000,
        "release_notes": 4000,
    },
}
REQUIRED = {
    "play": ["title", "short_description", "full_description"],
    "appstore": ["name", "description", "keywords"],
}
BYTE_FIELDS = {("appstore", "keywords")}

# fastlane file names -> listing fields
SUPPLY_FILES = {
    "title.txt": "title",
    "short_description.txt": "short_description",
    "full_description.txt": "full_description",
}
DELIVER_FILES = {
    "name.txt": "name",
    "subtitle.txt": "subtitle",
    "keywords.txt": "keywords",
    "promotional_text.txt": "promotional_text",
    "description.txt": "description",
    "release_notes.txt": "release_notes",
}
DELIVER_NON_LOCALE = {"android", "review_information", "trade_representative_contact_information"}

PROMO_WORDS = [
    "best",
    "#1",
    "no. 1",
    "number one",
    "top",
    "free",
    "new",
    "hot",
    "sale",
    "discount",
    "cheapest",
    "million downloads",
    "award",
    "editor's choice",
    "app of the year",
]
PRICE_RE = re.compile(r"(\$\s?\d|\d\s?(usd|eur|gbp)\b|\bfree\b|\b\d+%\s?off\b)", re.I)
EMOJI_RE = re.compile("[\U0001f000-\U0001faff☀-➿⬀-⯿️]")
OTHER_PLATFORM = {
    "play": re.compile(r"\b(iphone|ipad|ios|app store|apple watch|testflight)\b", re.I),
    "appstore": re.compile(r"\b(android|google play|play store|apk)\b", re.I),
}
ACRONYMS = {"GPS", "PDF", "HTML", "API", "USA", "NASA", "HIIT", "CRM", "SMS", "VPN", "AI", "QR", "NFC", "UI", "OK"}
STOPWORDS = set(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "this",
        "to",
        "with",
        "you",
        "your",
        "will",
        "we",
        "all",
        "any",
        "more",
        "one",
        "get",
        "app",
    ]
)
GENERIC_NOTES = re.compile(
    r"^\s*(bug fixes( and (performance )?improvements)?|minor (fixes|improvements))\.?\s*$", re.I
)


class Finding:
    __slots__ = ("check", "field", "fix", "locale", "message", "severity", "store")

    def __init__(self, store, locale, field, check, severity, message, fix):
        self.store, self.locale, self.field = store, locale, field
        self.check, self.severity, self.message, self.fix = check, severity, message, fix

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("store", "locale", "field", "check", "severity", "message", "fix")}


def measure(store: str, field: str, text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    if (store, field) in BYTE_FIELDS:
        return len(text.encode("utf-8"))
    return len(text)


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:'[^\W_]+)?", text.lower())


def check_locale(store: str, locale: str, fields: dict) -> list[Finding]:
    out: list[Finding] = []

    def add(field, check, sev, msg, fix):
        out.append(Finding(store, locale, field, check, sev, msg, fix))

    for field in REQUIRED[store]:
        if not str(fields.get(field) or "").strip():
            add(field, "field.missing", "medium", f"{field} is empty or missing", f"write a {field}")
    for field, value in fields.items():
        if field not in LIMITS[store]:
            add(field, "field.unknown", "info", f"unknown field '{field}' (not checked)", "check the field name")
            continue
        text = str(value or "")
        limit = LIMITS[store][field]
        n = measure(store, field, text)
        unit = "bytes" if (store, field) in BYTE_FIELDS else "chars"
        if n > limit:
            add(field, "length.over", "high", f"{n}/{limit} {unit}, {n - limit} over", f"cut to {limit} {unit}")
        if text != text.strip():
            add(field, "whitespace.edges", "low", "leading or trailing whitespace", "trim it")
        if OTHER_PLATFORM[store].search(text) and field != "keywords":
            word = OTHER_PLATFORM[store].search(text).group(0)
            add(
                field,
                "platform.other",
                "medium",
                f"mentions another platform ('{word}')",
                "remove references to the other store/platform",
            )
    short_fields = ("title", "short_description") if store == "play" else ("name", "subtitle")
    for field in short_fields:
        text = str(fields.get(field) or "")
        if not text:
            continue
        low = text.lower()
        promo = [w for w in PROMO_WORDS if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low)]
        if promo and store == "play":
            add(
                field,
                "policy.promotional",
                "medium",
                f"promotional/ranking words: {', '.join(promo)}",
                "Google Play metadata policy forbids ranking, price and promotion claims in title and short text",
            )
        if store == "appstore" and PRICE_RE.search(text):
            add(
                field,
                "policy.price",
                "medium",
                f"price or 'free' in {field}",
                "App Review rejects pricing terms in the name/subtitle; put them in the description",
            )
        if EMOJI_RE.search(text):
            add(field, "policy.emoji", "medium", "contains emoji or symbols", "remove emoji from titles")
        caps = [w for w in re.findall(r"\b[A-Z]{4,}\b", text) if w not in ACRONYMS]
        if caps:
            add(field, "style.all_caps", "low", f"ALL CAPS words: {', '.join(caps)}", "use title case")
        if re.search(r"[!?]{2,}|!\s*$", text):
            add(field, "style.punctuation", "low", "exclamation marks / repeated punctuation", "remove them")
    if store == "appstore":
        out += check_keywords(locale, fields)
    desc_field = "full_description" if store == "play" else "description"
    out += check_stuffing(store, locale, desc_field, str(fields.get(desc_field) or ""))
    notes = str(fields.get("release_notes") or "")
    if notes and GENERIC_NOTES.match(notes):
        add(
            "release_notes",
            "notes.generic",
            "info",
            "release notes only say 'bug fixes'",
            "name one or two user-visible changes",
        )
    return out


def check_keywords(locale: str, fields: dict) -> list[Finding]:
    out: list[Finding] = []
    raw = str(fields.get("keywords") or "")
    if not raw.strip():
        return out

    def add(check, sev, msg, fix):
        out.append(Finding("appstore", locale, "keywords", check, sev, msg, fix))

    if ";" in raw or "\n" in raw.strip():
        add("keywords.separator", "low", "keywords separated by ';' or newlines", "separate with commas only")
    if re.search(r",\s+|\s+,", raw):
        wasted = len(re.findall(r"\s+(?=,)|(?<=,)\s+", raw))
        add("keywords.spaces", "low", f"spaces around commas waste {wasted} byte(s)", "use 'a,b,c' with no spaces")
    terms = [t.strip().lower() for t in re.split(r"[,;\n]", raw) if t.strip()]
    seen, dups = set(), []
    for t in terms:
        if t in seen:
            dups.append(t)
        seen.add(t)
    if dups:
        add("keywords.duplicate", "low", f"duplicate keywords: {', '.join(sorted(set(dups)))}", "list each once")
    title_words = set(_words(str(fields.get("name") or "")) + _words(str(fields.get("subtitle") or "")))
    overlap = sorted({t for t in terms if t in title_words})
    if overlap:
        add(
            "keywords.in_title",
            "low",
            f"already in name/subtitle: {', '.join(overlap)}",
            "drop them; name and subtitle are indexed already",
        )
    filler = sorted({t for t in terms if t in {"app", "apps", "iphone", "ipad", "ios", "free", "apple"}})
    if filler:
        add("keywords.filler", "low", f"filler keywords: {', '.join(filler)}", "use the bytes for real search terms")
    plural = sorted({t for t in terms if t.endswith("s") and t[:-1] in seen})
    if plural:
        add("keywords.plural", "info", f"singular and plural both listed: {', '.join(plural)}", "keep one form")
    n = measure("appstore", "keywords", raw)
    if n < 80:
        add("keywords.unused", "info", f"only {n}/100 bytes used", "add more relevant search terms")
    return out


def check_stuffing(store: str, locale: str, field: str, text: str) -> list[Finding]:
    words = [w for w in _words(text) if w not in STOPWORDS and len(w) > 2]
    if len(words) < 60:
        return []
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    word, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    if n >= 8 and n / len(words) > 0.04:
        return [
            Finding(
                store,
                locale,
                field,
                "policy.keyword_stuffing",
                "medium" if store == "play" else "low",
                f"'{word}' repeated {n} times ({n * 100 // len(words)}% of words)",
                "write for people; Google Play treats repetitive keywords as spam",
            )
        ]
    return []


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip("\n")


def load_fastlane(path: Path) -> dict:
    """Load fastlane supply/deliver metadata from a project, fastlane/ or fastlane/metadata folder."""
    candidates = [path / "fastlane" / "metadata", path / "metadata", path]
    meta = next((c for c in candidates if c.is_dir() and any(c.iterdir())), None)
    listing: dict = {}
    if meta is None:
        return listing
    android = meta / "android" if (meta / "android").is_dir() else None
    if meta.name == "android":
        android, meta = meta, meta.parent
    if android:
        for loc in sorted(p for p in android.iterdir() if p.is_dir()):
            fields = {f: _read(loc / fn) for fn, f in SUPPLY_FILES.items() if (loc / fn).is_file()}
            changelogs = loc / "changelogs"
            if changelogs.is_dir():
                notes = sorted(changelogs.glob("*.txt"), key=lambda p: (p.stem != "default", p.stem))
                numbered = [p for p in notes if p.stem.isdigit()]
                pick = max(numbered, key=lambda p: int(p.stem)) if numbered else (notes[0] if notes else None)
                if pick:
                    fields["release_notes"] = _read(pick)
            if fields:
                listing.setdefault("play", {})[loc.name] = fields
    for loc in sorted(p for p in meta.iterdir() if p.is_dir() and p.name not in DELIVER_NON_LOCALE):
        fields = {f: _read(loc / fn) for fn, f in DELIVER_FILES.items() if (loc / fn).is_file()}
        if fields:
            listing.setdefault("appstore", {})[loc.name] = fields
    return listing


def normalize(data: dict) -> dict:
    if not isinstance(data, dict) or not ({"play", "appstore"} & set(data)):
        raise ValueError("listing JSON needs a 'play' and/or 'appstore' object")
    out: dict = {}
    for store in ("play", "appstore"):
        section = data.get(store)
        if not section:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"'{store}' must be an object")
        if any(k in LIMITS[store] for k in section):
            section = {"default": section}
        out[store] = section
    return out


def load(path: str) -> dict:
    if path == "-":
        return normalize(json.loads(sys.stdin.read()))
    p = Path(path)
    if p.is_dir():
        listing = load_fastlane(p)
        if not listing:
            raise ValueError(f"no fastlane metadata found under {p}")
        return listing
    return normalize(json.loads(p.read_text(encoding="utf-8")))


def check(listing: dict, stores: list[str] | None = None) -> tuple[list[Finding], list[dict]]:
    findings: list[Finding] = []
    usage: list[dict] = []
    for store, locales in listing.items():
        if stores and store not in stores:
            continue
        for locale, fields in locales.items():
            findings += check_locale(store, locale, fields)
            for field, value in fields.items():
                if field in LIMITS[store]:
                    usage.append(
                        {
                            "store": store,
                            "locale": locale,
                            "field": field,
                            "length": measure(store, field, str(value or "")),
                            "limit": LIMITS[store][field],
                            "unit": "bytes" if (store, field) in BYTE_FIELDS else "chars",
                        }
                    )
    return findings, usage


def print_limits() -> None:
    names = {"play": "Google Play", "appstore": "App Store"}
    for store, fields in LIMITS.items():
        print(names[store])
        for field, limit in fields.items():
            unit = "bytes" if (store, field) in BYTE_FIELDS else "characters"
            req = " (required)" if field in REQUIRED[store] else ""
            print(f"  {field:<18} {limit:>5} {unit}{req}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("path", nargs="?", help="listing.json, a fastlane metadata folder, or - for stdin")
    p.add_argument("--store", choices=["play", "appstore"], action="append", help="check only this store")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium", help="exit 1 at this severity")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info", help="hide findings below this")
    p.add_argument("--limits", action="store_true", help="print the field limits and exit")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    if args.limits:
        print_limits()
        return 0
    if not args.path:
        p.error("path is required (or use --limits)")
    try:
        listing = load(args.path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings, usage = check(listing, args.store)
    rank = SEVERITIES.index(args.min_severity)
    shown = [f for f in findings if SEVERITIES.index(f.severity) >= rank]
    if args.json:
        print(json.dumps({"usage": usage, "findings": [f.as_dict() for f in shown]}, indent=2, ensure_ascii=False))
    else:
        for u in usage:
            mark = "OVER" if u["length"] > u["limit"] else "ok"
            print(f"{u['store']:<8} {u['locale']:<8} {u['field']:<18} {u['length']:>5}/{u['limit']:<5} {mark}")
        if shown:
            print()
        for f in shown:
            print(f"{f.severity.upper():<6} {f.store}/{f.locale}/{f.field}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(shown)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
