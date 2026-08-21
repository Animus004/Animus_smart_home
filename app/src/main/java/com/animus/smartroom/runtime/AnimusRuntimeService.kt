package com.animus.smartroom.runtime

import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import com.animus.smartroom.AnimusApplication
import com.animus.smartroom.notification.AndroidNotificationAdapter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Android foreground service providing a persistent runtime anchor for Animus.
 *
 * Start policy: NOT started unconditionally from Application.onCreate().
 * Instead, started on-demand when Animus genuinely needs background capability:
 *  - When the user explicitly starts the runtime via AnimusApplication.startRuntime()
 *  - After a scheduled action fires (the receiver is self-contained via AlarmManager)
 *
 * AlarmManager + ScheduledDeviceActionReceiver remains the authoritative scheduler.
 * This service does NOT replace or duplicate scheduling logic.
 *
 * No Binder returned — MainActivity and other components communicate via the
 * AnimusApplication singleton bridge instead.
 */
class AnimusRuntimeService : Service() {

    companion object {
        private const val TAG = "AnimusRuntimeService"
        const val ACTION_START = "com.animus.smartroom.ACTION_RUNTIME_START"
        const val ACTION_STOP = "com.animus.smartroom.ACTION_RUNTIME_STOP"

        fun startIntent(context: Context): Intent =
            Intent(context, AnimusRuntimeService::class.java).apply { action = ACTION_START }

        fun stopIntent(context: Context): Intent =
            Intent(context, AnimusRuntimeService::class.java).apply { action = ACTION_STOP }
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "[service] onCreate")
        AndroidNotificationAdapter.createNotificationChannel(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                Log.i(TAG, "[service] Explicit stop requested")
                stopSelf()
                return START_NOT_STICKY
            }
            else -> {
                Log.i(TAG, "[service] Starting foreground runtime service")
                val notification = AndroidNotificationAdapter.buildRuntimeNotification(this)
                startForeground(AndroidNotificationAdapter.NOTIFICATION_ID_RUNTIME, notification)

                val app = application as? AnimusApplication
                app?.animusRuntime?.onStarted()

                // Observe structured action events and update notification
                serviceScope.launch {
                    com.animus.smartroom.diagnostics.DiagnosticBus.actionEvents.collectLatest { events ->
                        val latest = events.lastOrNull() ?: return@collectLatest
                        // Only update notification for terminal/completed events to avoid spam
                        if (latest.stage == com.animus.smartroom.core.diagnostics.model.ActionStage.COMPLETED ||
                            latest.stage == com.animus.smartroom.core.diagnostics.model.ActionStage.FAILED ||
                            latest.stage == com.animus.smartroom.core.diagnostics.model.ActionStage.CANCELLED) {
                            AndroidNotificationAdapter.updateNotification(this@AnimusRuntimeService, latest)
                        }
                    }
                }

                // Observe active scheduler action count to sync runtime state
                serviceScope.launch {
                    app?.scheduledActionStorage?.actionsFlow?.collectLatest { actions ->
                        val activeCount = actions.count {
                            it.status == com.animus.smartroom.scheduler.model.ScheduledActionStatus.SCHEDULED ||
                            it.status == com.animus.smartroom.scheduler.model.ScheduledActionStatus.EXECUTING
                        }
                        (app.animusRuntime as? AnimusRuntimeImpl)?.syncActiveActionCount(activeCount)
                    }
                }
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "[service] onDestroy")
        serviceScope.cancel()
        val app = application as? AnimusApplication
        app?.animusRuntime?.onStopped()
    }

    /** No binding — MainActivity uses AnimusApplication singleton bridge. */
    override fun onBind(intent: Intent?): IBinder? = null
}
