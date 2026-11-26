# Usage description keys

| Capability | Key(s) | Typical Flutter / RN packages |
| --- | --- | --- |
| Camera | NSCameraUsageDescription | image_picker, camera, mobile_scanner, react-native-vision-camera, expo-camera |
| Microphone | NSMicrophoneUsageDescription | camera (video), record, speech_to_text, expo-av, @react-native-voice/voice |
| Photo library (read) | NSPhotoLibraryUsageDescription | image_picker, photo_manager, react-native-image-picker, expo-media-library |
| Photo library (add only) | NSPhotoLibraryAddUsageDescription | gal, image_gallery_saver, @react-native-camera-roll/camera-roll |
| Location while in use | NSLocationWhenInUseUsageDescription | geolocator, location, expo-location |
| Location always | NSLocationAlwaysAndWhenInUseUsageDescription **and** NSLocationWhenInUseUsageDescription | flutter_background_geolocation, react-native-background-geolocation |
| Contacts | NSContactsUsageDescription | flutter_contacts, react-native-contacts, expo-contacts |
| Calendars | NSCalendarsFullAccessUsageDescription (iOS 17+), NSCalendarsUsageDescription (earlier) | device_calendar, expo-calendar |
| Reminders | NSRemindersFullAccessUsageDescription (iOS 17+) | expo-calendar |
| Bluetooth | NSBluetoothAlwaysUsageDescription | flutter_blue_plus, react-native-ble-plx |
| Face ID | NSFaceIDUsageDescription | local_auth, react-native-biometrics, expo-local-authentication |
| Speech recognition | NSSpeechRecognitionUsageDescription | speech_to_text, @react-native-voice/voice |
| Motion & fitness | NSMotionUsageDescription | pedometer, expo-sensors (pedometer) |
| HealthKit | NSHealthShareUsageDescription, NSHealthUpdateUsageDescription | health, react-native-health |
| Tracking (ATT) | NSUserTrackingUsageDescription | app_tracking_transparency, expo-tracking-transparency |
| Local network | NSLocalNetworkUsageDescription (+ NSBonjourServices) | LAN discovery, Flutter debug builds on device |
| NFC | NFCReaderUsageDescription (+ entitlement) | nfc_manager, react-native-nfc-manager |

Flutter debug builds on physical devices use the local network for hot reload and the
debugger (`NSLocalNetworkUsageDescription`, `NSBonjourServices`). Keep those entries in a
Debug-only plist so they do not ship in release builds unless the app really uses the LAN.

If the app supports iOS versions before 17, keep `NSCalendarsUsageDescription` next to
the new full-access key.

## Writing purpose strings

Formula: **what** + **why** + **user benefit**, specific to this app.

| Weak (rejected) | Good |
| --- | --- |
| "This app needs access to your camera." | "Scan paper receipts so Pocket Budget can fill in the amount and shop for you." |
| "Location is required." | "Tag each expense with the shop where you paid, so you can see spending by place." |
| "We use contacts." | "Pick a friend from your contacts to split a bill with. Contacts are not uploaded." |
| "Allow tracking." | "Allow tracking to see offers from partners that match your interests. You can change this in Settings." |
| "$(PRODUCT_NAME) needs Face ID" | "Unlock your budgets with Face ID instead of typing your passcode." |

Rules:

- Do not pressure ("You must allow...") or mislead about why the data is needed.
- Mention whether data leaves the device when it matters to users.
- Localize in `<lang>.lproj/InfoPlist.strings` with the same keys.
- Show your own pre-permission screen before the system prompt for important permissions,
  and handle denial gracefully (link to Settings).

## Privacy manifest

Since 2024 Apple requires a `PrivacyInfo.xcprivacy` in apps and listed third-party SDKs
that use "required reason" APIs (UserDefaults, file timestamps, system boot time, disk
space, active keyboards). Add one to the app target (Xcode: File > New > File > App
Privacy) declaring `NSPrivacyAccessedAPITypes` with reasons, collected data types and
tracking domains. Flutter plugins and React Native libraries ship their own manifests;
update old versions that do not.
