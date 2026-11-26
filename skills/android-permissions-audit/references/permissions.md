# Android permission and manifest checks

## Checks

| Check | Severity | Meaning | Fix |
| --- | --- | --- | --- |
| `permission.restricted` | high/medium | Google Play restricts it; needs a Permissions Declaration or is only allowed for certain app types | Remove, use an alternative below, or file the declaration |
| `permission.dangerous` | info | Runtime permission; shown to the user | Request in context, explain first, handle "deny" and "don't ask again" |
| `permission.legacy_storage` | medium/low | READ/WRITE_EXTERNAL_STORAGE without `maxSdkVersion` | `maxSdkVersion="32"` (READ) / `"28"` (WRITE); READ_MEDIA_* or photo picker |
| `permission.unused` | low | No usage hint in code or dependencies (heuristic) | Verify, then remove or `tools:node="remove"` |
| `permission.fgs_type` | medium | targetSdk 34+: foreground services need a type and a FOREGROUND_SERVICE_<TYPE> permission | Add `android:foregroundServiceType` and the permission |
| `permission.notifications` | low | Push service without POST_NOTIFICATIONS on Android 13+ | Declare and request it |
| `permission.custom_weak` | low | Custom permission with `normal`/`dangerous` protection | `protectionLevel="signature"` |
| `component.exported_missing` | high | intent-filter without `android:exported` (targetSdk 31+ build error) | Set it explicitly |
| `component.exported` | high (provider) / medium | Other apps can start or query it | `exported="false"` or a signature permission |
| `app.debuggable` | high | `android:debuggable="true"` hard-coded | Remove; Gradle sets it per build type |
| `app.cleartext` | medium | Plain HTTP allowed for all hosts | HTTPS; debug-only exceptions |
| `app.backup` | low | Auto Backup without rules copies tokens and databases | `dataExtractionRules` (Android 12+) and `fullBackupContent` excluding secrets |
| `nsc.cleartext` | high/medium/info | Network security config permits cleartext (info for emulator/localhost only) | Restrict to `<debug-overrides>` or specific dev hosts |
| `nsc.user_ca` | medium | Trusts user-installed CAs in release | Move to `<debug-overrides>` |

## Restricted permissions and alternatives

| Permission | Policy | Alternative |
| --- | --- | --- |
| READ_SMS, RECEIVE_SMS, SEND_SMS | SMS and Call Log: default handler or approved exception only | SMS Retriever API / SMS User Consent API for OTP; `Intent.ACTION_SENDTO` to compose |
| READ_CALL_LOG, WRITE_CALL_LOG, PROCESS_OUTGOING_CALLS | SMS and Call Log | CallScreeningService / default dialer role |
| ACCESS_BACKGROUND_LOCATION | Declaration + video + prominent in-app disclosure | Foreground-only location, geofencing via foreground service with `location` type |
| MANAGE_EXTERNAL_STORAGE | All files access: file managers, backup, antivirus | Storage Access Framework, MediaStore |
| QUERY_ALL_PACKAGES | Package visibility: core use only | `<queries>` with specific packages or intents |
| REQUEST_INSTALL_PACKAGES | Only apps whose core feature installs packages | Open the Play listing instead |
| READ_MEDIA_IMAGES, READ_MEDIA_VIDEO | Photo and Video Permissions: only for core, repeated broad access | Android photo picker (`PickVisualMedia`; Flutter `image_picker` uses it on Android 13+) |
| USE_EXACT_ALARM | Alarm clocks and calendars only | SCHEDULE_EXACT_ALARM (user grant) or WorkManager / inexact alarms |
| USE_FULL_SCREEN_INTENT | Calling and alarm apps on Android 14+ | Heads-up notification |
| SYSTEM_ALERT_WINDOW | User grant in settings | Bubbles, notifications, picture-in-picture |
| BIND_ACCESSIBILITY_SERVICE | Accessibility API policy | Only for accessibility tools; needs disclosure |
| FOREGROUND_SERVICE_SPECIAL_USE | Justification in Play Console | A specific service type |

Policies change; confirm the current wording in the Play Console Policy Center before
telling the user an exception is or is not allowed.

## Where permissions come from in Flutter / React Native

- Flutter plugins ship their own manifests (`image_picker`, `geolocator`,
  `permission_handler` adds nothing by itself; you declare what you use).
- React Native libraries do the same; Expo config plugins add permissions from `app.json`
  (`android.permissions`, `android.blockedPermissions` to strip).
- The merged manifest and `manifest-merger-release-report.txt` show the origin of each line.

## Exported components: decision guide

- Launcher activity: must be exported; fine.
- Deep link / App Link activity: exported; validate every URI parameter and never trust
  extras for authorization.
- Share targets (`ACTION_SEND`): exported; treat incoming data as untrusted.
- Internal services, receivers, providers: `exported="false"`.
- App-to-app APIs between your own apps: a custom permission with
  `protectionLevel="signature"`.
- `FileProvider`: always `exported="false"` with `grantUriPermissions="true"`.
