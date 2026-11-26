# Common crash patterns and fixes

## Android (Kotlin/Java)

| Signature | Usual cause | Fix |
| --- | --- | --- |
| `NullPointerException` / `NullPointerException: Parameter specified as non-null is null` | Java/platform API returned null into Kotlin non-null type; lateinit not initialised; view accessed after `onDestroyView` | Nullable types at the boundary, `viewLifecycleOwner` scopes, `isInitialized` checks |
| `IllegalStateException: Fragment not attached` / `Can not perform this action after onSaveInstanceState` | Async callback after the UI is gone | Collect flows with `repeatOnLifecycle`, cancel jobs in `onDestroyView`, `commitAllowingStateLoss` only for non-critical UI |
| `IllegalArgumentException` in your code | Validation with `require(...)` hit by real data | Validate at input; handle the invalid case in UI |
| `OutOfMemoryError` with `Bitmap` frames | Full-size images decoded | Downsample (Coil/Glide sizing), `inSampleSize`, recycle caches |
| `ForegroundServiceStartNotAllowedException`, `MissingForegroundServiceTypeException` | Android 12/14 restrictions | Start from a visible activity, declare the service type and permission |
| `SecurityException: Permission Denial` | Permission revoked or never granted | Check before use, handle denial |
| `RemoteServiceException: Bad notification` / `Context.startForegroundService() did not then call Service.startForeground()` | Notification channel missing, startForeground too late | Create the channel at startup, call `startForeground` within seconds |
| `android.view.WindowManager$BadTokenException` | Dialog shown from a finished activity | Check `isFinishing`/lifecycle state |
| `SQLiteException`, Room migration errors | Missing migration after a schema change | Add `Migration`, test upgrade from the previous store build |

ANRs ("Input dispatching timed out") have the main thread stack in the ANR trace: look
for disk/network I/O, locks or heavy JSON parsing on the main thread.

## Flutter / Dart

| Signature | Usual cause | Fix |
| --- | --- | --- |
| `Bad state: No element` | `.first`, `.single`, `firstWhere` on an empty list | `firstOrNull` / `firstWhereOrNull` (package:collection) and an empty state |
| `TypeError: type 'Null' is not a subtype of type 'String'` | JSON field missing or null | Nullable model fields, defaults, `json_serializable` with `checked: true`, validate API responses |
| `Null check operator used on a null value` | `!` on a value that can be null | Handle null; never `!` on data from I/O |
| `setState() called after dispose()` | Async work finishing after the widget left | `if (!mounted) return;` before `setState`; cancel subscriptions in `dispose` |
| `Looking up a deactivated widget's ancestor is unsafe` / context after `await` | `BuildContext` used after an async gap | `if (!context.mounted) return;` (lint: `use_build_context_synchronously`) |
| `RangeError (index)` | Index from stale list length | Use builder `itemCount`, guard indexes |
| `PlatformException(...)` | Plugin native side error (permission, missing config) | Catch around plugin calls, check plugin setup per platform |
| `RenderFlex overflowed` (debug) | Layout, not a crash in release | `Expanded`, `Flexible`, scrolling, text overflow |

Register `FlutterError.onError` and `PlatformDispatcher.instance.onError` to send both
framework and async errors to the crash reporter.

## React Native

| Signature | Usual cause | Fix |
| --- | --- | --- |
| `TypeError: undefined is not an object (evaluating 'x.y')` / `Cannot read property 'y' of undefined` | Data not loaded yet, API shape changed | Optional chaining with loading state, runtime validation (zod) at API boundary |
| `Invariant Violation: requireNativeComponent: "X" was not found in the UIManager` | Native module not linked, pods not installed, New Architecture incompatibility | `pod install`, rebuild, check the library's New Architecture support |
| `TurboModuleRegistry.getEnforcing(...): 'X' could not be found` | Native module missing in the build | Rebuild native app (not just Metro), check autolinking |
| `Maximum update depth exceeded` | setState in render / effect without dependencies | Fix effect dependencies, memoize |
| `SIGABRT` / `EXC_BAD_ACCESS` in `hermes` or `React` frames | Native crash in a library or JSI misuse | Symbolicate, upgrade the library, report upstream with the trace |

## iOS (native frames)

| Signature | Usual cause | Fix |
| --- | --- | --- |
| `EXC_BREAKPOINT (SIGTRAP)` in Swift frames | Force unwrap of nil, array out of bounds, `fatalError`, failed `as!` | Safe unwrapping, bounds checks |
| `EXC_CRASH (SIGABRT)` with `NSInvalidArgumentException` / `NSInternalInconsistencyException` | ObjC exception: nil in collection, UI on background thread, table view inconsistency | Read Last Exception Backtrace and the reason |
| `EXC_BAD_ACCESS (SIGSEGV/SIGBUS)` | Use-after-free, threading, C/C++ memory bugs | Address Sanitizer / Thread Sanitizer in debug builds |
| `0x8badf00d` termination | Watchdog: main thread blocked at launch or resume | Move work off the main thread, shorten launch |
| `Jetsam` / memory limit | Too much memory (images, caches) | Downsample images, cap caches |
| Crash on permission prompt (`TCC`) | Missing purpose string | `ios-plist-audit` |
