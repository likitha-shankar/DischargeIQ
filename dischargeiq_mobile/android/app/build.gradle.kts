import java.util.Properties
import java.io.FileInputStream

// Release signing material, deliberately outside the repository: the keystore
// lives in ~/.dischargeiq/ and key.properties carries its passwords, both
// gitignored. When the file is absent - a fresh clone, CI, another machine -
// the release build falls back to debug signing so it still builds, and
// _isReleaseSigned below makes that visible rather than silent.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKey = keystorePropertiesFile.exists()
if (hasReleaseKey) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.dischargeiq_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // flutter_local_notifications (medication reminders + garden nudge)
        // uses java.time on API < 26; desugaring backports it.
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // Matches the iOS bundle id chosen for TestFlight (Sprint 2, Task 2.4).
        // namespace stays com.example.dischargeiq_mobile - it is the code
        // package, changing it would break MainActivity's package path.
        applicationId = "com.likithashankar.dischargeiq"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // A real upload key when one is configured (task 1.10). This
            // matters beyond correctness: Android refuses to upgrade an
            // installed app with a differently-signed build, so a tester
            // holding a debug-signed APK would have to UNINSTALL to take a
            // properly signed one - and an uninstall deletes their saved
            // documents. Ship the real key before testers install, not after.
            signingConfig = if (hasReleaseKey) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
            // ML Kit script-pack suppressions - see proguard-rules.pro.
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
