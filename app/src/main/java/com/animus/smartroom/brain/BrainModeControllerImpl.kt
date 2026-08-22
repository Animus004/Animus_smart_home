package com.animus.smartroom.brain

import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.port.BrainModeController
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class BrainModeControllerImpl(
    initialMode: BrainMode = BrainMode.LOCAL
) : BrainModeController {

    private val _mode = MutableStateFlow(initialMode)
    override val mode: StateFlow<BrainMode> = _mode.asStateFlow()

    override fun setMode(mode: BrainMode) {
        _mode.value = mode
    }
}
