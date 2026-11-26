# fastlane metadata layout

The checker reads the layouts written by `fastlane supply init` (Google Play) and
`fastlane deliver init` (App Store). Point it at the project root, `fastlane/` or
`fastlane/metadata/`.

```
fastlane/metadata/
  android/                         # fastlane supply
    en-US/
      title.txt                    -> play title
      short_description.txt        -> play short_description
      full_description.txt         -> play full_description
      changelogs/
        42.txt                     -> release notes for versionCode 42 (highest number is checked)
        default.txt                -> used when no numbered file exists
  en-US/                           # fastlane deliver
    name.txt                       -> appstore name
    subtitle.txt                   -> appstore subtitle
    keywords.txt                   -> appstore keywords
    promotional_text.txt           -> appstore promotional_text
    description.txt                -> appstore description
    release_notes.txt              -> appstore release_notes (What's New)
  review_information/              # skipped (not a locale)
  trade_representative_contact_information/   # skipped
```

A trailing newline in each file is ignored. Other files (`video.txt`, `privacy_url.txt`,
`copyright.txt`) are not checked.

## Listing JSON

For projects without fastlane, write `listing.json`:

```json
{
  "play": {
    "en-US": {"title": "", "short_description": "", "full_description": "", "release_notes": ""}
  },
  "appstore": {
    "en-US": {"name": "", "subtitle": "", "keywords": "", "promotional_text": "",
              "description": "", "release_notes": ""}
  }
}
```

The locale level is optional (`{"play": {"title": "..."}}` is checked as locale `default`).

## CI

```yaml
- run: python3 path/to/check_listing.py fastlane/metadata --fail-on medium
```
