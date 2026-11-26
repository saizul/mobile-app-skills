# Getting and symbolicating crash data

## Inputs the script understands

| Source | How to get it | Notes |
| --- | --- | --- |
| Android logcat | `adb logcat -d -b crash > crash.txt` (crash buffer) or `adb logcat -d > all.txt` | `E AndroidRuntime:` and `E/flutter (pid):` prefixes are stripped |
| Play Console | Quality > Android vitals > Crashes and ANRs > open a cluster > copy stack trace into a `.txt` | One file can hold many traces; separate them with a blank line or `---` |
| Flutter | Console output, `FlutterError.onError` / `PlatformDispatcher.instance.onError` logs | `#0 ...(package:app/file.dart:12:5)` frames |
| React Native | Red box / LogBox text, `ErrorUtils` handler logs, Sentry "raw" stack trace | V8-style `at fn (file:line:col)` and `fn@file:line:col` frames |
| iOS device / TestFlight | Xcode > Window > Organizer > Crashes, or Settings > Privacy > Analytics Data (`.ips`) | `.ips` is JSON (header line + body); `.crash` is text |
| Crashlytics | BigQuery export (`firebase_crashlytics.<table>`), e.g. `SELECT * ... LIMIT 1000` saved as JSON | Uses `exceptions[].frames[]` and `owned` / `blamed` flags |
| Sentry, Bugsnag, custom | JSON array or JSONL of objects with a stack string (`stacktrace`, `stack`, `exception`, ...) | Optional `count`, `app_version` fields |

## Symbolication

- **Android R8/ProGuard**: `retrace mapping.txt obfuscated.txt > clear.txt`
  (`retrace` ships with the Android SDK cmdline-tools / R8). Keep `mapping.txt` per
  release (`android/app/build/outputs/mapping/release/`); Play Console de-obfuscates if
  you upload it there.
- **Android native (NDK, libflutter.so, libhermes.so)**: `ndk-stack -sym obj/local/arm64-v8a -dump tombstone.txt`;
  upload native debug symbols to Play Console (`ndk { debugSymbolLevel 'FULL' }`).
- **iOS**: download dSYMs from Xcode Organizer or App Store Connect; Xcode symbolicates
  `.ips` files dropped onto the device logs window; `atos -arch arm64 -o App.dSYM/Contents/Resources/DWARF/App -l <load address> <address>`
  for single frames.
- **Flutter obfuscated / split debug info**:
  `flutter symbolize -i trace.txt -d build/symbols/app.android-arm64.symbols`
  (keep the `--split-debug-info` directory for every release).
- **React Native Hermes**: generate source maps in release builds and use
  `npx metro-symbolicate index.android.bundle.map < trace.txt`, or upload maps to the
  crash reporter.

## Baselines for rollouts

```bash
python3 scripts/triage_crashes.py vitals-2.3.0/ --json --top 200 > baseline-2.3.0.json
python3 scripts/triage_crashes.py vitals-2.4.0/ --baseline baseline-2.3.0.json || echo "new crash signatures"
```
