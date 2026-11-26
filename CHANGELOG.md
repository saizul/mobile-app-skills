# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-26

### Added

- `store-listing-writer`: `check_listing.py` validates Google Play (title 30, short
  description 80, full description 4000, release notes 500) and App Store fields (name 30,
  subtitle 30, keywords 100 bytes, promotional text 170, description and What's New 4000)
  per locale from listing JSON or fastlane supply/deliver metadata; flags promotional
  words, prices, emoji, ALL CAPS, other-platform mentions, keyword stuffing and wasted
  keyword bytes. Writing guide and fastlane layout reference.
- `android-permissions-audit`: `manifest_audit.py` for dangerous and Play-restricted
  permissions, legacy storage, permissions without usage hints, foreground service types,
  exported components, missing `android:exported`, debuggable, cleartext, backup rules
  and network security config.
- `ios-plist-audit`: `plist_audit.py` infers capabilities from dependencies, Swift/ObjC
  APIs, background modes and entitlements; reports missing, empty, placeholder and vague
  usage descriptions, location key pairs, deprecated keys, ATS exceptions, export
  compliance, query scheme limit and missing privacy manifest.
- `release-checklist`: `release_preflight.py` for version/build numbers across Flutter,
  React Native, Expo, Gradle and Xcode, debug-signed release builds, hard-coded keystore
  passwords, signing files not git-ignored, target SDK and R8; checklist, signing,
  versioning and rollout references.
- `crash-log-triage`: `triage_crashes.py` groups Android, Flutter, React Native and Apple
  crash reports (text, `.ips`, JSON/JSONL, Crashlytics BigQuery) by signature with
  scrubbed messages, versions and baseline comparison; export and fix-pattern references.
- `app-size-reduction`: `size_report.py` for APK/AAB/IPA archives, bundletool CSV, Flutter
  `--analyze-size` JSON and listings, with ABI, debug-symbol, Hermes, image, font,
  duplicate and budget findings; techniques reference.
- `flutter-best-practices`: `flutter_audit.py` for dependency hygiene, lint setup, mixed
  state management and common build/performance/security mistakes; lints, state
  management and performance references.
- `react-native-best-practices`: `rn_audit.py` for Hermes, New Architecture flags,
  deprecated packages and common performance/security mistakes; New Architecture and
  performance references.
- Claude Code plugin marketplace manifest, `tools/validate_skills.py`, CI and release workflows.

[Unreleased]: https://github.com/saizul/mobile-app-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/mobile-app-skills/releases/tag/v0.1.0
