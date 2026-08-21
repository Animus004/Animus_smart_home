package com.animus.smartroom.overlay.storage

import android.content.Context
import android.content.SharedPreferences
import android.graphics.Point

/**
 * Persists and restores floating overlay screen coordinates.
 * Clamps coordinates within visible screen bounds to prevent off-screen positioning.
 */
class OverlayPositionStorage(
    private val context: Context,
    private val prefs: SharedPreferences = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
) {

    companion object {
        private const val PREF_NAME = "animus_overlay_position"
        const val KEY_POS_X = "animus_overlay_x"
        const val KEY_POS_Y = "animus_overlay_y"
        const val DEFAULT_X = 100
        const val DEFAULT_Y = 200

        fun clampStatic(
            x: Int,
            y: Int,
            screenWidth: Int,
            screenHeight: Int,
            overlayWidth: Int,
            overlayHeight: Int
        ): Pair<Int, Int> {
            val maxX = (screenWidth - overlayWidth).coerceAtLeast(0)
            val maxY = (screenHeight - overlayHeight).coerceAtLeast(0)

            val clampedX = x.coerceIn(0, maxX)
            val clampedY = y.coerceIn(0, maxY)
            return Pair(clampedX, clampedY)
        }
    }

    /**
     * Get saved overlay position, clamped to [screenWidth] and [screenHeight].
     */
    fun getPosition(
        screenWidth: Int = 1080,
        screenHeight: Int = 2400,
        overlayWidth: Int = 150,
        overlayHeight: Int = 150
    ): Point {
        val rawX = prefs.getInt(KEY_POS_X, DEFAULT_X)
        val rawY = prefs.getInt(KEY_POS_Y, DEFAULT_Y)

        val clamped = clamp(rawX, rawY, screenWidth, screenHeight, overlayWidth, overlayHeight)
        return Point(clamped.first, clamped.second)
    }

    /**
     * Save overlay position after user drags.
     */
    fun savePosition(
        x: Int,
        y: Int,
        screenWidth: Int = 1080,
        screenHeight: Int = 2400,
        overlayWidth: Int = 150,
        overlayHeight: Int = 150
    ) {
        val (clampedX, clampedY) = clamp(x, y, screenWidth, screenHeight, overlayWidth, overlayHeight)
        prefs.edit()
            .putInt(KEY_POS_X, clampedX)
            .putInt(KEY_POS_Y, clampedY)
            .apply()
    }

    /**
     * Pure function to clamp coordinates within bounding box.
     */
    fun clamp(
        x: Int,
        y: Int,
        screenWidth: Int,
        screenHeight: Int,
        overlayWidth: Int,
        overlayHeight: Int
    ): Pair<Int, Int> {
        val maxX = (screenWidth - overlayWidth).coerceAtLeast(0)
        val maxY = (screenHeight - overlayHeight).coerceAtLeast(0)

        val clampedX = x.coerceIn(0, maxX)
        val clampedY = y.coerceIn(0, maxY)
        return Pair(clampedX, clampedY)
    }
}
