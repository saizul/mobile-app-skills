---
name: release-checklist
description: Ship a Flutter, React Native or Expo app to Google Play and the App Store safely - a preflight script checks version name and build number per platform (pubspec.yaml version+build, Gradle versionCode/versionName, Xcode MARKETING_VERSION/CURRENT_PROJECT_VERSION, Expo app.json) against the last uploaded build, release builds signed with the debug key, hard-coded keystore passwords, keystores and key.properties not git-ignored, targetSdk below the Play requirement and R8 off; then a step-by-step checklist for signing (Play App Signing, upload key, certificates), internal/closed testing and TestFlight, staged rollout and phased release, halting a bad rollout, release notes and post-release monitoring. Use when the user is preparing a release, bumping versions, asks how to roll out gradually or roll back, or an upload was rejected for version code, signing or target API level.
license: MIT
compatibility: Python 3.8+ standard library only. Reads project files; never builds, signs or uploads.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Release checklist

A repeatable path from "main is green" to "100% of users", with a deterministic
preflight for the mistakes stores reject. The agent checks and prepares; the user (or
their CI) builds, signs, uploads and presses the rollout buttons.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Prepare release 2.4.0", "bump the version", "what do I need before submitting?"
- Upload errors: "Version code 41 has already been used", "You uploaded an APK or Android
  App Bundle that was signed in debug mode", "Your app currently targets API level 34",
  "The bundle version must be higher than the previously uploaded version"
- "How do I do a staged rollout / phased release?", "how do I stop a bad release?"

## When not to use

- Writing store text: `store-listing-writer`
- Permission and plist problems found during review: `android-permissions-audit`,
  `ios-plist-audit`
- App too big: `app-size-reduction`. Crash spike after release: `crash-log-triage`

## Workflow

1. **Collect the release facts**: target version (semver), last build numbers on each
   store (Play Console > Test and release > App bundle explorer; App Store Connect >
   TestFlight builds), what changed since the last tag (`git log --oneline vLAST..HEAD`).
2. **Run the preflight (read-only).**
   ```bash
   python3 scripts/release_preflight.py . --previous-android 41 --previous-ios 41 --previous-version 2.3.0
   python3 scripts/release_preflight.py . --json
   ```
   Exit 1 = findings at or above `--fail-on` (default `medium`). Secret values are never
   printed. `--min-target-sdk` defaults to the current Play requirement (36); check
   [the Play target API page](https://developer.android.com/google/play/requirements/target-sdk)
   when in doubt.
3. **Fix blockers**, proposing each change first:
   - Versions: see [references/versioning.md](references/versioning.md). Flutter: one
     line `version: 2.4.0+42` in `pubspec.yaml`. React Native: Gradle and Xcode separately.
   - Signing: see [references/signing.md](references/signing.md). Never generate,
     move or print keys or passwords yourself; give the user the commands.
   - Keystore or `key.properties` not ignored: add to `.gitignore`; if it was committed,
     the user must treat it as leaked (rotate the upload key via Play Console support).
4. **Walk the checklist** in [references/checklist.md](references/checklist.md): tests and
   lint, release build on a real device, permissions and plist audits, store listing and
   release notes, privacy forms, tag. Mark each item done / not applicable / blocked.
5. **Upload to testing first**: Play internal testing track, TestFlight internal group.
   Smoke-test the store-installed build (not a local build).
6. **Roll out gradually** ([references/rollout.md](references/rollout.md)): Play staged
   rollout (e.g. 1% > 5% > 20% > 50% > 100%), App Store phased release (7 days). Define
   the stop rule before starting: crash-free users below the previous version, a new top
   crash, ANR spike, payment or login failures.
7. **Monitor and decide** at each step with crash/ANR data (`crash-log-triage` to group
   new crashes against the previous version's baseline). To stop: Play "Halt rollout",
   App Store "Pause phased release". Fix forward with a higher build number; stores do
   not allow re-uploading the same number.
8. **Close the release**: tag `v2.4.0`, publish the changelog, record final build
   numbers for the next preflight.

## Output

```
Release 2.4.0 preflight (flutter)
  android 2.4.0 (42)  ios 2.4.0 (42)  previous 41/41
  BLOCKER  release build signed with the debug key (android/app/build.gradle.kts)
  BLOCKER  targetSdk 34 < 36 required by Google Play
  OK       build numbers increase, keystore files ignored

Checklist: 14/18 done, 2 blocked, 2 n/a
Rollout plan: Play 1% (24h) > 10% > 50% > 100%; App Store phased release on
Stop if crash-free users < 99.5% or a new crash group > 0.2% of sessions.
```
