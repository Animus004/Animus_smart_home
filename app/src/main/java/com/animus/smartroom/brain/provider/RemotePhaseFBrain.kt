package com.animus.smartroom.brain.provider

import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.client.AgentApiRemoteClient
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult

class RemotePhaseFBrain(
    private val client: AgentApiRemoteClient = AgentApiRemoteClient()
) : AnimusBrain {
    override val providerType: BrainProviderType = BrainProviderType.REMOTE_PHASE_F

    override suspend fun interpret(input: String): BrainResult {
        return client.interact(input)
    }
}
