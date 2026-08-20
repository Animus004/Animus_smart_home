package com.animus.smartroom.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothA2dp
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
        private const val CONNECT_TIMEOUT_MS = 10000L
        private const val DISCONNECT_TIMEOUT_MS = 5000L
    }

    private val bluetoothManager: BluetoothManager? =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter

    private val _uiState = MutableStateFlow(BluetoothUiState())
    val uiState: StateFlow<BluetoothUiState> = _uiState.asStateFlow()

    private var selectedDeviceMac: String? = null
    private var pendingConnectMac: String? = null
    private var a2dpProfile: BluetoothProfile? = null
    private var isReceiverRegistered = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null

    private val profileListener = object : BluetoothProfile.ServiceListener {
        override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "[proxy] A2DP Profile Proxy acquired successfully: $proxy")
                a2dpProfile = proxy

                val pendingMac = pendingConnectMac
                if (pendingMac != null) {
                    pendingConnectMac = null
                    Log.d(TAG, "[proxy] Executing deferred connection to: $pendingMac")
                    connectInternal(pendingMac)
                } else {
                    refreshState()
                }
            }
        }

        override fun onServiceDisconnected(profile: Int) {
            if (profile == BluetoothProfile.A2DP) {
                Log.w(TAG, "[proxy] A2DP Profile Proxy disconnected by system")
                a2dpProfile = null
                cancelTimeout()
                _uiState.update {
                    it.copy(
                        connectionState = if (it.connectionState is BluetoothDeviceState.Connecting) {
                            BluetoothDeviceState.Disconnected
                        } else {
                            it.connectionState
                        }
                    )
                }
                refreshState()
            }
        }
    }

    private val bluetoothReceiver = object : BroadcastReceiver() {
        @SuppressLint("MissingPermission")
        override fun onReceive(ctx: Context?, intent: Intent?) {
            val action = intent?.action ?: return
            Log.d(TAG, "[broadcast] Received broadcast: $action")

            when (action) {
                BluetoothAdapter.ACTION_STATE_CHANGED -> {
                    val state = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR)
                    val isEnabled = state == BluetoothAdapter.STATE_ON
                    Log.d(TAG, "[broadcast] BluetoothAdapter state changed: $state (isEnabled=$isEnabled)")
                    if (!isEnabled) {
                        cancelTimeout()
                        closeA2dpProxy()
                        _uiState.update {
                            it.copy(
                                isBluetoothEnabled = false,
                                connectionState = BluetoothDeviceState.Disconnected,
                                userNotice = "Bluetooth is turned off"
                            )
                        }
                    } else {
                        _uiState.update { it.copy(isBluetoothEnabled = true, userNotice = null) }
                        requestA2dpProxy()
                        refreshState()
                    }
                }

                BluetoothA2dp.ACTION_CONNECTION_STATE_CHANGED -> {
                    val state = intent.getIntExtra(BluetoothProfile.EXTRA_STATE, BluetoothProfile.STATE_DISCONNECTED)
                    val prevState = intent.getIntExtra(BluetoothProfile.EXTRA_PREVIOUS_STATE, BluetoothProfile.STATE_DISCONNECTED)
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }

                    Log.d(TAG, "[broadcast] A2DP connection state for ${device?.address} (${device?.name}): state=$state, prevState=$prevState")

                    if (isTargetDevice(device)) {
                        when (state) {
                            BluetoothProfile.STATE_CONNECTED -> {
                                cancelTimeout()
                                val name = getDeviceDisplayName(device)
                                val mac = device?.address ?: (selectedDeviceMac ?: LG_SNC4R_MAC_DEFAULT)
                                Log.i(TAG, "[broadcast] A2DP Connected successfully to $name ($mac)")
                                _uiState.update {
                                    it.copy(
                                        connectionState = BluetoothDeviceState.Connected(name, mac),
                                        userNotice = null
                                    )
                                }
                            }

                            BluetoothProfile.STATE_CONNECTING -> {
                                Log.d(TAG, "[broadcast] A2DP Connecting to ${device?.address}")
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Connecting)
                                }
                            }

                            BluetoothProfile.STATE_DISCONNECTING -> {
                                Log.d(TAG, "[broadcast] A2DP Disconnecting from ${device?.address}")
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Connecting)
                                }
                            }

                            BluetoothProfile.STATE_DISCONNECTED -> {
                                cancelTimeout()
                                Log.d(TAG, "[broadcast] A2DP Disconnected from ${device?.address} (prevState was $prevState)")
                                val newState = if (prevState == BluetoothProfile.STATE_CONNECTING) {
                                    BluetoothDeviceState.Error("Connection attempt failed or was rejected by device.")
                                } else {
                                    BluetoothDeviceState.Disconnected
                                }
                                val userNotice = when (newState) {
                                    is BluetoothDeviceState.Error -> newState.message
                                    else -> null
                                }
                                _uiState.update {
                                    it.copy(
                                        connectionState = newState,
                                        userNotice = userNotice
                                    )
                                }
                            }
                        }
                    }
                    refreshState()
                }

                BluetoothDevice.ACTION_ACL_CONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    Log.d(TAG, "[broadcast] ACL Connected: ${device?.address}")
                    if (isTargetDevice(device)) {
                        refreshState()
                    }
                }

                BluetoothDevice.ACTION_ACL_DISCONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    Log.d(TAG, "[broadcast] ACL Disconnected: ${device?.address}")
                    if (isTargetDevice(device)) {
                        cancelTimeout()
                        _uiState.update {
                            it.copy(connectionState = BluetoothDeviceState.Disconnected)
                        }
                        refreshState()
                    }
                }

                BluetoothDevice.ACTION_BOND_STATE_CHANGED -> {
                    Log.d(TAG, "[broadcast] Bond state changed")
                    refreshState()
                }
            }
        }
    }

    fun startListening() {
        Log.d(TAG, "[lifecycle] startListening called")
        if (!isReceiverRegistered) {
            val filter = IntentFilter().apply {
                addAction(BluetoothAdapter.ACTION_STATE_CHANGED)
                addAction(BluetoothA2dp.ACTION_CONNECTION_STATE_CHANGED)
                addAction(BluetoothDevice.ACTION_ACL_CONNECTED)
                addAction(BluetoothDevice.ACTION_ACL_DISCONNECTED)
                addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
            }
            context.registerReceiver(bluetoothReceiver, filter)
            isReceiverRegistered = true
            Log.d(TAG, "[lifecycle] BroadcastReceiver registered")
        }

        requestA2dpProxy()
        refreshState()
    }

    fun stopListening() {
        Log.d(TAG, "[lifecycle] stopListening called")
        cancelTimeout()
        pendingConnectMac = null
        if (isReceiverRegistered) {
            try {
                context.unregisterReceiver(bluetoothReceiver)
                Log.d(TAG, "[lifecycle] BroadcastReceiver unregistered")
            } catch (e: Exception) {
                Log.w(TAG, "[lifecycle] Failed to unregister receiver", e)
            }
            isReceiverRegistered = false
        }
        closeA2dpProxy()
    }

    private fun requestA2dpProxy() {
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            Log.w(TAG, "[proxy] BluetoothAdapter is null or disabled; cannot request proxy")
            return
        }

        closeA2dpProxy()

        Log.d(TAG, "[proxy] Requesting A2DP profile proxy via getProfileProxy")
        val success = bluetoothAdapter.getProfileProxy(
            context,
            profileListener,
            BluetoothProfile.A2DP
        )
        Log.d(TAG, "[proxy] getProfileProxy invocation returned: $success")
    }

    private fun closeA2dpProxy() {
        if (a2dpProfile != null && bluetoothAdapter != null) {
            Log.d(TAG, "[proxy] Closing existing A2DP profile proxy ($a2dpProfile)")
            try {
                bluetoothAdapter.closeProfileProxy(BluetoothProfile.A2DP, a2dpProfile)
            } catch (e: Exception) {
                Log.w(TAG, "[proxy] Error while closing profile proxy", e)
            }
            a2dpProfile = null
        }
    }

    fun selectDevice(macAddress: String) {
        Log.d(TAG, "[device] Device selected by user: $macAddress")
        selectedDeviceMac = macAddress
        cancelTimeout()
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
            Log.e(TAG, "[state] SecurityException reading bonded devices", e)
            emptySet()
        } ?: emptySet()

        val a2dp = a2dpProfile
        val deviceList = bondedDevices.map { device ->
            val name = try { device.name ?: "Unknown Device" } catch (e: SecurityException) { "Unknown Device" }
            val mac = device.address
            val isConnected = if (a2dp != null) {
                try {
                    a2dp.getConnectionState(device) == BluetoothProfile.STATE_CONNECTED
                } catch (e: Exception) {
                    false
                }
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
            selectedDeviceMac != null -> deviceList.find { it.macAddress.equals(selectedDeviceMac, ignoreCase = true) }
            deviceList.any { it.isConnected } -> deviceList.first { it.isConnected }
            deviceList.any { isLgSoundbar(it.name, it.macAddress) } -> deviceList.first { isLgSoundbar(it.name, it.macAddress) }
            else -> deviceList.firstOrNull()
        }

        if (resolvedSelectedDevice != null) {
            selectedDeviceMac = resolvedSelectedDevice.macAddress
        }

        // Determine actual connection state for resolved selected device
        val isSelectedConnected = resolvedSelectedDevice != null && resolvedSelectedDevice.isConnected

        val currentConnState = _uiState.value.connectionState
        val resolvedConnState: BluetoothDeviceState = when {
            resolvedSelectedDevice == null -> BluetoothDeviceState.Disconnected
            isSelectedConnected -> BluetoothDeviceState.Connected(
                deviceName = resolvedSelectedDevice.name,
                macAddress = resolvedSelectedDevice.macAddress
            )
            currentConnState is BluetoothDeviceState.Connecting && timeoutRunnable != null -> {
                // Keep connecting only while active timeout timer is running
                BluetoothDeviceState.Connecting
            }
            currentConnState is BluetoothDeviceState.Error -> currentConnState
            else -> BluetoothDeviceState.Disconnected
        }

        Log.d(TAG, "[state] State refreshed: selected=${resolvedSelectedDevice?.name}, connected=$isSelectedConnected, connState=$resolvedConnState, pairedCount=${deviceList.size}")

        _uiState.update {
            it.copy(
                hasRequiredPermissions = hasPerms,
                isBluetoothEnabled = isEnabled,
                pairedDevices = deviceList,
                selectedDevice = resolvedSelectedDevice,
                connectionState = resolvedConnState,
                userNotice = if (deviceList.isEmpty()) "No paired Bluetooth devices found. Please pair in Settings." else it.userNotice
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
            Log.w(TAG, "[connect] Permission check failed")
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Bluetooth permissions not granted"),
                    userNotice = "Please grant Bluetooth permissions to connect."
                )
            }
            return
        }

        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            Log.w(TAG, "[connect] Bluetooth is turned off")
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
            Log.w(TAG, "[connect] No device selected")
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("No device selected"),
                    userNotice = "Please select or pair a Bluetooth audio device first."
                )
            }
            return
        }

        // Prevent duplicate attempts if already connecting to the same device
        if (_uiState.value.connectionState is BluetoothDeviceState.Connecting && timeoutRunnable != null) {
            Log.w(TAG, "[connect] Already connecting to ${selected.name}, ignoring duplicate trigger")
            return
        }

        cancelTimeout()
        connectInternal(selected.macAddress)
    }

    @SuppressLint("MissingPermission")
    private fun connectInternal(macAddress: String) {
        val bluetoothDevice = try {
            bluetoothAdapter?.getRemoteDevice(macAddress)
        } catch (e: Exception) {
            Log.e(TAG, "[connect] Failed to get remote device for $macAddress", e)
            null
        }

        val deviceName = getDeviceDisplayName(bluetoothDevice)

        if (bluetoothDevice == null) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Invalid device"),
                    userNotice = "Could not find device $deviceName ($macAddress)."
                )
            }
            return
        }

        Log.i(TAG, "[connect] Initiating connection attempt to $deviceName ($macAddress)")

        _uiState.update {
            it.copy(
                connectionState = BluetoothDeviceState.Connecting,
                userNotice = null
            )
        }

        val a2dp = a2dpProfile
        if (a2dp == null) {
            Log.d(TAG, "[connect] A2DP proxy not ready; requesting proxy and queueing connect for $macAddress")
            pendingConnectMac = macAddress
            startTimeoutTimer("Connection timed out waiting for Bluetooth audio service.")
            requestA2dpProxy()
            return
        }

        // Check if already connected on A2DP level
        val currentA2dpState = try {
            a2dp.getConnectionState(bluetoothDevice)
        } catch (e: Exception) {
            Log.w(TAG, "[connect] Error querying getConnectionState", e)
            BluetoothProfile.STATE_DISCONNECTED
        }

        Log.d(TAG, "[connect] Current A2DP state for $deviceName: $currentA2dpState")

        if (currentA2dpState == BluetoothProfile.STATE_CONNECTED) {
            Log.i(TAG, "[connect] Device $deviceName is already CONNECTED via A2DP")
            cancelTimeout()
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Connected(deviceName, macAddress),
                    userNotice = null
                )
            }
            return
        }

        // Call connect via reflection
        val success = invokeProfileConnect(a2dp, bluetoothDevice)
        Log.d(TAG, "[connect] invokeProfileConnect result: $success")

        if (success) {
            startTimeoutTimer("Connection attempt timed out. Ensure $deviceName is powered on and in Bluetooth mode.")
        } else {
            cancelTimeout()
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

        Log.i(TAG, "[disconnect] Initiating disconnection from ${selected.name} (${selected.macAddress})")

        cancelTimeout()
        pendingConnectMac = null

        val bluetoothDevice = try {
            bluetoothAdapter?.getRemoteDevice(selected.macAddress)
        } catch (e: Exception) {
            null
        }

        val a2dp = a2dpProfile

        _uiState.update {
            it.copy(connectionState = BluetoothDeviceState.Connecting)
        }

        // Start disconnect safety timeout
        startDisconnectTimeoutTimer()

        if (a2dp != null && bluetoothDevice != null) {
            val success = invokeProfileDisconnect(a2dp, bluetoothDevice)
            Log.d(TAG, "[disconnect] invokeProfileDisconnect result: $success")
            if (!success) {
                cancelTimeout()
                _uiState.update {
                    it.copy(connectionState = BluetoothDeviceState.Disconnected)
                }
            }
        } else {
            cancelTimeout()
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
            Log.d(TAG, "[reflection] BluetoothA2dp.connect() returned: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "[reflection] Failed to invoke BluetoothA2dp.connect()", e)
            false
        }
    }

    private fun invokeProfileDisconnect(profile: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val disconnectMethod: Method = profile.javaClass.getMethod("disconnect", BluetoothDevice::class.java)
            disconnectMethod.isAccessible = true
            val result = disconnectMethod.invoke(profile, device) as? Boolean ?: false
            Log.d(TAG, "[reflection] BluetoothA2dp.disconnect() returned: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "[reflection] Failed to invoke BluetoothA2dp.disconnect()", e)
            false
        }
    }

    private fun startTimeoutTimer(timeoutMessage: String) {
        cancelTimeout()
        Log.d(TAG, "[timer] Starting connection timeout timer ($CONNECT_TIMEOUT_MS ms)")
        val runnable = Runnable {
            Log.w(TAG, "[timer] Connection timer expired: $timeoutMessage")
            timeoutRunnable = null
            if (_uiState.value.connectionState is BluetoothDeviceState.Connecting) {
                _uiState.update {
                    it.copy(
                        connectionState = BluetoothDeviceState.Error(timeoutMessage),
                        userNotice = timeoutMessage
                    )
                }
            }
            refreshState()
        }
        timeoutRunnable = runnable
        mainHandler.postDelayed(runnable, CONNECT_TIMEOUT_MS)
    }

    private fun startDisconnectTimeoutTimer() {
        cancelTimeout()
        Log.d(TAG, "[timer] Starting disconnect timeout timer ($DISCONNECT_TIMEOUT_MS ms)")
        val runnable = Runnable {
            Log.d(TAG, "[timer] Disconnect timer expired, setting Disconnected")
            timeoutRunnable = null
            if (_uiState.value.connectionState is BluetoothDeviceState.Connecting) {
                _uiState.update {
                    it.copy(connectionState = BluetoothDeviceState.Disconnected)
                }
            }
            refreshState()
        }
        timeoutRunnable = runnable
        mainHandler.postDelayed(runnable, DISCONNECT_TIMEOUT_MS)
    }

    private fun cancelTimeout() {
        if (timeoutRunnable != null) {
            Log.d(TAG, "[timer] Cancelling active timeout timer")
            timeoutRunnable?.let { mainHandler.removeCallbacks(it) }
            timeoutRunnable = null
        }
    }

    @SuppressLint("MissingPermission")
    private fun isTargetDevice(device: BluetoothDevice?): Boolean {
        if (device == null) return false
        val selectedMac = selectedDeviceMac
        if (selectedMac != null && device.address.equals(selectedMac, ignoreCase = true)) {
            return true
        }
        if (selectedMac == null && isLgSoundbar(getDeviceDisplayName(device), device.address)) {
            return true
        }
        return false
    }

    @SuppressLint("MissingPermission")
    private fun getDeviceDisplayName(device: BluetoothDevice?): String {
        if (device != null && hasRequiredPermissions()) {
            try {
                val name = device.name
                if (!name.isNullOrBlank()) return name
            } catch (e: SecurityException) {
                Log.w(TAG, "SecurityException reading device name", e)
            }
        }
        return selectedDeviceMac ?: LG_SNC4R_NAME_DEFAULT
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
