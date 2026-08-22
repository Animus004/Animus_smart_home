package com.animus.smartroom.core.brain.port

import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse

interface BrainProvider {
    suspend fun understand(
        input: String,
        context: BrainContext
    ): BrainResponse

    fun isAvailable(): Boolean
}
