package com.animus.smartroom.scheduler.storage

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import com.animus.smartroom.device.model.DeviceType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

open class ScheduledActionStorage(context: Context? = null) {

    companion object {
        private const val TAG = "ScheduledActionStorage"
        private const val PREFS_NAME = "animus_scheduled_actions_prefs"

        // Global StateFlow to guarantee UI and background service synchronization
        private val _globalActionsFlow = MutableStateFlow<List<ScheduledDeviceAction>>(emptyList())
        val activeActionsFlow: StateFlow<List<ScheduledDeviceAction>> = _globalActionsFlow.asStateFlow()
    }

    val actionsFlow: StateFlow<List<ScheduledDeviceAction>>
        get() = _globalActionsFlow.asStateFlow()

    private val prefs: SharedPreferences? =
        context?.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ ->
        val updated = readAllFromPrefs()
        _globalActionsFlow.value = updated
        Log.d(TAG, "[storage] Preference change detected -> ${updated.size} actions in storage")
    }

    init {
        prefs?.registerOnSharedPreferenceChangeListener(prefListener)
        val initial = readAllFromPrefs()
        if (_globalActionsFlow.value.isEmpty() && initial.isNotEmpty()) {
            _globalActionsFlow.value = initial
        }
    }

    private fun readAllFromPrefs(): List<ScheduledDeviceAction> {
        val p = prefs ?: return emptyList()
        val list = mutableListOf<ScheduledDeviceAction>()
        p.all.forEach { (key, value) ->
            if (value is String) {
                val action = ScheduledDeviceAction.fromJson(value)
                if (action != null) {
                    list.add(action)
                }
            }
        }
        return list.sortedBy { it.scheduledExecutionTimeMillis }
    }

    @Synchronized
    open fun saveAction(action: ScheduledDeviceAction) {
        _globalActionsFlow.update { current ->
            val mutable = current.toMutableList()
            val index = mutable.indexOfFirst { it.id == action.id }
            if (index >= 0) {
                mutable[index] = action
            } else {
                mutable.add(action)
            }
            mutable.sortedBy { it.scheduledExecutionTimeMillis }
        }

        prefs?.edit()?.putString(action.id, action.toJson())?.apply()
        Log.i(TAG, "[storage] Saved action ${action.id} (${action.targetDeviceType} -> ${action.actionType}, Status: ${action.status})")

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.PERSISTED,
            message = "id=${action.id}, target=${action.targetDeviceType}, action=${action.actionType}, status=${action.status}"
        )
    }

    @Synchronized
    open fun getAction(id: String): ScheduledDeviceAction? {
        return _globalActionsFlow.value.firstOrNull { it.id == id } ?: run {
            val jsonStr = prefs?.getString(id, null) ?: return null
            ScheduledDeviceAction.fromJson(jsonStr)
        }
    }

    @Synchronized
    open fun getActiveActions(): List<ScheduledDeviceAction> {
        return _globalActionsFlow.value.filter { it.isPending }
    }

    @Synchronized
    open fun getActiveActionForDevice(deviceType: DeviceType): ScheduledDeviceAction? {
        return _globalActionsFlow.value.firstOrNull { it.targetDeviceType == deviceType && it.isPending }
    }

    @Synchronized
    open fun updateStatus(id: String, status: ScheduledActionStatus, failureReason: String? = null): ScheduledDeviceAction? {
        val existing = getAction(id) ?: return null
        val updated = existing.copy(status = status, failureReason = failureReason)
        saveAction(updated)
        return updated
    }

    @Synchronized
    open fun cancelAction(id: String): ScheduledDeviceAction? {
        val existing = getAction(id) ?: return null
        val updated = existing.copy(status = ScheduledActionStatus.CANCELLED)
        saveAction(updated)
        Log.i(TAG, "[storage] Cancelled scheduled action $id")
        return updated
    }

    @Synchronized
    open fun cancelActionsForDevice(deviceType: DeviceType): List<ScheduledDeviceAction> {
        val active = _globalActionsFlow.value.filter { it.targetDeviceType == deviceType && it.isPending }
        active.forEach { action ->
            cancelAction(action.id)
        }
        return active
    }

    @Synchronized
    open fun deleteAction(id: String) {
        _globalActionsFlow.update { current ->
            current.filterNot { it.id == id }
        }
        prefs?.edit()?.remove(id)?.apply()
        Log.i(TAG, "[storage] Deleted action $id")
    }

    @Synchronized
    open fun clear() {
        _globalActionsFlow.value = emptyList()
        prefs?.edit()?.clear()?.apply()
    }
}
