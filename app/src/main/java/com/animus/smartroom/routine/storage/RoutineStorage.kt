package com.animus.smartroom.routine.storage

import android.content.Context
import android.util.Log
import com.animus.smartroom.core.port.AndroidPersistentStore
import com.animus.smartroom.core.port.PersistentStore
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.routine.model.EnvironmentSnapshot
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.model.RoutineType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

open class RoutineStorage(
    context: Context? = null,
    store: PersistentStore? = null
) {

    companion object {
        private const val TAG = "RoutineStorage"
        const val PREFS_NAME = "animus_routines_prefs"
        const val KEY_ACTIVE_ROUTINE = "active_routine_json"

        // Process-wide StateFlow to guarantee instantaneous state synchronization across Receiver, Engine, ViewModel & UI
        private val _globalActiveRoutineFlow = MutableStateFlow<RoutineState?>(null)
        val activeRoutineFlow: StateFlow<RoutineState?> = _globalActiveRoutineFlow.asStateFlow()
    }

    val activeRoutineFlow: StateFlow<RoutineState?>
        get() = _globalActiveRoutineFlow.asStateFlow()

    private val persistentStore: PersistentStore? = store ?: context?.let { AndroidPersistentStore(it, PREFS_NAME) }

    private val storeListener: (String) -> Unit = { key ->
        if (key == KEY_ACTIVE_ROUTINE) {
            val updated = readFromStore()
            _globalActiveRoutineFlow.value = updated
            Log.d(TAG, "[storage] Preference change detected -> status: ${updated?.status}")
        }
    }

    init {
        persistentStore?.registerChangeListener(storeListener)
        val initial = readFromStore()
        if (_globalActiveRoutineFlow.value == null && initial != null) {
            _globalActiveRoutineFlow.value = initial
        }
    }

    open fun saveActiveRoutine(routine: RoutineState?) {
        _globalActiveRoutineFlow.value = routine
        val p = persistentStore ?: return
        if (routine == null) {
            p.remove(KEY_ACTIVE_ROUTINE)
            DiagnosticBus.log(
                tag = "storage",
                stage = DiagnosticStage.PERSISTED,
                message = "status=NONE"
            )
            return
        }

        try {
            val json = JSONObject().apply {
                put("id", routine.id)
                put("type", routine.type.name)
                put("createdAt", routine.createdAt)
                if (routine.scheduledWakeTime != null) {
                    put("scheduledWakeTime", routine.scheduledWakeTime)
                }
                put("status", routine.status.name)
                if (routine.failureReason != null) {
                    put("failureReason", routine.failureReason)
                }

                routine.initialSnapshot?.let { snap ->
                    val snapJson = JSONObject().apply {
                        put("isSpeakerConnected", snap.isSpeakerConnected)
                        if (snap.speakerName != null) put("speakerName", snap.speakerName)
                        put("mediaVolume", snap.mediaVolume.toDouble())
                        put("isMusicPlaying", snap.isMusicPlaying)
                        if (snap.acPower != null) put("acPower", snap.acPower)
                        if (snap.acTargetTemperature != null) put("acTargetTemperature", snap.acTargetTemperature)
                        if (snap.acMode != null) put("acMode", snap.acMode)
                        if (snap.acFanSpeed != null) put("acFanSpeed", snap.acFanSpeed)
                    }
                    put("initialSnapshot", snapJson)
                }
            }

            p.putString(KEY_ACTIVE_ROUTINE, json.toString())
            Log.d(TAG, "[storage] Saved routine: ${routine.id} (Status: ${routine.status})")
            DiagnosticBus.log(
                tag = "storage",
                stage = DiagnosticStage.PERSISTED,
                message = "status=${routine.status.name}"
            )
        } catch (e: Exception) {
            Log.e(TAG, "[storage] Failed to serialize routine state", e)
        }
    }

    open fun getActiveRoutine(): RoutineState? {
        val currentFlowValue = _globalActiveRoutineFlow.value
        if (currentFlowValue != null) return currentFlowValue
        return readFromStore()
    }

    private fun readFromStore(): RoutineState? {
        val raw = persistentStore?.getString(KEY_ACTIVE_ROUTINE, null) ?: return null
        return try {
            val json = JSONObject(raw)
            val id = json.getString("id")
            val type = RoutineType.valueOf(json.optString("type", RoutineType.SLEEP.name))
            val createdAt = json.optLong("createdAt", System.currentTimeMillis())
            val scheduledWakeTime = if (json.has("scheduledWakeTime")) json.getLong("scheduledWakeTime") else null
            val status = RoutineStatus.valueOf(json.optString("status", RoutineStatus.ACTIVE.name))
            val failureReason = if (json.has("failureReason")) json.getString("failureReason") else null

            var snapshot: EnvironmentSnapshot? = null
            if (json.has("initialSnapshot")) {
                val snapJson = json.getJSONObject("initialSnapshot")
                snapshot = EnvironmentSnapshot(
                    isSpeakerConnected = snapJson.optBoolean("isSpeakerConnected", false),
                    speakerName = if (snapJson.has("speakerName")) snapJson.getString("speakerName") else null,
                    mediaVolume = snapJson.optDouble("mediaVolume", 0.5).toFloat(),
                    isMusicPlaying = snapJson.optBoolean("isMusicPlaying", false),
                    acPower = if (snapJson.has("acPower")) snapJson.getBoolean("acPower") else null,
                    acTargetTemperature = if (snapJson.has("acTargetTemperature")) snapJson.getInt("acTargetTemperature") else null,
                    acMode = if (snapJson.has("acMode")) snapJson.getString("acMode") else null,
                    acFanSpeed = if (snapJson.has("acFanSpeed")) snapJson.getString("acFanSpeed") else null
                )
            }

            RoutineState(
                id = id,
                type = type,
                createdAt = createdAt,
                scheduledWakeTime = scheduledWakeTime,
                status = status,
                failureReason = failureReason,
                initialSnapshot = snapshot
            )
        } catch (e: Exception) {
            Log.e(TAG, "[storage] Failed to parse routine state", e)
            null
        }
    }

    open fun clearActiveRoutine() {
        _globalActiveRoutineFlow.value = null
        persistentStore?.remove(KEY_ACTIVE_ROUTINE)
        DiagnosticBus.log(
            tag = "storage",
            stage = DiagnosticStage.PERSISTED,
            message = "status=NONE"
        )
    }
}
