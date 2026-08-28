package com.animus.smartroom.brain

import android.util.Log
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.brain.provider.RemotePhaseFBrain
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class AnimusBrainManager(
    val localBrain: AnimusBrain = LocalAnimusBrain(),
    val cloudBrain: AnimusBrain = CloudAnimusBrain(),
    val remotePhaseFBrain: AnimusBrain = RemotePhaseFBrain(),
    initialProvider: BrainProviderType = BrainProviderType.REMOTE_PHASE_F,
    private val onProviderChanged: ((BrainProviderType) -> Unit)? = null
) : AnimusBrain {

    companion object {
        private const val TAG = "AnimusBrainManager"
    }

    private val _activeProvider = MutableStateFlow(BrainProviderType.REMOTE_PHASE_F)
    val activeProvider: StateFlow<BrainProviderType> = _activeProvider.asStateFlow()

    override val providerType: BrainProviderType
        get() = BrainProviderType.REMOTE_PHASE_F

    fun setProvider(type: BrainProviderType) {
        Log.i(TAG, "[brain-selection] Brain provider set to: $type (Authoritative Animus backend active)")
        _activeProvider.value = BrainProviderType.REMOTE_PHASE_F
        onProviderChanged?.invoke(BrainProviderType.REMOTE_PHASE_F)
    }

    override suspend fun interpret(input: String): BrainResult {
        Log.i(TAG, "[brain-selection] Delegating input directly to authoritative Animus Agent (Phase F): '$input'")
        return remotePhaseFBrain.interpret(input)
    }
}

