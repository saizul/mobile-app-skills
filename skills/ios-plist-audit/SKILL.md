---
name: ios-plist-audit
description: Audit an iOS Info.plist (Flutter ios/Runner, React Native, Expo prebuild or native) with a deterministic plistlib script - infers needed capabilities from dependencies (pubspec.yaml, package.json), Swift/Objective-C API use, background modes and entitlements, then reports missing NS*UsageDescription keys (camera, microphone, photos, location, contacts, calendars, Bluetooth, Face ID, tracking, health, motion, NFC), empty, placeholder or vague purpose strings that App Review rejects (guideline 5.1.1), location key pairs, deprecated keys, App Transport Security exceptions (NSAllowsArbitraryLoads, insecure domains, TLS 1.0/1.1), missing export compliance key and privacy manifest. Use when the user asks to review iOS permissions or Info.plist, fix a crash on permission request, answer an App Review rejection about purpose strings or ATS, or prepare an App Store submission.
license: MIT
compatibility: Python 3.8+ standard library only (plistlib reads XML and binary plists). Works on any OS; no Xcode needed.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# iOS Info.plist audit

Make sure every protected resource the app touches has a clear purpose string, and that
network security exceptions are justified. Read-only; changes are proposed as a diff.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- App crashes the first time it opens the camera, photos, location or contacts
  ("This app has crashed because it attempted to access privacy-sensitive data without a
  usage description")
- App Review: "Guideline 5.1.1 - purpose string does not sufficiently explain", "ATS
  exception needs justification", "Missing purpose string in Info.plist" (ITMS-90683)
- Adding a Flutter plugin / React Native library that uses a device capability
- Pre-submission review of `ios/Runner/Info.plist` or `ios/<App>/Info.plist`

## When not to use

- Android permissions: `android-permissions-audit`
- Signing, provisioning, versions and TestFlight: `release-checklist`
- App Store listing text: `store-listing-writer`

## Workflow

1. **Locate files.** Flutter: `ios/Runner/Info.plist`, entitlements
   `ios/Runner/Runner.entitlements`. React Native: `ios/<AppName>/Info.plist`. Expo
   managed: purpose strings live in `app.json` (`ios.infoPlist`) or config plugins; run
   `npx expo prebuild --platform ios` in a scratch copy, or check `app.json` by hand.
   Build settings such as `$(PRODUCT_NAME)` are fine inside strings.
2. **Run the audit (read-only).**
   ```bash
   python3 scripts/plist_audit.py ios/Runner/Info.plist --project . \
     --entitlements ios/Runner/Runner.entitlements
   python3 scripts/plist_audit.py ios/MyApp/Info.plist --project . --json
   ```
   `--project` infers capabilities from `pubspec.yaml`, `package.json` and Swift/ObjC
   sources (skipping Pods, node_modules, build). Exit 1 = findings at or above
   `--fail-on` (default `medium`).
3. **Check the inference.** The script lists each inferred capability and why. A
   dependency can be present without the feature being used (e.g. `image_picker` only for
   the gallery). Ask the user which features are real; do not add purpose strings for
   unused capabilities. Apple still scans the binary for API references, so remove unused
   SDKs instead of leaving strings out.
4. **Write purpose strings** using [references/usage-descriptions.md](references/usage-descriptions.md):
   say what is accessed, why, and what the user gets, in one or two sentences, in the
   app's language (localize via `InfoPlist.strings`). Never "This app needs access to X".
5. **ATS exceptions:** prefer fixing the server (HTTPS, TLS 1.2+). Keep an exception only
   for a named host the user controls or a documented third-party need, and scope it to
   that domain; see [references/ats.md](references/ats.md). `NSAllowsArbitraryLoads`
   requires a written justification in App Review.
6. **Localized prompts** (with `--project`): `usage.untranslated` lists purpose strings
   missing from a locale's `InfoPlist.strings` / `InfoPlist.xcstrings` (users see the
   development-language text); `usage.localized_placeholder` is an empty or TODO
   translation. Add the translations next to the base string you wrote in step 4.
7. **Other findings:** set `ITSAppUsesNonExemptEncryption` to `false` only if the app
   uses no encryption beyond HTTPS and OS APIs (the user must confirm their export
   status); add a `PrivacyInfo.xcprivacy` to the app target if missing.
8. **Propose the plist diff** (XML `<key>/<string>` pairs) and wait for approval. Then
   re-run the audit.

## Output

```
iOS Info.plist audit: 3 high, 2 medium, 1 info
Capabilities: camera (image_picker), photos (image_picker), faceid (local_auth),
              location-always (UIBackgroundModes)

HIGH  NSLocationWhenInUseUsageDescription missing (needed with background location)
HIGH  NSFaceIDUsageDescription missing -> "Unlock Pocket Budget with Face ID instead of your passcode."
MED   NSCameraUsageDescription is vague ("This app needs the camera")
      -> "Scan paper receipts so Pocket Budget can fill in the amount and shop for you."
MED   ATS: plain HTTP for legacy-api.example.com and subdomains -> move the API to HTTPS

Proposed Info.plist diff: +3 keys, 1 string rewritten, 1 ATS exception removed.
```
