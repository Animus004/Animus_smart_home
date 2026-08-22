package com.animus.smartroom.core.brain.port

import com.animus.smartroom.core.brain.BrainMode
import kotlinx.coroutines.flow.StateFlow

interface BrainModeController {
    val mode: StateFlow<BrainMode>
    fun setMode(mode: BrainMode)
}
