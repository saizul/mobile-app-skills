---
name: app-size-reduction
description: Measure and reduce Android and iOS app size for Flutter and React Native - a script reads an .apk, .aab or .ipa directly (as a zip), `bundletool get-size total` CSV, Flutter `--analyze-size` JSON or an `unzip -l` listing, and reports size by category (dex, native libs per ABI, Flutter engine and Dart AOT code, Hermes/JS bundle, assets, resources, frameworks), largest files, and findings - universal APKs with several ABIs, unstripped native libraries, JS bundles not compiled to Hermes bytecode, Flutter debug builds, heavy images and fonts, duplicate files, no R8 mapping, and a size budget for CI. Then a prioritized guide: AAB and ABI splits, R8 and resource shrinking, image formats, deferred components, asset delivery, Hermes, dependency pruning, iOS app thinning. Use when the user says the app is too big, download size grew, wants a size budget in CI, or asks what is inside their APK/AAB/IPA.
license: MIT
compatibility: Python 3.8+ standard library only (zipfile). Optional inputs come from bundletool, apkanalyzer or the Flutter CLI, which the user runs.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# App size reduction

Measure first, cut the biggest categories, and keep the result with a budget. Always
compare release builds; debug builds are several times larger and meaningless.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Why is my APK 80 MB?", "reduce app size", "download size increased in this release"
- Play Console warns about size, or users on slow networks drop off at install
- Setting up a size budget check in CI
- Comparing what Flutter engine, Dart code, Hermes bundle and assets each cost

## When not to use

- Runtime memory or startup time (different problem): `flutter-best-practices` /
  `react-native-best-practices`
- Store listing or release process: `store-listing-writer`, `release-checklist`

## Workflow

1. **Build release artifacts** (the user runs these):
   - Flutter: `flutter build appbundle --release` and `flutter build apk --analyze-size --target-platform android-arm64`
     (writes `apk-code-size-analysis_*.json`, path printed at the end), iOS:
     `flutter build ipa --analyze-size`.
   - React Native: `cd android && ./gradlew bundleRelease` (`app/build/outputs/bundle/release/app-release.aab`),
     iOS: archive in Xcode, export an `.ipa` (Ad Hoc or App Store Connect).
   - Real per-device download sizes from an AAB (needs `bundletool`):
     ```bash
     bundletool build-apks --bundle=app-release.aab --output=app.apks
     bundletool get-size total --apks=app.apks --dimensions=ABI,SCREEN_DENSITY > size.csv
     ```
2. **Run the report (read-only).**
   ```bash
   python3 scripts/size_report.py app-release.aab
   python3 scripts/size_report.py app-release.apk --json
   python3 scripts/size_report.py size.csv --budget-mb 30
   python3 scripts/size_report.py ~/.flutter-devtools/apk-code-size-analysis_01.json
   ```
   Exit 1 = findings at or above `--fail-on` (default `high`, which includes a budget
   overrun). Nothing is extracted or executed.
3. **Read the category table** and work top-down. Typical big items and their levers are
   in [references/techniques.md](references/techniques.md):
   - Native libraries per ABI -> ship an AAB (Play splits per ABI) or `--split-per-abi`
   - Flutter engine is fixed cost (~4-6 MB per ABI compressed); Dart AOT code shrinks with
     fewer/lighter packages, `--split-debug-info` and deferred components
   - Assets/images -> WebP/AVIF, correct resolution, remove unused, download on demand
   - dex -> R8 (`isMinifyEnabled`, `isShrinkResources`), drop heavy SDKs
   - JS bundle -> Hermes bytecode, remove moment/lodash-style heavyweights
4. **Find what pulls weight in code**: Flutter DevTools App Size tool (open the
   `--analyze-size` JSON), `npx react-native-bundle-visualizer` or
   `source-map-explorer` for the JS bundle, `./gradlew :app:dependencies` for Android
   libraries, Xcode's App Thinning Size Report (export with "App Thinning: All
   compatible device variants").
5. **Propose changes** ordered by bytes saved per effort, each with the expected saving
   and risk (R8 needs keep rules for reflection; WebP needs minSdk 18+ for alpha).
   Wait for approval before editing build files or deleting assets.
6. **Re-measure** with the same command and report before/after per category.
7. **Lock it in**: add `size_report.py <artifact> --budget-mb N` to CI, set N a bit above
   the new size.

## Output

```
app-release.aab (Flutter): 31.4 MB compressed, max download 18.2 MB (arm64, xxhdpi)

  Flutter engine (libflutter.so)   11.2 MB  36%
  Dart code (libapp.so)             8.9 MB  28%
  Flutter assets                    7.1 MB  23%   <- 5.8 MB of PNG onboarding images
  dex (Kotlin/Java)                 2.6 MB   8%

Plan (saving / effort):
  1. Onboarding PNG -> WebP at 2x                -4.5 MB  low
  2. Remove unused fonts (6 weights -> 2)        -1.1 MB  low
  3. Deferred component for the PDF export        -2.0 MB  medium
CI budget: size_report.py app-release.aab --budget-mb 26
```
