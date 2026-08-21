package com.animus.smartroom.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothA2dp
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothHeadset
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
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withTimeout
import java.lang.reflect.Method

class BluetoothAudioDeviceManager(
    private val context: Context
) {
    companion object {
        private const val TAG = "BluetoothAudioMgr"
        const val LG_SNC4R_NAME_DEFAULT = "LG SNC4R(79)"
        const val LG_SNC4R_NAME_FALLBACK = "LG SNC4R"
        const val LG_SNC4R_MAC_DEFAULT = "54:15:89:DC:A5:79"
        const val STONE_SPINX_PRO_MAC = "04:7D:46:72:A7:E9"
        private const val CONNECT_TIMEOUT_MS = 10000L
        private const val DISCONNECT_TIMEOUT_MS = 6000L
    }

    private val bluetoothManager: BluetoothManager? =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter
    private val aliasManager = BluetoothDeviceAliasManager(context)

    private val _uiState = MutableStateFlow(BluetoothUiState())
    val uiState: StateFlow<BluetoothUiState> = _uiState.asStateFlow()

    private var selectedDeviceMac: String? = null
    private var pendingConnectMac: String? = null
    private var a2dpProfile: BluetoothProfile? = null
    private var headsetProfile: BluetoothProfile? = null
    private var isReceiverRegistered = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null

    private val a2dpListener = object : BluetoothProfile.ServiceListener {
        override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "[proxy] A2DP Profile Proxy acquired: $proxy")
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
                refreshState()
            }
        }
    }

    private val headsetListener = object : BluetoothProfile.ServiceListener {
        override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
            if (profile == BluetoothProfile.HEADSET) {
                Log.d(TAG, "[proxy] HEADSET Profile Proxy acquired: $proxy")
                headsetProfile = proxy
                refreshState()
            }
        }

        override fun onServiceDisconnected(profile: Int) {
            if (profile == BluetoothProfile.HEADSET) {
                Log.w(TAG, "[proxy] HEADSET Profile Proxy disconnected by system")
                headsetProfile = null
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
                        closeProfileProxies()
                        _uiState.update {
                            it.copy(
                                isBluetoothEnabled = false,
                                connectionState = BluetoothDeviceState.Disconnected,
                                userNotice = "Bluetooth is turned off"
                            )
                        }
                    } else {
                        _uiState.update { it.copy(isBluetoothEnabled = true, userNotice = null) }
                        requestProfileProxies()
                        refreshState()
                    }
                }

                BluetoothA2dp.ACTION_CONNECTION_STATE_CHANGED,
                BluetoothHeadset.ACTION_CONNECTION_STATE_CHANGED -> {
                    val state = intent.getIntExtra(BluetoothProfile.EXTRA_STATE, BluetoothProfile.STATE_DISCONNECTED)
                    val prevState = intent.getIntExtra(BluetoothProfile.EXTRA_PREVIOUS_STATE, BluetoothProfile.STATE_DISCONNECTED)
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }

                    Log.d(TAG, "[broadcast] Profile state changed for ${device?.address} (${device?.name}): action=$action, state=$state, prevState=$prevState")

                    if (isTargetDevice(device)) {
                        when (state) {
                            BluetoothProfile.STATE_CONNECTED -> {
                                cancelTimeout()
                                val name = getDeviceDisplayName(device)
                                val mac = device?.address ?: (selectedDeviceMac ?: LG_SNC4R_MAC_DEFAULT)
                                Log.i(TAG, "[broadcast] Profile CONNECTED for $name ($mac)")
                                _uiState.update {
                                    it.copy(
                                        connectionState = BluetoothDeviceState.Connected(name, mac),
                                        userNotice = null
                                    )
                                }
                            }

                            BluetoothProfile.STATE_CONNECTING -> {
                                if (_uiState.value.connectionState !is BluetoothDeviceState.Disconnecting) {
                                    _uiState.update {
                                        it.copy(connectionState = BluetoothDeviceState.Connecting)
                                    }
                                }
                            }

                            BluetoothProfile.STATE_DISCONNECTING -> {
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Disconnecting)
                                }
                            }

                            BluetoothProfile.STATE_DISCONNECTED -> {
                                val isStillConnectedAtSystem = isDeviceConnectedAtSystemLevel(device)
                                Log.d(TAG, "[broadcast] Profile DISCONNECTED for ${device?.address}. isStillConnectedAtSystem=$isStillConnectedAtSystem")

                                if (isStillConnectedAtSystem) {
                                    Log.w(TAG, "[broadcast] Target device is STILL CONNECTED to other profiles/ACL at system level. Retaining current state.")
                                } else {
                                    cancelTimeout()
                                    val newState = if (prevState == BluetoothProfile.STATE_CONNECTING) {
                                        BluetoothDeviceState.Error("Connection attempt failed or was rejected by device.")
                                    } else {
                                        BluetoothDeviceState.Disconnected
                                    }
                                    _uiState.update {
                                        it.copy(
                                            connectionState = newState,
                                            userNotice = if (newState is BluetoothDeviceState.Error) newState.message else null
                                        )
                                    }
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
                        val isStillConnectedAtSystem = isDeviceConnectedAtSystemLevel(device)
                        Log.d(TAG, "[broadcast] ACL Disconnected received. isStillConnectedAtSystem=$isStillConnectedAtSystem")
                        if (!isStillConnectedAtSystem) {
                            cancelTimeout()
                            _uiState.update {
                                it.copy(connectionState = BluetoothDeviceState.Disconnected)
                            }
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
                addAction(BluetoothHeadset.ACTION_CONNECTION_STATE_CHANGED)
                addAction(BluetoothDevice.ACTION_ACL_CONNECTED)
                addAction(BluetoothDevice.ACTION_ACL_DISCONNECTED)
                addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
            }
            context.registerReceiver(bluetoothReceiver, filter)
            isReceiverRegistered = true
            Log.d(TAG, "[lifecycle] BroadcastReceiver registered")
        }

        requestProfileProxies()
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
        closeProfileProxies()
    }

    private fun requestProfileProxies() {
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            Log.w(TAG, "[proxy] BluetoothAdapter is null or disabled; cannot request proxies")
            return
        }

        closeProfileProxies()

        Log.d(TAG, "[proxy] Requesting A2DP profile proxy")
        bluetoothAdapter.getProfileProxy(context, a2dpListener, BluetoothProfile.A2DP)

        Log.d(TAG, "[proxy] Requesting HEADSET profile proxy")
        bluetoothAdapter.getProfileProxy(context, headsetListener, BluetoothProfile.HEADSET)
    }

    private fun closeProfileProxies() {
        if (bluetoothAdapter != null) {
            a2dpProfile?.let {
                try { bluetoothAdapter.closeProfileProxy(BluetoothProfile.A2DP, it) } catch (e: Exception) { /* ignore */ }
            }
            a2dpProfile = null

            headsetProfile?.let {
                try { bluetoothAdapter.closeProfileProxy(BluetoothProfile.HEADSET, it) } catch (e: Exception) { /* ignore */ }
            }
            headsetProfile = null
        }
    }

    fun selectDevice(macAddress: String) {
        Log.d(TAG, "[device] Device selected by user: $macAddress")
        selectedDeviceMac = macAddress
        cancelTimeout()
        refreshState()
    }

    @SuppressLint("MissingPermission")
    fun isDeviceConnectedAtSystemLevel(device: BluetoothDevice?): Boolean {
        if (device == null) return false

        // 1. Check hidden / reflection BluetoothDevice.isConnected() (direct physical ACL link check)
        try {
            val isConnectedMethod = device.javaClass.getMethod("isConnected")
            isConnectedMethod.isAccessible = true
            val result = isConnectedMethod.invoke(device) as? Boolean
            if (result == true) {
                return true
            }
        } catch (e: Exception) {
            Log.v(TAG, "[state] BluetoothDevice.isConnected reflection: ${e.message}")
        }

        // 2. Check A2DP proxy
        val a2dp = a2dpProfile
        if (a2dp != null) {
            try {
                if (a2dp.getConnectionState(device) == BluetoothProfile.STATE_CONNECTED) {
                    return true
                }
            } catch (e: Exception) { /* ignore */ }
        }

        // 3. Check HEADSET proxy
        val headset = headsetProfile
        if (headset != null) {
            try {
                if (headset.getConnectionState(device) == BluetoothProfile.STATE_CONNECTED) {
                    return true
                }
            } catch (e: Exception) { /* ignore */ }
        }

        // 4. Check BluetoothManager.getConnectedDevices for GATT profile
        if (bluetoothManager != null && hasRequiredPermissions()) {
            try {
                val gattDevices = bluetoothManager.getConnectedDevices(BluetoothProfile.GATT)
                if (gattDevices.any { it.address.equals(device.address, ignoreCase = true) }) {
                    return true
                }
            } catch (e: Exception) { /* ignore */ }
        }

        return false
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

        val deviceList = bondedDevices.map { device ->
            val name = try { device.name ?: "Unknown Device" } catch (e: SecurityException) { "Unknown Device" }
            val mac = device.address
            val isConnected = isDeviceConnectedAtSystemLevel(device)

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
                    name.contains("buds", ignoreCase = true) ||
                    name.contains("spinx", ignoreCase = true) ||
                    name.contains("stone", ignoreCase = true) ||
                    mac.equals(STONE_SPINX_PRO_MAC, ignoreCase = true)

            val alias = aliasManager.getAlias(mac)
            BluetoothAudioDevice(
                name = name,
                macAddress = mac,
                alias = alias,
                isBonded = true,
                isConnected = isConnected,
                isAudioDevice = isAudio
            )
        }.sortedWith(
            compareByDescending<BluetoothAudioDevice> { it.isConnected }
                .thenByDescending { isLgSoundbar(it.name, it.macAddress) }
                .thenByDescending { it.macAddress.equals(STONE_SPINX_PRO_MAC, ignoreCase = true) }
                .thenByDescending { it.isAudioDevice }
                .thenBy { it.displayName }
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

        val targetBtDevice = try {
            if (resolvedSelectedDevice != null) bluetoothAdapter.getRemoteDevice(resolvedSelectedDevice.macAddress) else null
        } catch (e: Exception) {
            null
        }

        // Determine system-level connection state for the resolved selected device
        val isSelectedConnected = isDeviceConnectedAtSystemLevel(targetBtDevice)

        val currentConnState = _uiState.value.connectionState
        val resolvedConnState: BluetoothDeviceState = when {
            resolvedSelectedDevice == null -> BluetoothDeviceState.Disconnected
            isSelectedConnected -> {
                if (currentConnState is BluetoothDeviceState.Disconnecting && timeoutRunnable != null) {
                    BluetoothDeviceState.Disconnecting
                } else {
                    BluetoothDeviceState.Connected(
                        deviceName = resolvedSelectedDevice.name,
                        macAddress = resolvedSelectedDevice.macAddress
                    )
                }
            }
            currentConnState is BluetoothDeviceState.Connecting && timeoutRunnable != null -> {
                BluetoothDeviceState.Connecting
            }
            currentConnState is BluetoothDeviceState.Disconnecting && timeoutRunnable != null -> {
                // Device confirmed NOT connected at system level -> disconnect complete!
                cancelTimeout()
                BluetoothDeviceState.Disconnected
            }
            currentConnState is BluetoothDeviceState.Error -> currentConnState
            else -> BluetoothDeviceState.Disconnected
        }

        Log.d(TAG, "[state] State refreshed: selected=${resolvedSelectedDevice?.name} (${resolvedSelectedDevice?.macAddress}), systemConnected=$isSelectedConnected, connState=$resolvedConnState, pairedCount=${deviceList.size}")

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

    /**
     * Suspends until the Bluetooth connection reaches Connected or Error state,
     * or until the timeout expires.
     */
    suspend fun awaitConnection(timeoutMs: Long = 6000L): Boolean {
        if (_uiState.value.connectionState is BluetoothDeviceState.Connected) {
            return true
        }

        return try {
            withTimeout(timeoutMs) {
                _uiState.filter {
                    it.connectionState is BluetoothDeviceState.Connected ||
                            it.connectionState is BluetoothDeviceState.Error
                }.first().connectionState is BluetoothDeviceState.Connected
            }
        } catch (e: TimeoutCancellationException) {
            Log.w(TAG, "[awaitConnection] Timed out after ${timeoutMs}ms waiting for Bluetooth connection")
            _uiState.value.connectionState is BluetoothDeviceState.Connected
        }
    }

    /**
     * Connects to the selected device and awaits completion.
     */
    suspend fun connectAndAwait(timeoutMs: Long = 6000L): Boolean {
        if (_uiState.value.connectionState is BluetoothDeviceState.Connected) {
            return true
        }
        connect()
        return awaitConnection(timeoutMs)
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
            Log.d(TAG, "[connect] A2DP proxy not ready; requesting proxies and queueing connect for $macAddress")
            pendingConnectMac = macAddress
            startTimeoutTimer("Connection timed out waiting for Bluetooth audio service.")
            requestProfileProxies()
            return
        }

        // Check if already connected at system level
        if (isDeviceConnectedAtSystemLevel(bluetoothDevice)) {
            Log.i(TAG, "[connect] Device $deviceName is already CONNECTED at system level")
            cancelTimeout()
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Connected(deviceName, macAddress),
                    userNotice = null
                )
            }
            return
        }

        // Connect A2DP profile
        val a2dpSuccess = invokeProfileConnect(a2dp, bluetoothDevice)
        Log.d(TAG, "[connect] invokeProfileConnect (A2DP) result: $a2dpSuccess")

        // Connect HEADSET profile if available
        headsetProfile?.let { proxy ->
            val headsetSuccess = invokeProfileConnect(proxy, bluetoothDevice)
            Log.d(TAG, "[connect] invokeProfileConnect (HEADSET) result: $headsetSuccess")
        }

        if (a2dpSuccess) {
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

        // Prevent duplicate disconnect calls
        if (_uiState.value.connectionState is BluetoothDeviceState.Disconnecting && timeoutRunnable != null) {
            Log.w(TAG, "[disconnect] Disconnection from ${selected.name} already in progress, ignoring duplicate trigger")
            return
        }

        val bluetoothDevice = try {
            bluetoothAdapter?.getRemoteDevice(selected.macAddress)
        } catch (e: Exception) {
            null
        }

        val isConnectedAtSystem = isDeviceConnectedAtSystemLevel(bluetoothDevice)
        if (!isConnectedAtSystem && _uiState.value.connectionState is BluetoothDeviceState.Disconnected) {
            Log.d(TAG, "[disconnect] Already disconnected from ${selected.name}")
            return
        }

        Log.i(TAG, "[disconnect] Initiating full system disconnection from ${selected.name} (${selected.macAddress})")

        cancelTimeout()
        pendingConnectMac = null

        // Transition to Disconnecting state
        _uiState.update {
            it.copy(
                connectionState = BluetoothDeviceState.Disconnecting,
                userNotice = null
            )
        }

        // Start bounded disconnect safety timeout
        startDisconnectTimeoutTimer(selected.name, selected.macAddress)

        if (bluetoothDevice != null) {
            // 1. Invoke A2DP profile disconnect
            a2dpProfile?.let { proxy ->
                val a2dpSuccess = invokeProfileDisconnect(proxy, bluetoothDevice)
                Log.d(TAG, "[disconnect] invoke A2DP disconnect result: $a2dpSuccess")
            }

            // 2. Invoke HEADSET profile disconnect
            headsetProfile?.let { proxy ->
                val headsetSuccess = invokeProfileDisconnect(proxy, bluetoothDevice)
                Log.d(TAG, "[disconnect] invoke HEADSET disconnect result: $headsetSuccess")
            }

            // 3. Invoke BluetoothDevice.disconnect() (API 29+ hidden method: tears down all profiles & ACL)
            val deviceSuccess = invokeDeviceDisconnect(bluetoothDevice)
            Log.d(TAG, "[disconnect] invoke BluetoothDevice.disconnect() result: $deviceSuccess")

            // 4. Invoke BluetoothAdapter.disconnect(device) if available via reflection
            invokeAdapterDisconnect(bluetoothDevice)
        }
    }

    private fun invokeProfileConnect(profile: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val connectMethod: Method = profile.javaClass.getMethod("connect", BluetoothDevice::class.java)
            connectMethod.isAccessible = true
            val result = connectMethod.invoke(profile, device) as? Boolean ?: false
            Log.d(TAG, "[reflection] ${profile.javaClass.simpleName}.connect() returned: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "[reflection] Failed to invoke connect() on ${profile.javaClass.simpleName}", e)
            false
        }
    }

    private fun invokeProfileDisconnect(profile: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val disconnectMethod: Method = profile.javaClass.getMethod("disconnect", BluetoothDevice::class.java)
            disconnectMethod.isAccessible = true
            val result = disconnectMethod.invoke(profile, device) as? Boolean ?: false
            Log.d(TAG, "[reflection] ${profile.javaClass.simpleName}.disconnect() returned: $result")
            true
        } catch (e: Exception) {
            Log.e(TAG, "[reflection] Failed to invoke disconnect() on ${profile.javaClass.simpleName}", e)
            false
        }
    }

    private fun invokeDeviceDisconnect(device: BluetoothDevice): Boolean {
        return try {
            val disconnectMethod: Method = device.javaClass.getMethod("disconnect")
            disconnectMethod.isAccessible = true
            val result = disconnectMethod.invoke(device) as? Boolean ?: false
            Log.d(TAG, "[reflection] BluetoothDevice.disconnect() returned: $result")
            true
        } catch (e: Exception) {
            Log.d(TAG, "[reflection] BluetoothDevice.disconnect() not available: ${e.message}")
            false
        }
    }

    private fun invokeAdapterDisconnect(device: BluetoothDevice): Boolean {
        val adapter = bluetoothAdapter ?: return false
        return try {
            val disconnectMethod: Method = adapter.javaClass.getMethod("disconnect", BluetoothDevice::class.java)
            disconnectMethod.isAccessible = true
            val result = disconnectMethod.invoke(adapter, device) as? Boolean ?: false
            Log.d(TAG, "[reflection] BluetoothAdapter.disconnect() returned: $result")
            true
        } catch (e: Exception) {
            Log.d(TAG, "[reflection] BluetoothAdapter.disconnect() not available: ${e.message}")
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

    @SuppressLint("MissingPermission")
    private fun startDisconnectTimeoutTimer(targetName: String, macAddress: String) {
        cancelTimeout()
        Log.d(TAG, "[timer] Starting disconnect timeout timer ($DISCONNECT_TIMEOUT_MS ms) for $targetName")
        val runnable = Runnable {
            Log.w(TAG, "[timer] Disconnect timer expired for $targetName ($macAddress)")
            timeoutRunnable = null

            val device = try { bluetoothAdapter?.getRemoteDevice(macAddress) } catch (e: Exception) { null }
            val isStillConnected = isDeviceConnectedAtSystemLevel(device)

            if (isStillConnected) {
                Log.e(TAG, "[timer] Disconnect timed out: $targetName is STILL CONNECTED at system level")
                _uiState.update {
                    it.copy(
                        connectionState = BluetoothDeviceState.Error("Couldn't disconnect $targetName"),
                        userNotice = "Couldn't disconnect $targetName. Please disconnect from Bluetooth settings."
                    )
                }
            } else {
                Log.i(TAG, "[timer] Disconnect confirmed via system-level check for $targetName")
                _uiState.update {
                    it.copy(
                        connectionState = BluetoothDeviceState.Disconnected,
                        userNotice = null
                    )
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
        if (device != null) {
            val alias = aliasManager.getAlias(device.address)
            if (!alias.isNullOrBlank()) return alias
            if (hasRequiredPermissions()) {
                try {
                    val name = device.name
                    if (!name.isNullOrBlank()) return name
                } catch (e: SecurityException) {
                    Log.w(TAG, "SecurityException reading device name", e)
                }
            }
            return device.address
        }
        val selectedMac = selectedDeviceMac
        if (selectedMac != null) {
            val alias = aliasManager.getAlias(selectedMac)
            if (!alias.isNullOrBlank()) return alias
            return selectedMac
        }
        return LG_SNC4R_NAME_DEFAULT
    }

    fun setDeviceAlias(macAddress: String, alias: String?) {
        Log.i(TAG, "[alias] Setting alias for $macAddress: '$alias'")
        aliasManager.setAlias(macAddress, alias)
        refreshState()
    }

    fun getDeviceAlias(macAddress: String): String? {
        return aliasManager.getAlias(macAddress)
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
