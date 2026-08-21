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
            val engine = DeviceSchedulerEngine(context)
            engine.restorePersistedActions()
        }
    }
}
