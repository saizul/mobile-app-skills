# Signing

## Android

- Use **Play App Signing**: Google holds the app signing key; you sign uploads with an
  **upload key**. A lost or leaked upload key can be reset through Play Console; a lost
  app signing key without Play App Signing cannot.
- Create the upload key (the user runs this and chooses the passwords):
  ```bash
  keytool -genkeypair -v -keystore ~/keys/upload-keystore.jks -keyalg RSA -keysize 2048 \
    -validity 10000 -alias upload
  ```
- Keep the keystore **outside the repository** (password manager, CI secret as base64).
- Flutter (`android/key.properties`, git-ignored):
  ```properties
  storePassword=...
  keyPassword=...
  keyAlias=upload
  storeFile=/path/outside/repo/upload-keystore.jks
  ```
  and in `android/app/build.gradle.kts`:
  ```kotlin
  val keystoreProperties = java.util.Properties().apply {
      val f = rootProject.file("key.properties")
      if (f.exists()) load(java.io.FileInputStream(f))
  }
  android {
      signingConfigs {
          create("release") {
              keyAlias = keystoreProperties["keyAlias"] as String?
              keyPassword = keystoreProperties["keyPassword"] as String?
              storeFile = (keystoreProperties["storeFile"] as String?)?.let { file(it) }
              storePassword = keystoreProperties["storePassword"] as String?
          }
      }
      buildTypes {
          release { signingConfig = signingConfigs.getByName("release") }
      }
  }
  ```
  The Flutter template ships `signingConfig = signingConfigs.getByName("debug")` in
  `release` with a TODO; Play rejects bundles signed that way.
- React Native: `MYAPP_UPLOAD_*` variables in `~/.gradle/gradle.properties` (not the
  project's) and a `signingConfigs.release` block; the template's release build type
  uses the debug config until you change it.
- CI: decode the keystore from a secret into a temp file, pass passwords as environment
  variables, delete the file after the build.

## iOS

- Prefer **automatic signing** with an Apple Distribution certificate managed by Xcode or
  App Store Connect API keys in CI (`xcodebuild -allowProvisioningUpdates` with
  `-authenticationKeyPath`), or fastlane `match` for teams.
- Never commit `.p12`, `.p8` or `.mobileprovision` files; the preflight flags them.
- Flutter: `flutter build ipa --export-options-plist=ios/ExportOptions.plist`.
- React Native: archive the `.xcworkspace` scheme in Release, or `xcodebuild archive`.

## If a key or password was committed

1. Treat it as leaked even if the commit was reverted (clones and forks keep it).
2. Android upload key: request an upload key reset in Play Console, generate a new key.
3. iOS: revoke the certificate / API key in the Apple Developer portal and create new ones.
4. Remove the files from history only after rotating (history rewrites do not un-leak).
