# Versioning

Two numbers per platform:

| | Android | iOS | Flutter `pubspec.yaml` | Expo `app.json` |
| --- | --- | --- | --- | --- |
| User-visible version | `versionName` | `CFBundleShortVersionString` / `MARKETING_VERSION` | `version: 2.4.0+42` (before `+`) | `expo.version` |
| Build number | `versionCode` (integer, max 2100000000) | `CFBundleVersion` / `CURRENT_PROJECT_VERSION` | after `+` | `android.versionCode`, `ios.buildNumber` |

Rules:

- The build number must be higher than every build ever uploaded for that app (Play:
  across all tracks; App Store: per version train, but keep it increasing anyway).
- Marketing version: `MAJOR.MINOR.PATCH`. App Store requires it to increase after a
  version is released; you cannot reuse a released version.
- Keep the same marketing version on both platforms for the same feature set; it makes
  support and crash reports easier.
- Flutter overrides at build time: `flutter build appbundle --build-name=2.4.0 --build-number=42`.
- React Native: edit `android/app/build.gradle` (`versionCode`, `versionName`) and in
  Xcode the target's General tab (writes `MARKETING_VERSION` and
  `CURRENT_PROJECT_VERSION` for every configuration). `agvtool` and fastlane
  `increment_build_number` / `increment_version_code` (plugin) automate it.
- Expo with EAS: `"cli": {"appVersionSource": "remote"}` plus `"autoIncrement": true` in a
  build profile lets EAS manage build numbers.

Common schemes for the build number: a counter (`42`), CI run number, or a date-based
integer (`2026112601`). Pick one and never go back.
