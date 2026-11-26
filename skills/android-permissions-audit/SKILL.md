---
name: android-permissions-audit
description: Audit an AndroidManifest.xml (Flutter, React Native or native, source or merged release manifest) with a deterministic script - dangerous runtime permissions, Google Play restricted permissions that need a declaration or get apps rejected (SMS, call log, background location, MANAGE_EXTERNAL_STORAGE, QUERY_ALL_PACKAGES, exact alarms, full-screen intents, photo/video access), legacy storage permissions, permissions with no usage in the code, exported activities, services, receivers and providers without a permission, missing android:exported, debuggable builds, cleartext traffic, backup rules and network security config (cleartext, user CAs). Use when the user asks to review Android permissions, prepare a Play Console permissions declaration or Data safety form, fix a Play policy rejection, harden the manifest, or before a release.
license: MIT
compatibility: Python 3.8+ standard library only (xml.etree). Reads text manifests; decode binary manifests from an APK first.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Android permissions audit

Find permissions and manifest settings that cause Play rejections, security holes or
needless permission prompts, and propose the smallest safe fix. Read-only.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Which permissions does my app request and why?", "remove unused permissions"
- Play Console rejection or warning: "Permissions declaration form", "SMS and Call Log",
  "background location", "All files access", "QUERY_ALL_PACKAGES", "Photo and video permissions"
- Filling the Data safety form or a security review of exported components
- Build error "android:exported needs to be explicitly specified"
- Before every release that adds a plugin or SDK (plugins add permissions silently)

## When not to use

- iOS permissions and usage strings: `ios-plist-audit`
- Signing, versioning and rollout: `release-checklist`
- Runtime crash from a denied permission: `crash-log-triage` first, then come back

## Workflow

1. **Locate the manifests.**
   - Flutter / React Native source: `android/app/src/main/AndroidManifest.xml`
   - Merged manifest (includes every library's permissions; preferred). Build once, then:
     ```bash
     cd android && ./gradlew :app:processReleaseMainManifest   # or assembleRelease
     find android/app/build -path '*merged*' -name AndroidManifest.xml
     ```
   - From an APK the manifest is binary: decode it with
     `apkanalyzer manifest print app.apk > AndroidManifest.xml` (Android SDK cmdline-tools).
   - targetSdk usually lives in Gradle (`android/app/build.gradle[.kts]`), pass it with `--gradle`.
2. **Run the audit (read-only).**
   ```bash
   python3 scripts/manifest_audit.py android/app/src/main/AndroidManifest.xml \
     --gradle android/app/build.gradle --source . --res android/app/src/main/res
   python3 scripts/manifest_audit.py merged/AndroidManifest.xml --target-sdk 36 --json
   ```
   `--source` scans Dart/Kotlin/Java/JS and dependency files for usage hints, `--res`
   resolves `@xml/network_security_config`. Exit 1 = findings at or above `--fail-on`
   (default `medium`).
3. **Triage high findings first** (meaning and fixes in
   [references/permissions.md](references/permissions.md)):
   1. `app.debuggable`, `component.exported` on providers: security holes; fix now.
   2. `permission.restricted`: remove unless it is the app's core feature; otherwise the
      user must file the Play Console declaration (with video for background location).
   3. `component.exported_missing`: the build fails on targetSdk 31+.
   4. Cleartext and user CAs: move to a debug-only network config.
4. **Find who added a permission** when it is not in the source manifest: open the
   merged manifest report `android/app/build/outputs/logs/manifest-merger-release-report.txt`
   and search for the permission. Then decide: replace the library, configure it, or
   strip the permission:
   ```xml
   <uses-permission android:name="android.permission.READ_PHONE_STATE" tools:node="remove" />
   ```
   (needs `xmlns:tools="http://schemas.android.com/tools"` on `<manifest>`). Only strip
   it after checking the library still works without it.
5. **Check alternatives that avoid permissions** (references): photo picker instead of
   READ_MEDIA_*, SMS Retriever instead of READ_SMS, `<queries>` instead of
   QUERY_ALL_PACKAGES, coarse instead of fine location, inexact alarms.
6. **Propose a diff** to the manifest(s) and wait for approval. Never edit
   `build/` outputs; change the source manifest or the library configuration.
7. **Re-run** on the new merged manifest and list what changed.
8. **Data safety / declarations:** summarise each remaining sensitive permission with the
   feature that uses it, so the user can fill the Play Console forms accurately.

## Output

```
Android manifest audit (merged release, targetSdk 36): 2 high, 3 medium, 4 low

HIGH  provider .data.ExpenseProvider exported without permission
      -> android:exported="false" (only the app reads it)
HIGH  READ_SMS (added by com.example:otp-sdk) - restricted by Play SMS policy
      -> switch to SMS User Consent API, strip with tools:node="remove"
MED   usesCleartextTraffic="true" -> debug-only network_security_config
LOW   READ_CONTACTS: no usage found in code -> remove

Proposed diff: AndroidManifest.xml (+3 -2). Remaining sensitive permissions for the
Data safety form: CAMERA (receipt scanning), ACCESS_COARSE_LOCATION (shop tagging).
```
