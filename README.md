# Animus Smart Room 🏠✨

An Android smart-room controller application built with **Kotlin** and **Jetpack Compose**. **Animus Smart Room** acts as a personalized command center for your smart room environment, media, and connected devices.

---

## 📱 Features

### Current (v1.0 Foundation)
- **Modern Dark UI**: Designed specifically for high-contrast ambient room control.
- **LG SNC4R Device Card**: Dedicated Bluetooth device connection interface with real-time status and toggle controls.
- **Media Control Section**: Quick playback controls (e.g. "Play Zara Zara" preset).
- **Modular Architecture**: Built with scalable Compose theming and clean separation of UI components.

### 🗺️ Roadmap & Upcoming Features
- [ ] **Bluetooth Control**: Real BLE / classic Bluetooth pairing and automated connection to soundbars and smart peripherals.
- [ ] **YouTube Music Integration**: In-app background music queue and playback control via YouTube Music APIs/Intents.
- [ ] **Voice Command Interface**: Hands-free room and media commands.
- [ ] **Scene Modes**:
  - 🎬 **Movie Mode**: Dynamic lighting & audio profile for movies.
  - 🎮 **Game Mode**: Low-latency audio routing and gaming ambiance.
- [ ] **Smart Room Automations**: Scheduled routines and sensor-triggered actions.

---

## 🛠️ Tech Stack

- **Language**: [Kotlin](https://kotlinlang.org/) (1.9.22)
- **UI Framework**: [Jetpack Compose](https://developer.android.com/jetpack/compose) with Material 3
- **Build System**: Gradle 8.6 with Kotlin DSL (`.gradle.kts`)
- **Min SDK**: API 26 (Android 8.0 Oreo)
- **Target SDK**: API 34 (Android 14)

---

## 🚀 Getting Started

### Prerequisites
- **Android Studio** (Hedgehog | 2023.1.1 or newer recommended)
- **JDK 17**
- Android SDK with API 34 platform installed

### Setup & Build
1. **Clone the repository**:
   ```bash
   git clone https://github.com/Animus004/Animus_smart_home.git
   cd Animus_smart_home
   ```

2. **Build the Debug APK**:
   ```bash
   ./gradlew assembleDebug
   ```

3. **Locate the APK**:
   The output APK will be generated at:
   ```
   app/build/outputs/apk/debug/app-debug.apk
   ```

---

## 📂 Project Structure

```
AnimusSmartRoom/
├── app/
│   ├── src/main/
│   │   ├── java/com/animus/smartroom/
│   │   │   ├── MainActivity.kt        # Main Entrypoint & Home Screen UI
│   │   │   └── ui/theme/             # Theme, Color palettes & Typography
│   │   ├── res/                      # Strings, Drawables & App themes
│   │   └── AndroidManifest.xml       # App Manifest
│   └── build.gradle.kts              # App module dependencies & config
├── gradle/wrapper/                   # Gradle wrapper binaries & properties
├── build.gradle.kts                  # Root project build configuration
├── settings.gradle.kts               # Gradle settings & module definitions
└── README.md                         # Project documentation
```

---

## 📄 License
This project is proprietary for personal smart-room automation.
