package com.animus.smartroom.core.port

/**
 * Pure JVM port for querying system overlay permission status.
 * Implemented on Android by AndroidOverlayPermissionPort.
 */
interface OverlayPermissionPort {
    /**
     * Returns true if the app currently has permission to draw system overlays (floating windows).
     */
    fun canDrawOverlays(): Boolean
}
