package com.animus.smartroom.brain

import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult

interface AnimusBrain {
    val providerType: BrainProviderType
    suspend fun interpret(input: String): BrainResult
}
