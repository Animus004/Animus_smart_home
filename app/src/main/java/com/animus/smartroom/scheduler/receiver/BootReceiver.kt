package com.animus.smartroom.scheduler.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.animus.smartroom.scheduler.DeviceSchedulerEngine

class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.i(TAG, "[boot] Received broadcast: $action")

        if (action == Intent.ACTION_BOOT_COMPLETED ||
            action == Intent.ACTION_LOCKED_BOOT_COMPLETED ||
            action == "android.intent.action.QUICKBOOT_POWERON"
        ) {
            Log.i(TAG, "[boot] Restoring pending scheduled device actions...")
            val engine = (context.applicationContext as? com.animus.smartroom.AnimusApplication)?.deviceSchedulerEngine
                ?: DeviceSchedulerEngine(
                    storage = com.animus.smartroom.scheduler.storage.ScheduledActionStorage(com.animus.smartroom.core.port.AndroidPersistentStore(context, com.animus.smartroom.scheduler.storage.ScheduledActionStorage.PREFS_NAME)),
                    clock = com.animus.smartroom.core.port.AndroidClock(),
                    platformScheduler = com.animus.smartroom.core.port.AndroidAlarmManagerScheduler(context)
                )
            engine.restorePersistedActions()
        }
    }
}
