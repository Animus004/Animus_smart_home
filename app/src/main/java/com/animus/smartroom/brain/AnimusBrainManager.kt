package com.animus.smartroom.brain

import android.util.Log
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class AnimusBrainManager(
    private val localBrain: AnimusBrain = LocalAnimusBrain(),
    private val cloudBrain: AnimusBrain = CloudAnimusBrain()
) : AnimusBrain {

    companion object {
        private const val TAG = "AnimusBrainManager"
    }

    private val _activeProvider = MutableStateFlow(BrainProviderType.LOCAL)
    val activeProvider: StateFlow<BrainProviderType> = _activeProvider.asStateFlow()

    override val providerType: BrainProviderType
        get() = _activeProvider.value

    fun setProvider(type: BrainProviderType) {
        Log.i(TAG, "[provider] Switching active Brain provider to: $type")
        _activeProvider.value = type
    }

    override suspend fun interpret(input: String): BrainResult {
        val currentProvider = _activeProvider.value
        Log.d(TAG, "[interpret] Routing user input through provider: $currentProvider")

        val targetBrain = when (currentProvider) {
            BrainProviderType.LOCAL -> localBrain
            BrainProviderType.GEMINI -> cloudBrain
        }

        val result = targetBrain.interpret(input)

        // If cloud brain is unavailable, gracefully fall back to local brain
        return if (currentProvider == BrainProviderType.GEMINI && result is BrainResult.Unavailable) {
            Log.w(TAG, "[interpret] Cloud brain unavailable ($result). Falling back to Local Brain.")
            localBrain.interpret(input)
        } else {
            result
        }
    }
}
