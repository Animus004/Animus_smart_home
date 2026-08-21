package com.animus.smartroom.device.tuya.model

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode

data class TuyaAcState(
    val power: Boolean = false,
    val targetTemperature: Int = 24,
    val ambientTemperature: Int = 24,
    val mode: AcMode = AcMode.AUTO,
    val fanSpeed: AcFanSpeed = AcFanSpeed.AUTO,
    val isOnline: Boolean = true
)
