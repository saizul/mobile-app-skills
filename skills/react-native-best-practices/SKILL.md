---
name: react-native-best-practices
description: Review and improve React Native and Expo apps - Hermes engine, the New Architecture (Fabric, TurboModules, bridgeless; the only architecture from React Native 0.82, opt-out last possible in 0.81 / Expo SDK 54), upgrades, library choices, list and animation performance (FlatList/FlashList, memoization, Reanimated, native driver), startup and bundle size, secure storage and release config. A script audits package.json, app.json, gradle.properties, Podfile, babel config and JS/TS sources for Hermes disabled, New Architecture opt-outs or dead flags, deprecated or heavy packages (moment, full lodash, react-native-camera, old async-storage), ScrollView with mapped children, FlatList without keyExtractor, useNativeDriver false, console.log not stripped, tokens in AsyncStorage, plain HTTP and R8 off. Use when the user asks to review a React Native or Expo codebase, upgrade React Native, enable Hermes or the New Architecture, fix slow lists or janky animations, or prepare an RN app for production.
license: MIT
compatibility: Python 3.8+ standard library only. The script is a static pre-check; the React Native CLI, Expo Doctor and profilers remain the source of truth.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# React Native best practices

Current guidance for production React Native and Expo apps, with a quick static audit.
Recommend and prove with measurements; upgrades and architecture changes happen only
after the user agrees.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Review my React Native app", "is this ready for production?"
- "Should we enable Hermes / the New Architecture?", "upgrade to the latest React Native"
- Slow lists, dropped frames, janky animations, slow startup
- A library broke after an upgrade or does not support the New Architecture

## When not to use

- Flutter apps: `flutter-best-practices`
- App size deep dive: `app-size-reduction`; production crashes: `crash-log-triage`
- Permissions and plist strings: `android-permissions-audit`, `ios-plist-audit`

## Workflow

1. **Collect versions and health with the official tools** (the user runs them):
   ```bash
   npx react-native info          # bare React Native
   npx expo-doctor                # Expo projects
   npx tsc --noEmit && npx eslint . && npm test
   ```
2. **Run the audit (read-only).**
   ```bash
   python3 scripts/rn_audit.py .
   python3 scripts/rn_audit.py . --json --min-severity low
   ```
   Exit 1 = findings at or above `--fail-on` (default `medium`). Code findings are
   line-based heuristics: confirm in the file before calling them bugs.
3. **Engine and architecture** ([references/new-architecture.md](references/new-architecture.md)):
   - `engine.hermes_off`: turn Hermes back on unless a measured blocker exists.
   - `arch.legacy` (React Native 0.81 or older with the New Architecture disabled): list
     native dependencies, check each on reactnative.directory, plan replacement of
     unsupported ones, enable, test on both platforms, then upgrade.
   - `arch.dead_flag` (0.82+): remove the ignored opt-out flags.
4. **Upgrades**: one minor version at a time for big jumps, with the React Native Upgrade
   Helper diff (bare) or `npx expo install --fix` after bumping the SDK (Expo). Rebuild
   native apps (`pod install`, clean Gradle) and run the full test matrix.
5. **Performance** ([references/performance.md](references/performance.md)): profile a
   release build first (React DevTools Profiler, Perf Monitor, Android Studio / Instruments),
   then fix lists, re-renders and animations. Report before/after numbers.
6. **Security and release config**: tokens in Keychain/Keystore
   (`react-native-keychain`, `expo-secure-store`), HTTPS only, R8 on, console logs
   stripped in production, no secrets in the JS bundle (it is readable).
7. **Report and propose** prioritized small diffs (correctness > engine/architecture >
   performance > style); apply after approval and re-run tools and the audit.

## Output

```
React Native review (react-native 0.79.5, bare): 3 medium, 5 low

MED  Hermes disabled (gradle.properties, Podfile) -> remove both flags, rebuild
MED  New Architecture opted out; 0.81 is the last version allowing it
     -> 2 of 23 native libs unsupported: react-native-camera (-> vision-camera), X (fork)
MED  src/auth/session.ts:7 token in AsyncStorage -> react-native-keychain
LOW  ScrollView + map for 400 transactions -> FlashList, estimated item size 72

Plan: Hermes on (1 PR) > replace camera lib > enable New Architecture > upgrade to 0.83.
```
