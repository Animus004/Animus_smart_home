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
    initialProvider: BrainProviderType = BrainProviderType.LOCAL,
    private val onProviderChanged: ((BrainProviderType) -> Unit)? = null
) : AnimusBrain {

    companion object {
        private const val TAG = "AnimusBrainManager"
    }

    private val _activeProvider = MutableStateFlow(initialProvider)
    val activeProvider: StateFlow<BrainProviderType> = _activeProvider.asStateFlow()

    override val providerType: BrainProviderType
        get() = _activeProvider.value

    fun setProvider(type: BrainProviderType) {
        Log.i(TAG, "[brain-selection] Brain provider set to: $type")
        _activeProvider.value = type
        onProviderChanged?.invoke(type)
    }

    override suspend fun interpret(input: String): BrainResult {
        return when (_activeProvider.value) {
            BrainProviderType.REMOTE_PHASE_F -> {
                Log.i(TAG, "[brain-selection] Delegating input directly to authoritative Animus Agent (Phase F): '$input'")
                remotePhaseFBrain.interpret(input)
            }
            BrainProviderType.GEMINI -> {
                val res = cloudBrain.interpret(input)
                if (res is BrainResult.Unavailable || res is BrainResult.Failure) {
                    Log.w(TAG, "[brain-fallback] Gemini unavailable or failed, falling back to local brain")
                    localBrain.interpret(input)
                } else {
                    res
                }
            }
            BrainProviderType.LOCAL -> {
                localBrain.interpret(input)
            }
        }
    }
}

