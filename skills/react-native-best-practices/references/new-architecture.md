# Hermes and the New Architecture

## Timeline (check the React Native blog for later changes)

| Version | Change |
| --- | --- |
| 0.70 | Hermes is the default JS engine |
| 0.74 | Bridgeless mode default when the New Architecture is on |
| 0.76 | New Architecture enabled by default for new and upgraded apps |
| 0.81 / Expo SDK 54 | Last versions that allow disabling the New Architecture |
| 0.82 | Runs only on the New Architecture; `newArchEnabled=false` / `RCT_NEW_ARCH_ENABLED=0` are ignored |
| 0.84 | Hermes V1 is the default engine |

## Flags

| Where | Hermes | New Architecture |
| --- | --- | --- |
| `android/gradle.properties` | `hermesEnabled=true` | `newArchEnabled=true` |
| `ios/Podfile` | `:hermes_enabled => true` (default) | `RCT_NEW_ARCH_ENABLED=1` env at `pod install` (pre-0.76 opt-in) |
| Expo `app.json` | `jsEngine` (omit for Hermes) | `newArchEnabled` |

## Migration plan for apps still on the legacy architecture

1. Upgrade to 0.81 (or Expo SDK 54) with the legacy architecture still allowed.
2. Inventory native dependencies: `npx react-native config` (bare) or package.json;
   check each on https://reactnative.directory (filter "New Architecture").
3. For unsupported libraries: upgrade, switch to a maintained alternative, or patch
   (`patch-package`). The interop layer runs many legacy modules, but not all.
4. Enable the New Architecture, clean builds (`cd ios && pod install`,
   `cd android && ./gradlew clean`), run the full manual and automated test pass on both
   platforms, including release builds.
5. Watch for: libraries using `UIManager` or `findNodeHandle` directly, `setNativeProps`
   in older code, custom native modules (convert to TurboModules with Codegen specs),
   layout differences from Fabric's synchronous layout.
6. After a stable release, upgrade past 0.82 where the legacy path no longer exists.

## Hermes notes

- Debug with the React Native DevTools (Chrome DevTools-based) rather than remote JS
  debugging, which Hermes does not support.
- `Intl` support is available in Hermes; very old polyfills (`intl`) can be removed.
- Generate and upload source maps for release crash symbolication.
- If an app disabled Hermes years ago for a library, re-test: most of those blockers are
  gone.
