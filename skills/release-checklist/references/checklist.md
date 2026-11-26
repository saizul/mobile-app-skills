# Release checklist

Copy into the release ticket and mark each line `[x]`, `n/a` or `BLOCKED: reason`.

## Code and build

- [ ] Main branch green: unit, widget/component and integration tests, lints
- [ ] `release_preflight.py` passes (versions, signing, target SDK, secrets)
- [ ] Release build installed on a real low-end Android device and an older iPhone
- [ ] Release-only config checked: API base URLs, feature flags, analytics/crash keys
      for production, logging level, no debug menus
- [ ] R8/ProGuard on (Android) and mapping file uploaded to the crash reporter; dSYMs
      uploaded for iOS; Flutter `--obfuscate --split-debug-info` symbols archived if used
- [ ] Database / storage migrations tested from the previous store version (install old
      version, add data, upgrade)
- [ ] Deep links, push notifications, in-app purchases and login tested on the release build

## Store requirements

- [ ] `android-permissions-audit` and `ios-plist-audit`: no high findings
- [ ] Play Data safety form and App Store privacy labels still match what the app collects
- [ ] Target API level meets the current Play requirement
- [ ] Built with the Xcode/SDK version App Store Connect currently requires
- [ ] Export compliance (`ITSAppUsesNonExemptEncryption`) answered
- [ ] Account deletion available in-app if the app has accounts (both stores require it)
- [ ] Demo account and notes for App Review if login is required

## Listing

- [ ] Release notes / What's New written for every locale (`store-listing-writer`)
- [ ] Screenshots updated if the UI changed noticeably
- [ ] Support URL and privacy policy URL reachable

## Rollout

- [ ] Uploaded to Play internal testing / TestFlight; store build smoke-tested
- [ ] Rollout plan and stop rule written down (see rollout.md)
- [ ] Crash and ANR dashboards open; baseline from the previous version saved
- [ ] Backend compatible with both old and new app versions (no breaking API change
      until the old version is gone; consider a minimum-version gate)

## After release

- [ ] Git tag and changelog published
- [ ] Final build numbers recorded for the next preflight
- [ ] Reviews and support inbox checked after 24 hours
