package com.animus.smartroom.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.lang.reflect.Method

class BluetoothAudioDeviceManager(
    private val context: Context
) {
    companion object {
        private const val TAG = "BluetoothAudioMgr"
        const val LG_SNC4R_NAME_DEFAULT = "LG SNC4R(79)"
        const val LG_SNC4R_NAME_FALLBACK = "LG SNC4R"
        const val LG_SNC4R_MAC_DEFAULT = "54:15:89:DC:A5:79"
        private const val CONNECT_TIMEOUT_MS = 12000L
    }

    private val bluetoothManager: BluetoothManager? =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter

    private val _uiState = MutableStateFlow(BluetoothUiState())
    val uiState: StateFlow<BluetoothUiState> = _uiState.asStateFlow()

    private var selectedDeviceMac: String? = null
    private var a2dpProfile: BluetoothProfile? = null
    private var isReceiverRegistered = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null

    private val profileListener = object : BluetoothProfile.ServiceListener {
        override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "A2DP Profile Proxy connected")
                a2dpProfile = proxy
                refreshState()
            }
        }

        override fun onServiceDisconnected(profile: Int) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "A2DP Profile Proxy disconnected")
                a2dpProfile = null
                _uiState.update {
                    it.copy(connectionState = BluetoothDeviceState.Disconnected)
                }
            }
        }
    }

    private val bluetoothReceiver = object : BroadcastReceiver() {
        @SuppressLint("MissingPermission")
        override fun onReceive(ctx: Context?, intent: Intent?) {
            val action = intent?.action ?: return
            Log.d(TAG, "Received broadcast: $action")

            when (action) {
                BluetoothAdapter.ACTION_STATE_CHANGED -> {
                    val state = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR)
                    val isEnabled = state == BluetoothAdapter.STATE_ON
                    _uiState.update {
                        it.copy(
                            isBluetoothEnabled = isEnabled,
                            connectionState = if (!isEnabled) BluetoothDeviceState.Disconnected else it.connectionState
                        )
                    }
                    refreshState()
                }

                BluetoothDevice.ACTION_ACL_CONNECTED,
                BluetoothDevice.ACTION_ACL_DISCONNECTED,
                "android.bluetooth.a2dp.profile.action.CONNECTION_STATE_CHANGED",
                BluetoothDevice.ACTION_BOND_STATE_CHANGED -> {
                    cancelTimeout()
                    refreshState()
                }
            }
        }
    }

    fun startListening() {
        if (!isReceiverRegistered) {
            val filter = IntentFilter().apply {
                addAction(BluetoothAdapter.ACTION_STATE_CHANGED)
                addAction(BluetoothDevice.ACTION_ACL_CONNECTED)
                addAction(BluetoothDevice.ACTION_ACL_DISCONNECTED)
                addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
                addAction("android.bluetooth.a2dp.profile.action.CONNECTION_STATE_CHANGED")
            }
            context.registerReceiver(bluetoothReceiver, filter)
            isReceiverRegistered = true
        }

        bluetoothAdapter?.getProfileProxy(
            context,
            profileListener,
            BluetoothProfile.A2DP
        )

        refreshState()
    }

    fun stopListening() {
        cancelTimeout()
        if (isReceiverRegistered) {
            try {
                context.unregisterReceiver(bluetoothReceiver)
            } catch (e: Exception) {
                Log.w(TAG, "Failed to unregister receiver", e)
            }
            isReceiverRegistered = false
        }
        if (a2dpProfile != null && bluetoothAdapter != null) {
            bluetoothAdapter.closeProfileProxy(BluetoothProfile.A2DP, a2dpProfile)
            a2dpProfile = null
        }
    }

    fun selectDevice(macAddress: String) {
        selectedDeviceMac = macAddress
        refreshState()
    }

    @SuppressLint("MissingPermission")
    fun refreshState() {
        val hasPerms = hasRequiredPermissions()
        val isEnabled = bluetoothAdapter?.isEnabled == true

        if (!hasPerms || !isEnabled || bluetoothAdapter == null) {
            _uiState.update {
                it.copy(
                    hasRequiredPermissions = hasPerms,
                    isBluetoothEnabled = isEnabled,
                    pairedDevices = emptyList(),
                    selectedDevice = null,
                    connectionState = BluetoothDeviceState.Disconnected
                )
            }
            return
        }

        val bondedDevices = try {
            bluetoothAdapter.bondedDevices
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException reading bonded devices", e)
            emptySet()
        } ?: emptySet()

        val a2dp = a2dpProfile
        val deviceList = bondedDevices.map { device ->
            val name = try { device.name ?: "Unknown Device" } catch (e: SecurityException) { "Unknown Device" }
            val mac = device.address
            val isConnected = if (a2dp != null) {
                a2dp.getConnectionState(device) == BluetoothProfile.STATE_CONNECTED
            } else false

            val majorClass = try {
                device.bluetoothClass?.majorDeviceClass
            } catch (e: SecurityException) {
                null
            }
            val isAudio = majorClass == BluetoothClass.Device.Major.AUDIO_VIDEO ||
                    name.contains("sound", ignoreCase = true) ||
                    name.contains("snc", ignoreCase = true) ||
                    name.contains("lg", ignoreCase = true) ||
                    name.contains("speaker", ignoreCase = true) ||
                    name.contains("headset", ignoreCase = true) ||
                    name.contains("ear", ignoreCase = true) ||
                    name.contains("buds", ignoreCase = true)

            BluetoothAudioDevice(
                name = name,
                macAddress = mac,
                isBonded = true,
                isConnected = isConnected,
                isAudioDevice = isAudio
            )
        }.sortedWith(
            compareByDescending<BluetoothAudioDevice> { it.isConnected }
                .thenByDescending { isLgSoundbar(it.name, it.macAddress) }
                .thenByDescending { it.isAudioDevice }
                .thenBy { it.name }
        )

        // Resolve selected device
        val resolvedSelectedDevice: BluetoothAudioDevice? = when {
            // 1. Explicitly selected device if present
            selectedDeviceMac != null -> deviceList.find { it.macAddress.equals(selectedDeviceMac, ignoreCase = true) }
            // 2. Currently connected device
            deviceList.any { it.isConnected } -> deviceList.first { it.isConnected }
            // 3. LG SNC4R preferred default
            deviceList.any { isLgSoundbar(it.name, it.macAddress) } -> deviceList.first { isLgSoundbar(it.name, it.macAddress) }
            // 4. First paired device or null
            else -> deviceList.firstOrNull()
        }

        if (resolvedSelectedDevice != null) {
            selectedDeviceMac = resolvedSelectedDevice.macAddress
        }

        // Determine active connection state for the selected device
        val activeConnState: BluetoothDeviceState = when {
            resolvedSelectedDevice == null -> BluetoothDeviceState.Disconnected
            resolvedSelectedDevice.isConnected -> BluetoothDeviceState.Connected(
                deviceName = resolvedSelectedDevice.name,
                macAddress = resolvedSelectedDevice.macAddress
            )
            _uiState.value.connectionState is BluetoothDeviceState.Connecting -> BluetoothDeviceState.Connecting
            _uiState.value.connectionState is BluetoothDeviceState.Error -> _uiState.value.connectionState
            else -> BluetoothDeviceState.Disconnected
        }

        _uiState.update {
            it.copy(
                hasRequiredPermissions = hasPerms,
                isBluetoothEnabled = isEnabled,
                pairedDevices = deviceList,
                selectedDevice = resolvedSelectedDevice,
                connectionState = activeConnState,
                userNotice = if (deviceList.isEmpty()) "No paired Bluetooth devices found. Please pair in Settings." else null
            )
        }
    }

    private fun isLgSoundbar(name: String, mac: String): Boolean {
        return mac.equals(LG_SNC4R_MAC_DEFAULT, ignoreCase = true) ||
                name.contains(LG_SNC4R_NAME_FALLBACK, ignoreCase = true) ||
                name.equals(LG_SNC4R_NAME_DEFAULT, ignoreCase = true)
    }

    @SuppressLint("MissingPermission")
    fun connect() {
        if (!hasRequiredPermissions()) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Bluetooth permissions not granted"),
                    userNotice = "Please grant Bluetooth permissions to connect."
                )
            }
            return
        }

        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Bluetooth is turned off"),
                    userNotice = "Please turn on Bluetooth in device settings."
                )
            }
            return
        }

        val selected = _uiState.value.selectedDevice
        if (selected == null) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("No device selected"),
                    userNotice = "Please select or pair a Bluetooth audio device first."
                )
            }
            return
        }

        val bluetoothDevice = try {
            bluetoothAdapter.getRemoteDevice(selected.macAddress)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get remote device for ${selected.macAddress}", e)
            null
        }

        if (bluetoothDevice == null) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Invalid device"),
                    userNotice = "Could not find device ${selected.name} (${selected.macAddress})."
                )
            }
            return
        }

        _uiState.update {
            it.copy(
                connectionState = BluetoothDeviceState.Connecting,
                userNotice = null
            )
        }

        val a2dp = a2dpProfile
        if (a2dp == null) {
            Log.w(TAG, "A2DP profile proxy is not ready yet; requesting proxy...")
            bluetoothAdapter.getProfileProxy(
                context,
                profileListener,
                BluetoothProfile.A2DP
            )
            startTimeoutTimer("Connection timed out waiting for audio service.")
            return
        }

        if (a2dp.getConnectionState(bluetoothDevice) == BluetoothProfile.STATE_CONNECTED) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Connected(selected.name, selected.macAddress)
                )
            }
            return
        }

        val success = invokeProfileConnect(a2dp, bluetoothDevice)
        if (success) {
            startTimeoutTimer("Connection attempt timed out. Ensure ${selected.name} is powered on and in range.")
        } else {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Could not initiate audio connection"),
                    userNotice = "Unable to connect automatically. Please connect from system Bluetooth settings."
                )
            }
        }
    }

    @SuppressLint("MissingPermission")
    fun disconnect() {
        if (!hasRequiredPermissions()) return
        val selected = _uiState.value.selectedDevice ?: return
        val a2dp = a2dpProfile ?: return
        val bluetoothDevice = try {
            bluetoothAdapter?.getRemoteDevice(selected.macAddress)
        } catch (e: Exception) {
            null
        } ?: return

        _uiState.update {
            it.copy(connectionState = BluetoothDeviceState.Connecting)
        }

        val success = invokeProfileDisconnect(a2dp, bluetoothDevice)
        if (!success) {
            _uiState.update {
                it.copy(connectionState = BluetoothDeviceState.Disconnected)
            }
        }
    }

    private fun invokeProfileConnect(profile: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val connectMethod: Method = profile.javaClass.getMethod("connect", BluetoothDevice::class.java)
            connectMethod.isAccessible = true
            val result = connectMethod.invoke(profile, device) as? Boolean ?: false
            Log.d(TAG, "BluetoothA2dp.connect invocation result: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to invoke BluetoothA2dp connect reflection", e)
            false
        }
    }

    private fun invokeProfileDisconnect(profile: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val disconnectMethod: Method = profile.javaClass.getMethod("disconnect", BluetoothDevice::class.java)
            disconnectMethod.isAccessible = true
            val result = disconnectMethod.invoke(profile, device) as? Boolean ?: false
            Log.d(TAG, "BluetoothA2dp.disconnect invocation result: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to invoke BluetoothA2dp disconnect reflection", e)
            false
        }
    }

    private fun startTimeoutTimer(timeoutMessage: String) {
        cancelTimeout()
        val runnable = Runnable {
            if (_uiState.value.connectionState is BluetoothDeviceState.Connecting) {
                _uiState.update {
                    it.copy(
                        connectionState = BluetoothDeviceState.Error(timeoutMessage),
                        userNotice = timeoutMessage
                    )
                }
            }
        }
        timeoutRunnable = runnable
        mainHandler.postDelayed(runnable, CONNECT_TIMEOUT_MS)
    }

    private fun cancelTimeout() {
        timeoutRunnable?.let { mainHandler.removeCallbacks(it) }
        timeoutRunnable = null
    }

    fun hasRequiredPermissions(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.BLUETOOTH_CONNECT
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.BLUETOOTH
            ) == PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.BLUETOOTH_ADMIN
            ) == PackageManager.PERMISSION_GRANTED
        }
    }

    fun getRequiredPermissions(): Array<String> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN
            )
        } else {
            arrayOf(
                Manifest.permission.BLUETOOTH,
                Manifest.permission.BLUETOOTH_ADMIN,
                Manifest.permission.ACCESS_FINE_LOCATION
            )
        }
    }
}
