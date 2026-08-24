# First-Party Animus Fire TV Helper (`com.animus.firetv.helper`)
## Architecture & Specification Document

---

## 1. Overview & Purpose

The **Animus Fire TV Helper** is a lightweight, headless Android service companion designed specifically for Amazon Fire TV devices (Fire OS 7 / Android 9+). 

Its sole responsibility is providing low-latency, deterministic ADB broadcast endpoints for Bluetooth profile manipulation (`BluetoothA2dp` and `BluetoothHeadset`), avoiding the overhead, visual disruption, and unreliability of remote-keystroke UI automation.

---

## 2. Package & Component Definition

- **Application ID**: `com.animus.firetv.helper`
- **Version Name**: `1.0.0`
- **Target SDK**: `28` (Android 9 / Fire OS 7)
- **Minimum SDK**: `26` (Android 8.0)
- **Primary Component**: `com.animus.firetv.helper.BluetoothControlReceiver` (BroadcastReceiver)
- **Foreground Activities**: None (100% headless background component)

---

## 3. Required Android Permissions

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.animus.firetv.helper">

    <!-- Bluetooth Administration -->
    <uses-permission android:name="android.permission.BLUETOOTH" />
    <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

    <!-- Boot Completion to initialize listener immediately -->
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />

    <application
        android:label="AnimusFireTVHelper"
        android:allowBackup="false"
        android:directBootAware="true">

        <receiver
            android:name=".BluetoothControlReceiver"
            android:permission="android.permission.DUMP"
            android:exported="true">
            <intent-filter>
                <action android:name="com.animus.firetv.ACTION_CONNECT" />
                <action android:name="com.animus.firetv.ACTION_DISCONNECT" />
                <action android:name="com.animus.firetv.ACTION_STATUS" />
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>

    </application>
</manifest>
```

> **Security Note**: Protecting the receiver with `android.permission.DUMP` ensures that only `shell` (UID 2000 over ADB) and system-privileged processes can invoke it, preventing unauthorized local third-party apps from intercepting or triggering Bluetooth commands.

---

## 4. Broadcast Protocol & Actions

### A. Connect Action
- **Intent Action**: `com.animus.firetv.ACTION_CONNECT` (or fallback `com.saihgupr.btcontrol.ACTION_CONNECT`)
- **Component**: `com.animus.firetv.helper/.BluetoothControlReceiver`
- **Intent Extras**:
  - `-e address "<MAC_ADDRESS>"`: Mandatory 17-character hardware MAC address (e.g., `54:15:89:DC:A5:79`).
- **CLI Example**:
  ```bash
  adb shell am broadcast \
    -a com.animus.firetv.ACTION_CONNECT \
    -n com.animus.firetv.helper/.BluetoothControlReceiver \
    -e address "54:15:89:DC:A5:79"
  ```

### B. Disconnect Action
- **Intent Action**: `com.animus.firetv.ACTION_DISCONNECT`
- **Component**: `com.animus.firetv.helper/.BluetoothControlReceiver`
- **Intent Extras**:
  - `-e address "<MAC_ADDRESS>"`: Mandatory hardware MAC address.
- **CLI Example**:
  ```bash
  adb shell am broadcast \
    -a com.animus.firetv.ACTION_DISCONNECT \
    -n com.animus.firetv.helper/.BluetoothControlReceiver \
    -e address "54:15:89:DC:A5:79"
  ```

### C. Status Query Action
- **Intent Action**: `com.animus.firetv.ACTION_STATUS`
- **CLI Example**:
  ```bash
  adb shell am broadcast \
    -a com.animus.firetv.ACTION_STATUS \
    -n com.animus.firetv.helper/.BluetoothControlReceiver
  ```

---

## 5. Core Java Implementation Pattern

```java
package com.animus.firetv.helper;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothProfile;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import java.lang.reflect.Method;

public class BluetoothControlReceiver extends BroadcastReceiver {
    private static final String TAG = "AnimusBTReceiver";
    public static final String ACTION_CONNECT = "com.animus.firetv.ACTION_CONNECT";
    public static final String ACTION_DISCONNECT = "com.animus.firetv.ACTION_DISCONNECT";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        String address = intent.getStringExtra("address");

        if (address == null || address.isEmpty()) {
            Log.e(TAG, "No Bluetooth address provided.");
            return;
        }

        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null || !adapter.isEnabled()) {
            Log.e(TAG, "BluetoothAdapter is null or disabled.");
            return;
        }

        BluetoothDevice device = adapter.getRemoteDevice(address);
        if (device == null) {
            Log.e(TAG, "Device not found for MAC: " + address);
            return;
        }

        adapter.getProfileProxy(context, new BluetoothProfile.ServiceListener() {
            @Override
            public void onServiceConnected(int profile, BluetoothProfile proxy) {
                if (profile == BluetoothProfile.A2DP) {
                    try {
                        String methodName = ACTION_CONNECT.equals(action) ? "connect" : "disconnect";
                        Method method = proxy.getClass().getMethod(methodName, BluetoothDevice.class);
                        method.setAccessible(true);
                        boolean ok = (Boolean) method.invoke(proxy, device);
                        Log.i(TAG, "Method " + methodName + " invoked on A2DP proxy: " + ok);
                    } catch (Exception e) {
                        Log.e(TAG, "Reflection exception on A2DP proxy: " + e.getMessage(), e);
                    } finally {
                        adapter.closeProfileProxy(profile, proxy);
                    }
                }
            }

            @Override
            public void onServiceDisconnected(int profile) {}
        }, BluetoothProfile.A2DP);
    }
}
```
