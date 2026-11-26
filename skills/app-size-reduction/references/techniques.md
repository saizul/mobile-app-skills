# Size reduction techniques

Ordered roughly by typical saving per effort.

## Android (all frameworks)

| Technique | How | Saves | Risk |
| --- | --- | --- | --- |
| Ship an App Bundle | Upload `.aab`; Play generates per-ABI, per-density, per-language APKs | 30-60% vs universal APK | None |
| ABI filters | `ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }` drops x86/x86_64 | 1 ABI per filter removed | Emulators need a debug build |
| R8 minify + resource shrinking | `isMinifyEnabled = true`, `isShrinkResources = true` in `release` | 10-40% of dex, unused res | Keep rules for reflection (Gson, Retrofit models) |
| Strip native debug symbols | AGP strips by default; check `packaging { jniLibs { keepDebugSymbols ... } }` is not set | MBs per lib | Upload symbols to Play for crash reports |
| WebP / vector drawables | Android Studio "Convert to WebP"; VectorDrawable for icons | 25-80% per image | Lossy settings: review visually |
| Remove unused resources and locales | `resourceConfigurations += listOf("en", "de")` in `defaultConfig` (recent AGP versions replace it with `androidResources.localeFilters`) | Library strings for 80+ locales | Keep locales you support |
| Play Asset Delivery / Feature Delivery | Move large assets or rarely used features into on-demand packs | Large | More code paths |
| Drop heavy SDKs | Audit with `./gradlew :app:dependencies`; replace full SDKs with lighter ones | Varies | Feature parity |

## Flutter

- `flutter build appbundle` for Play; for direct APKs use `--split-per-abi`.
- `--split-debug-info=build/symbols --obfuscate` moves symbols out of `libapp.so`
  (keep the folder to symbolize crashes).
- `flutter build apk --analyze-size --target-platform android-arm64` and open the JSON in
  DevTools > App Size to see which packages are biggest.
- Assets: only declare folders you need in `pubspec.yaml` (`assets:` includes everything
  in a listed folder); compress images; prefer `.webp`; use resolution-aware variants
  (`2.0x/`, `3.0x/`) sensibly.
- Fonts: subset, keep only used weights; Material icons are tree-shaken in release unless
  you use `--no-tree-shake-icons` or dynamic `IconData` (which disables it).
- Deferred components (Android): `deferred as` imports plus `deferred-components` in
  `pubspec.yaml` for big, rarely used features.
- Drop packages that bundle native SDKs you do not use (full Firebase suites, map SDKs).

## React Native

- Hermes (default since 0.70) compiles the bundle to bytecode: smaller and faster startup.
  The script reports a plain-JS bundle as `js.not_hermes`.
- Enable R8 for release: `def enableProguardInReleaseBuilds = true` and keep rules
  required by libraries.
- Bundle analysis: `npx react-native-bundle-visualizer` or
  `npx source-map-explorer index.android.bundle index.android.bundle.map`.
- Replace heavy JS dependencies: `moment` -> `date-fns`/`dayjs`/`Intl`, full `lodash` ->
  per-method imports, large icon fonts -> only the icon sets used.
- Images: `require()`d images are bundled for every density you provide; ship WebP, and
  load large media from a CDN.
- Remove unused native modules (each adds native code for every ABI).

## iOS

- The App Store thins apps per device; measure with an App Thinning Size Report, not the
  `.ipa` size. Universal `.ipa` file size overstates what users download.
- Asset catalogs (`Assets.xcassets`) enable per-device slicing; avoid loose PNGs.
- Strip debug symbols in Release (`STRIP_INSTALLED_PRODUCT = YES`, `DEBUG_INFORMATION_FORMAT = dwarf-with-dsym`)
  and keep the dSYM for crash reports.
- On-Demand Resources for large optional content.
- Flutter: `Flutter.framework` is fixed cost; App.framework (Dart AOT) shrinks with the
  same Dart-side techniques as Android.

## Budgets in CI

```yaml
- run: python3 tools/size_report.py build/app/outputs/bundle/release/app-release.aab --budget-mb 35
```

Track the compressed size per release in the changelog so growth is visible in review.
