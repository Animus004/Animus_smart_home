package com.animus.smartroom.ui.glass

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

object GlassTokens {
    // Deep Space Backgrounds
    val BackgroundDeep = Color(0xFF050811)
    val BackgroundDark = Color(0xFF090E1A)
    val BackgroundSurface = Color(0xFF0E1526)

    // Glass Translucent Surfaces
    val GlassSurface = Color(0xFF131D31).copy(alpha = 0.65f)
    val GlassSurfaceHover = Color(0xFF1B2844).copy(alpha = 0.75f)
    val GlassSurfaceLight = Color(0xFF23355A).copy(alpha = 0.45f)
    val GlassSurfaceUltraLight = Color(0xFFFFFFFF).copy(alpha = 0.06f)

    // Accent Colors
    val AccentGreen = Color(0xFF22C55E)
    val AccentYellow = Color(0xFFEAB308)
    val AccentBlue = Color(0xFF38BDF8)
    val AccentCyan = Color(0xFF06B6D4)
    val AccentRed = Color(0xFFEF4444)
    val AccentPurple = Color(0xFFA855F7)
    val AccentIndigo = Color(0xFF6366F1)

    // Glass Borders & Outlines
    val BorderLight = Color(0xFFFFFFFF).copy(alpha = 0.12f)
    val BorderGlow = Color(0xFF38BDF8).copy(alpha = 0.35f)

    fun glassBorder(accentColor: Color? = null): BorderStroke {
        return BorderStroke(
            width = 1.dp,
            brush = if (accentColor != null) {
                Brush.linearGradient(
                    listOf(
                        accentColor.copy(alpha = 0.55f),
                        accentColor.copy(alpha = 0.15f)
                    )
                )
            } else {
                Brush.linearGradient(
                    listOf(
                        Color(0xFFFFFFFF).copy(alpha = 0.18f),
                        Color(0xFFFFFFFF).copy(alpha = 0.05f)
                    )
                )
            }
        )
    }

    // Geometry
    val CornerRadiusSmall = RoundedCornerShape(12.dp)
    val CornerRadiusMedium = RoundedCornerShape(20.dp)
    val CornerRadiusLarge = RoundedCornerShape(28.dp)
    val CornerRadiusFull = RoundedCornerShape(999.dp)
}
