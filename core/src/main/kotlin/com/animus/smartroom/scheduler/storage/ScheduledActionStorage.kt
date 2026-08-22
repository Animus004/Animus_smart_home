package com.animus.smartroom.scheduler.storage

import com.animus.smartroom.core.port.PersistentStore
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

open class ScheduledActionStorage(
    private val store: PersistentStore
) {
    companion object {
        const val PREFS_NAME = "animus_scheduled_actions_prefs"
        private val _globalActionsFlow = MutableStateFlow<List<ScheduledDeviceAction>>(emptyList())
        val activeActionsFlow: StateFlow<List<ScheduledDeviceAction>> = _globalActionsFlow.asStateFlow()
    }

    val actionsFlow: StateFlow<List<ScheduledDeviceAction>>
        get() = _globalActionsFlow.asStateFlow()

    private val storeListener: (String) -> Unit = { _ ->
        val updated = readAllFromStore()
        _globalActionsFlow.value = updated
    }

    init {
        store.registerChangeListener(storeListener)
        val initial = readAllFromStore()
        if (_globalActionsFlow.value.isEmpty() && initial.isNotEmpty()) {
            _globalActionsFlow.value = initial
        }
    }

    private fun readAllFromStore(): List<ScheduledDeviceAction> {
        val list = mutableListOf<ScheduledDeviceAction>()
        store.getAll().forEach { (_, value) ->
            if (value is String) {
                val action = ScheduledDeviceAction.fromJson(value)
                if (action != null) {
                    list.add(action)
                }
            }
        }
        return list.sortedBy { it.scheduledExecutionTimeMillis }
    }

    open fun saveAction(action: ScheduledDeviceAction) {
        store.putString(action.id, action.toJson())
        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.PERSISTED,
            message = "id=${action.id}, target=${action.targetDeviceType}, action=${action.actionType}, status=${action.status}"
        )
        _globalActionsFlow.value = readAllFromStore()
    }

    open fun getAction(actionId: String): ScheduledDeviceAction? {
        val json = store.getString(actionId, null) ?: return null
        return ScheduledDeviceAction.fromJson(json)
    }

    open fun getAllActions(): List<ScheduledDeviceAction> {
        return readAllFromStore()
    }

    open fun getPendingActions(): List<ScheduledDeviceAction> {
        return readAllFromStore().filter { it.status == ScheduledActionStatus.SCHEDULED }
    }

    open fun getActiveActions(): List<ScheduledDeviceAction> {
        return getPendingActions()
    }

    open fun getPendingActionForDevice(deviceType: DeviceType): ScheduledDeviceAction? {
        return readAllFromStore().firstOrNull {
            it.targetDeviceType == deviceType && it.status == ScheduledActionStatus.SCHEDULED
        }
    }

    open fun getActiveActionForDevice(deviceType: DeviceType): ScheduledDeviceAction? {
        return getPendingActionForDevice(deviceType)
    }

    open fun updateStatus(actionId: String, newStatus: ScheduledActionStatus, failureReason: String? = null) {
        val action = getAction(actionId) ?: return
        val updated = action.copy(
            status = newStatus,
            failureReason = failureReason
        )
        saveAction(updated)
    }

    open fun cancelAction(actionId: String) {
        updateStatus(actionId, ScheduledActionStatus.CANCELLED)
        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "Cancelled action $actionId"
        )
    }

    open fun cancelActionsForDevice(deviceType: DeviceType): List<ScheduledDeviceAction> {
        val active = getPendingActions().filter { it.targetDeviceType == deviceType }
        active.forEach { action ->
            cancelAction(action.id)
        }
        return active
    }

    open fun deleteAction(actionId: String) {
        store.remove(actionId)
        _globalActionsFlow.value = readAllFromStore()
    }

    open fun clearAll() {
        store.getAll().keys.forEach { key ->
            store.remove(key)
        }
        _globalActionsFlow.value = emptyList()
    }

    open fun clear() {
        clearAll()
    }
}

