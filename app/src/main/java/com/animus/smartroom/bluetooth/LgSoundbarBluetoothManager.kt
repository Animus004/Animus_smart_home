package com.animus.smartroom.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
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
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.lang.reflect.Method

class LgSoundbarBluetoothManager(
    private val context: Context
) {
    companion object {
        private const val TAG = "LgBluetoothManager"
        const val TARGET_DEVICE_NAME = "LG SNC4R(79)"
        const val TARGET_DEVICE_NAME_FALLBACK = "LG SNC4R"
        const val TARGET_DEVICE_MAC = "54:15:89:DC:A5:79"
        private const val CONNECT_TIMEOUT_MS = 12000L
    }

    private val bluetoothManager: BluetoothManager? =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter

    private val _uiState = MutableStateFlow(
        BluetoothUiState(
            targetDeviceName = TARGET_DEVICE_NAME,
            targetDeviceMac = TARGET_DEVICE_MAC
        )
    )
    val uiState: StateFlow<BluetoothUiState> = _uiState.asStateFlow()

    private var a2dpProfile: BluetoothProfile? = null
    private var isReceiverRegistered = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null

    private val profileListener = object : BluetoothProfile.ServiceListener {
        override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "A2DP Profile Service Connected")
                a2dpProfile = proxy
                checkCurrentConnectionState()
            }
        }

        override fun onServiceDisconnected(profile: Int) {
            if (profile == BluetoothProfile.A2DP) {
                Log.d(TAG, "A2DP Profile Service Disconnected")
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
            Log.d(TAG, "Received Bluetooth broadcast: $action")

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
                    if (isEnabled) {
                        checkCurrentConnectionState()
                    }
                }

                BluetoothDevice.ACTION_ACL_CONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    if (isTargetDevice(device)) {
                        cancelTimeout()
                        val name = getDeviceDisplayName(device)
                        val mac = device?.address ?: TARGET_DEVICE_MAC
                        _uiState.update {
                            it.copy(
                                connectionState = BluetoothDeviceState.Connected(name, mac),
                                isPaired = true,
                                userNotice = null
                            )
                        }
                    }
                }

                BluetoothDevice.ACTION_ACL_DISCONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    if (isTargetDevice(device)) {
                        cancelTimeout()
                        _uiState.update {
                            it.copy(
                                connectionState = BluetoothDeviceState.Disconnected,
                                userNotice = null
                            )
                        }
                    }
                }

                "android.bluetooth.a2dp.profile.action.CONNECTION_STATE_CHANGED" -> {
                    val state = intent.getIntExtra(
                        BluetoothProfile.EXTRA_STATE,
                        BluetoothProfile.STATE_DISCONNECTED
                    )
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }

                    if (isTargetDevice(device)) {
                        when (state) {
                            BluetoothProfile.STATE_CONNECTED -> {
                                cancelTimeout()
                                val name = getDeviceDisplayName(device)
                                val mac = device?.address ?: TARGET_DEVICE_MAC
                                _uiState.update {
                                    it.copy(
                                        connectionState = BluetoothDeviceState.Connected(name, mac),
                                        isPaired = true,
                                        userNotice = null
                                    )
                                }
                            }
                            BluetoothProfile.STATE_CONNECTING -> {
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Connecting)
                                }
                            }
                            BluetoothProfile.STATE_DISCONNECTED -> {
                                cancelTimeout()
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Disconnected)
                                }
                            }
                            BluetoothProfile.STATE_DISCONNECTING -> {
                                _uiState.update {
                                    it.copy(connectionState = BluetoothDeviceState.Connecting)
                                }
                            }
                        }
                    }
                }

                BluetoothDevice.ACTION_BOND_STATE_CHANGED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    if (isTargetDevice(device)) {
                        val bondState = intent.getIntExtra(
                            BluetoothDevice.EXTRA_BOND_STATE,
                            BluetoothDevice.BOND_NONE
                        )
                        val isPaired = bondState == BluetoothDevice.BOND_BONDED
                        _uiState.update { it.copy(isPaired = isPaired) }
                    }
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

    fun refreshState() {
        val hasPerms = hasRequiredPermissions()
        val isEnabled = bluetoothAdapter?.isEnabled == true
        val targetDevice = findTargetDevice()
        val isPaired = targetDevice != null && targetDevice.bondState == BluetoothDevice.BOND_BONDED

        _uiState.update {
            it.copy(
                hasRequiredPermissions = hasPerms,
                isBluetoothEnabled = isEnabled,
                isPaired = isPaired
            )
        }

        if (hasPerms && isEnabled) {
            checkCurrentConnectionState()
        }
    }

    @SuppressLint("MissingPermission")
    private fun checkCurrentConnectionState() {
        if (!hasRequiredPermissions() || bluetoothAdapter?.isEnabled != true) {
            _uiState.update {
                it.copy(connectionState = BluetoothDeviceState.Disconnected)
            }
            return
        }

        val target = findTargetDevice()
        if (target == null) {
            _uiState.update {
                it.copy(
                    isPaired = false,
                    connectionState = BluetoothDeviceState.Disconnected
                )
            }
            return
        }

        val a2dp = a2dpProfile
        if (a2dp != null) {
            val state = a2dp.getConnectionState(target)
            if (state == BluetoothProfile.STATE_CONNECTED) {
                val name = getDeviceDisplayName(target)
                _uiState.update {
                    it.copy(
                        isPaired = true,
                        connectionState = BluetoothDeviceState.Connected(name, target.address)
                    )
                }
                return
            }
        }

        // Check bonded status
        val isBonded = target.bondState == BluetoothDevice.BOND_BONDED
        _uiState.update {
            it.copy(
                isPaired = isBonded,
                connectionState = if (it.connectionState is BluetoothDeviceState.Connecting) {
                    it.connectionState
                } else {
                    BluetoothDeviceState.Disconnected
                }
            )
        }
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

        val targetDevice = findTargetDevice()
        if (targetDevice == null) {
            _uiState.update {
                it.copy(
                    isPaired = false,
                    connectionState = BluetoothDeviceState.Error("LG SNC4R is not paired"),
                    userNotice = "LG SNC4R ($TARGET_DEVICE_MAC) is not paired. Please pair it in Bluetooth settings first."
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

        // Check if already connected
        if (a2dp.getConnectionState(targetDevice) == BluetoothProfile.STATE_CONNECTED) {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Connected(
                        deviceName = getDeviceDisplayName(targetDevice),
                        macAddress = targetDevice.address
                    ),
                    isPaired = true
                )
            }
            return
        }

        // Connect via A2DP reflection
        val success = invokeProfileConnect(a2dp, targetDevice)
        if (success) {
            startTimeoutTimer("Connection attempt timed out. Ensure the soundbar is powered on and in Bluetooth mode.")
        } else {
            _uiState.update {
                it.copy(
                    connectionState = BluetoothDeviceState.Error("Could not initiate A2DP connection"),
                    userNotice = "Unable to connect automatically. Please connect from system Bluetooth settings."
                )
            }
        }
    }

    @SuppressLint("MissingPermission")
    fun disconnect() {
        if (!hasRequiredPermissions()) return

        val target = findTargetDevice() ?: return
        val a2dp = a2dpProfile

        _uiState.update {
            it.copy(connectionState = BluetoothDeviceState.Connecting)
        }

        if (a2dp != null) {
            val success = invokeProfileDisconnect(a2dp, target)
            if (!success) {
                _uiState.update {
                    it.copy(connectionState = BluetoothDeviceState.Disconnected)
                }
            }
        } else {
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
        timeoutRunnable = Runnable {
            if (_uiState.value.connectionState is BluetoothDeviceState.Connecting) {
                _uiState.update {
                    it.copy(
                        connectionState = BluetoothDeviceState.Error(timeoutMessage),
                        userNotice = timeoutMessage
                    )
                }
            }
        }
        mainHandler.postDelayed(timeoutRunnable!!, CONNECT_TIMEOUT_MS)
    }

    private fun cancelTimeout() {
        timeoutRunnable?.let { mainHandler.removeCallbacks(it) }
        timeoutRunnable = null
    }

    @SuppressLint("MissingPermission")
    private fun findTargetDevice(): BluetoothDevice? {
        if (!hasRequiredPermissions() || bluetoothAdapter == null) return null

        val bondedDevices = try {
            bluetoothAdapter.bondedDevices
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException while accessing bondedDevices", e)
            return null
        } ?: emptySet()

        // 1. Try matching by MAC address first (most accurate)
        val byMac = bondedDevices.find {
            it.address.equals(TARGET_DEVICE_MAC, ignoreCase = true)
        }
        if (byMac != null) return byMac

        // 2. Fallback to matching by device name
        return bondedDevices.find { device ->
            val name = try { device.name } catch (e: SecurityException) { null }
            name != null && (name.contains(TARGET_DEVICE_NAME_FALLBACK, ignoreCase = true) ||
                    name.equals(TARGET_DEVICE_NAME, ignoreCase = true))
        }
    }

    @SuppressLint("MissingPermission")
    private fun isTargetDevice(device: BluetoothDevice?): Boolean {
        if (device == null) return false
        if (device.address.equals(TARGET_DEVICE_MAC, ignoreCase = true)) return true
        if (hasRequiredPermissions()) {
            val name = try { device.name } catch (e: SecurityException) { null }
            if (name != null && name.contains(TARGET_DEVICE_NAME_FALLBACK, ignoreCase = true)) {
                return true
            }
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
        return TARGET_DEVICE_NAME
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
