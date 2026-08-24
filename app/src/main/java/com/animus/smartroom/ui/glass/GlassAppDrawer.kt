package com.animus.smartroom.ui.glass

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp

enum class ActiveGlassTool {
    NONE,
    DEVICE_STATUS,
    AC_REMOTE,
    MUSIC_CONTROLLER,
    CHAT,
    AUTOMATIONS,
    WIDGET_TOGGLE,
    BRAIN_SWITCH
}

@Composable
fun GlassAppDrawer(
    activeTool: ActiveGlassTool,
    onSelectTool: (ActiveGlassTool) -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxWidth(0.94f)
            .clip(GlassTokens.CornerRadiusFull)
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        GlassTokens.GlassSurfaceHover,
                        GlassTokens.GlassSurface
                    )
                )
            )
            .border(
                width = 1.dp,
                brush = Brush.horizontalGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.25f),
                        Color.White.copy(alpha = 0.08f),
                        Color.White.copy(alpha = 0.25f)
                    )
                ),
                shape = GlassTokens.CornerRadiusFull
            )
            .padding(horizontal = 14.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            ToolDockButton(
                icon = Icons.Default.Sensors,
                contentDescription = "Device Status",
                isActive = activeTool == ActiveGlassTool.DEVICE_STATUS,
                accentColor = GlassTokens.AccentBlue,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.DEVICE_STATUS) ActiveGlassTool.NONE else ActiveGlassTool.DEVICE_STATUS) }
            )

            ToolDockButton(
                icon = Icons.Default.AcUnit,
                contentDescription = "AC Remote",
                isActive = activeTool == ActiveGlassTool.AC_REMOTE,
                accentColor = GlassTokens.AccentCyan,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.AC_REMOTE) ActiveGlassTool.NONE else ActiveGlassTool.AC_REMOTE) }
            )

            ToolDockButton(
                icon = Icons.Default.MusicNote,
                contentDescription = "Music Controller",
                isActive = activeTool == ActiveGlassTool.MUSIC_CONTROLLER,
                accentColor = GlassTokens.AccentPurple,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.MUSIC_CONTROLLER) ActiveGlassTool.NONE else ActiveGlassTool.MUSIC_CONTROLLER) }
            )

            ToolDockButton(
                icon = Icons.Default.Forum,
                contentDescription = "Chat",
                isActive = activeTool == ActiveGlassTool.CHAT,
                accentColor = GlassTokens.AccentBlue,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.CHAT) ActiveGlassTool.NONE else ActiveGlassTool.CHAT) }
            )

            ToolDockButton(
                icon = Icons.Default.Schedule,
                contentDescription = "Automations",
                isActive = activeTool == ActiveGlassTool.AUTOMATIONS,
                accentColor = GlassTokens.AccentYellow,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.AUTOMATIONS) ActiveGlassTool.NONE else ActiveGlassTool.AUTOMATIONS) }
            )

            ToolDockButton(
                icon = Icons.Default.Widgets,
                contentDescription = "Widget Toggle",
                isActive = activeTool == ActiveGlassTool.WIDGET_TOGGLE,
                accentColor = GlassTokens.AccentIndigo,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.WIDGET_TOGGLE) ActiveGlassTool.NONE else ActiveGlassTool.WIDGET_TOGGLE) }
            )

            ToolDockButton(
                icon = Icons.Default.Psychology,
                contentDescription = "Brain Switch",
                isActive = activeTool == ActiveGlassTool.BRAIN_SWITCH,
                accentColor = GlassTokens.AccentGreen,
                onClick = { onSelectTool(if (activeTool == ActiveGlassTool.BRAIN_SWITCH) ActiveGlassTool.NONE else ActiveGlassTool.BRAIN_SWITCH) }
            )
        }
    }
}

@Composable
private fun ToolDockButton(
    icon: ImageVector,
    contentDescription: String,
    isActive: Boolean,
    accentColor: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .size(42.dp)
            .clip(CircleShape)
            .background(
                if (isActive) accentColor.copy(alpha = 0.28f)
                else Color.Transparent
            )
            .border(
                width = if (isActive) 1.dp else 0.dp,
                color = if (isActive) accentColor else Color.Transparent,
                shape = CircleShape
            )
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = if (isActive) accentColor else Color.White.copy(alpha = 0.75f),
            modifier = Modifier.size(22.dp)
        )
    }
}
