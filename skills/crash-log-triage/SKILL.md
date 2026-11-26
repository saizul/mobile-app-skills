---
name: crash-log-triage
description: Triage mobile app crashes with a deterministic script that groups crash reports by signature (root exception type + first app frame) and ranks them by count - Android/Kotlin/Java stack traces and logcat FATAL EXCEPTION with Caused by chains, Flutter/Dart traces (Unhandled Exception, #0 frames), React Native JavaScript errors (Hermes/JSC bundles), Apple .crash text and .ips JSON reports, JSON/JSONL exports and Crashlytics BigQuery rows - scrubbing emails, ids and URLs from messages, flagging unsymbolicated frames and new signatures against a baseline. Then guides root-cause analysis and fixes per crash type (NPE, Bad state, null cast, undefined is not an object, EXC_BAD_ACCESS, SIGABRT, OOM, ANR). Use when the user pastes stack traces or crash exports, asks what the top crashes are, why the app crashes, or whether a new release introduced new crashes.
license: MIT
compatibility: Python 3.8+ standard library only. Works offline on exported files; never calls Crashlytics, Sentry or store APIs.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Crash log triage

Turn a pile of crash reports into a ranked list of distinct problems, then fix the top
ones with evidence from the code. Read-only until a fix is approved.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- The user pastes stack traces, logcat output, `.crash` / `.ips` files or a crash export
- "What are our top crashes?", "why does the app crash on launch?"
- "Did version 2.4.0 introduce new crashes?" (compare against a baseline)
- Crash-free rate dropped during a staged rollout

## When not to use

- ANR / slow frames without a stack trace: profile first (Android Studio profiler,
  Flutter DevTools, React Native performance monitor), see the best-practices skills
- Store rejections and policy issues: `release-checklist`, the audit skills
- Pulling data from Crashlytics/Sentry/Play Console: the user exports it (see
  [references/exports.md](references/exports.md)); scripts never call those services

## Workflow

1. **Get the data, safely.** Ask for exported files rather than pasted customer data:
   logcat (`adb logcat -d -b crash > crash.txt`), Xcode Organizer / device `.ips` files,
   Crashlytics BigQuery export, Sentry or Play Console stack traces saved as text. Crash
   reports can contain personal data; work on files locally and quote only frames.
2. **Symbolicate first if needed.** Obfuscated Android frames (`a.b.c`) need the R8
   `mapping.txt` (`retrace`), iOS addresses need dSYMs, Flutter `--obfuscate` builds need
   `flutter symbolize -i trace.txt -d symbols/app.android-arm64.symbols`, Hermes bundles
   need source maps. Commands in [references/exports.md](references/exports.md).
3. **Group and rank (read-only).**
   ```bash
   python3 scripts/triage_crashes.py crashes/ --app com.example.app --app package:my_app
   python3 scripts/triage_crashes.py export.json --json --top 50 > baseline-2.3.0.json
   python3 scripts/triage_crashes.py crashes-2.4.0/ --baseline baseline-2.3.0.json
   ```
   `--app` sets which frames are "yours" (otherwise framework prefixes are skipped
   automatically). `--keep-lines` splits groups by line number. With `--baseline` the
   exit code is 1 when new signatures appear (useful as a rollout gate).
4. **Pick the top 3 groups** by count and by severity (launch crashes and data loss
   beat rare edge cases). For each, read the app frame's source file around the line.
5. **Find the root cause** using the patterns in [references/patterns.md](references/patterns.md):
   what value was null/empty/out of range, which lifecycle state, which thread, which
   versions/OS (look at the group's `versions`). State the evidence; mark guesses as guesses.
6. **Propose the fix** as a minimal diff plus a regression test that reproduces the
   crash input (unit test for parsing, widget/component test for UI state). Wait for
   approval before editing.
7. **Verify**: after the fix ships, re-run with the old output as `--baseline` and check
   the signature is gone or falling.

## Output

```
Crash triage: 412 reports, 9 groups (Android 7, iOS 2), versions 2.3.0-2.4.0

#1  58%  java.lang.IllegalStateException @ com.example.app.data.BudgetRepository.load
         "Budget <n> not found for user <email>" - 2.4.0 only (NEW)
         Cause: load() runs before sync finishes on first launch (BudgetRepository.kt:88)
         Fix: return empty state + trigger sync; test: first-launch repository test
#2  21%  TypeError @ bundle BudgetSummary - undefined budget.items while loading
#3   9%  EXC_BAD_ACCESS (SIGSEGV) @ Runner <unsymbolicated> -> upload dSYMs for 2.4.0 (41)

Next: fix #1 (diff below), symbolicate #3, re-run against baseline after 2.4.1.
```
