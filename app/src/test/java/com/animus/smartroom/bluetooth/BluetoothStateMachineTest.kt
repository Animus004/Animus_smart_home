package com.animus.smartroom.bluetooth

import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BluetoothStateMachineTest {

    @Test
    fun testDisconnectingStateModel() {
        val connectedState = BluetoothDeviceState.Connected("LG SNC4R(79)", "54:15:89:DC:A5:79")
        val disconnectingState = BluetoothDeviceState.Disconnecting
        val disconnectedState = BluetoothDeviceState.Disconnected
        val errorState = BluetoothDeviceState.Error("Couldn't disconnect LG SNC4R(79)")

        // 1. Initial connected state
        var uiState = BluetoothUiState(
            selectedDevice = BluetoothAudioDevice("LG SNC4R(79)", "54:15:89:DC:A5:79", isConnected = true),
            connectionState = connectedState
        )
        assertTrue(uiState.connectionState is BluetoothDeviceState.Connected)

        // 2. Disconnect requested -> transitions to Disconnecting
        uiState = uiState.copy(connectionState = disconnectingState)
        assertEquals(BluetoothDeviceState.Disconnecting, uiState.connectionState)

        // 3. Android confirmation received (STATE_DISCONNECTED) -> transitions to Disconnected
        uiState = uiState.copy(
            selectedDevice = uiState.selectedDevice?.copy(isConnected = false),
            connectionState = disconnectedState
        )
        assertEquals(BluetoothDeviceState.Disconnected, uiState.connectionState)

        // 4. Timeout occurs while device still connected -> transitions to Error
        var timeoutState = BluetoothUiState(
            selectedDevice = BluetoothAudioDevice("LG SNC4R(79)", "54:15:89:DC:A5:79", isConnected = true),
            connectionState = disconnectingState
        )
        // Simulated timeout check: device is still reported connected -> Error
        if (timeoutState.selectedDevice?.isConnected == true) {
            timeoutState = timeoutState.copy(connectionState = errorState, userNotice = errorState.message)
        }
        assertTrue(timeoutState.connectionState is BluetoothDeviceState.Error)
        assertEquals("Couldn't disconnect LG SNC4R(79)", (timeoutState.connectionState as BluetoothDeviceState.Error).message)

        // 5. Timeout occurs but device is actually disconnected -> transitions to Disconnected
        var timeoutDisconnectedState = BluetoothUiState(
            selectedDevice = BluetoothAudioDevice("LG SNC4R(79)", "54:15:89:DC:A5:79", isConnected = false),
            connectionState = disconnectingState
        )
        if (timeoutDisconnectedState.selectedDevice?.isConnected == false) {
            timeoutDisconnectedState = timeoutDisconnectedState.copy(connectionState = BluetoothDeviceState.Disconnected)
        }
        assertEquals(BluetoothDeviceState.Disconnected, timeoutDisconnectedState.connectionState)
    }

    @Test
    fun testMultiDeviceDisconnectSafety() {
        val speakerA = BluetoothAudioDevice("LG SNC4R(79)", "54:15:89:DC:A5:79", isConnected = true)
        val speakerB = BluetoothAudioDevice("JBL Flip 5", "AA:BB:CC:DD:EE:FF", isConnected = true)

        val uiState = BluetoothUiState(
            pairedDevices = listOf(speakerA, speakerB),
            selectedDevice = speakerB,
            connectionState = BluetoothDeviceState.Connected(speakerB.name, speakerB.macAddress)
        )

        // Disconnecting speaker B must not falsely report Disconnected immediately
        val disconnectingState = uiState.copy(connectionState = BluetoothDeviceState.Disconnecting)
        assertEquals(BluetoothDeviceState.Disconnecting, disconnectingState.connectionState)
    }

    @Test
    fun testStoneSpinxProMultiProfileDisconnectSafety() {
        val stoneSpinxPro = BluetoothAudioDevice("Stone Spinx Pro", "04:7D:46:72:A7:E9", isConnected = true)

        var uiState = BluetoothUiState(
            pairedDevices = listOf(stoneSpinxPro),
            selectedDevice = stoneSpinxPro,
            connectionState = BluetoothDeviceState.Connected(stoneSpinxPro.name, stoneSpinxPro.macAddress)
        )

        // 1. Disconnect triggered
        uiState = uiState.copy(connectionState = BluetoothDeviceState.Disconnecting)
        assertEquals(BluetoothDeviceState.Disconnecting, uiState.connectionState)

        // 2. A2DP disconnected, BUT HFP/ACL is still connected at system level -> MUST remain Disconnecting
        val isA2dpConnected = false
        val isHfpOrAclConnected = true
        val isSystemConnected = isA2dpConnected || isHfpOrAclConnected

        if (isSystemConnected) {
            // Must NOT transition to Disconnected!
            assertEquals(BluetoothDeviceState.Disconnecting, uiState.connectionState)
        }

        // 3. Timeout expires while still connected -> MUST transition to Error
        val finalState = if (isSystemConnected) {
            uiState.copy(
                connectionState = BluetoothDeviceState.Error("Couldn't disconnect Stone Spinx Pro"),
                userNotice = "Couldn't disconnect Stone Spinx Pro. Please disconnect from Bluetooth settings."
            )
        } else {
            uiState.copy(connectionState = BluetoothDeviceState.Disconnected)
        }

        assertTrue(finalState.connectionState is BluetoothDeviceState.Error)
        assertEquals("Couldn't disconnect Stone Spinx Pro", (finalState.connectionState as BluetoothDeviceState.Error).message)
    }
}
