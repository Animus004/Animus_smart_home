package com.animus.smartroom.ui.glass

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class WidgetSettings(
    val showClock: Boolean = true,
    val showRoomWeather: Boolean = true,
    val showQuickMusic: Boolean = true,
    val showDeviceTelemetry: Boolean = false
)

@Composable
fun WidgetTogglePanel(
    widgetSettings: WidgetSettings,
    onToggleClock: (Boolean) -> Unit,
    onToggleWeather: (Boolean) -> Unit,
    onToggleMusic: (Boolean) -> Unit,
    onToggleTelemetry: (Boolean) -> Unit,
    onToggleFloatingOverlay: () -> Unit,
    isFloatingOverlayRunning: Boolean,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentIndigo)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(GlassTokens.CornerRadiusSmall)
                            .background(GlassTokens.AccentIndigo.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Widgets,
                            contentDescription = "Widgets",
                            tint = GlassTokens.AccentIndigo,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Canvas Widget Toggles",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Customizable Ambient Surface Elements",
                            color = Color.White.copy(alpha = 0.6f),
                            fontSize = 11.5.sp
                        )
                    }
                }

                IconButton(onClick = onClose) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Color.White.copy(alpha = 0.7f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            WidgetToggleRow(
                title = "Ambient Time & Date",
                description = "Displays the current time and day in a minimal translucent style",
                icon = Icons.Default.AccessTime,
                checked = widgetSettings.showClock,
                onCheckedChange = onToggleClock
            )

            Spacer(modifier = Modifier.height(12.dp))

            WidgetToggleRow(
                title = "Room Climate Widget",
                description = "Shows live AC setpoint and room temperature indicator",
                icon = Icons.Default.Thermostat,
                checked = widgetSettings.showRoomWeather,
                onCheckedChange = onToggleWeather
            )

            Spacer(modifier = Modifier.height(12.dp))

            WidgetToggleRow(
                title = "Quick Music Mini-Player",
                description = "Shows current track and play/pause button at the bottom of the canvas",
                icon = Icons.Default.MusicNote,
                checked = widgetSettings.showQuickMusic,
                onCheckedChange = onToggleMusic
            )

            Spacer(modifier = Modifier.height(12.dp))

            WidgetToggleRow(
                title = "Hardware Telemetry Pill",
                description = "Displays live connection badges for Soundbar, Projector & Fire TV",
                icon = Icons.Default.Sensors,
                checked = widgetSettings.showDeviceTelemetry,
                onCheckedChange = onToggleTelemetry
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Floating System Overlay Service
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(GlassTokens.CornerRadiusMedium)
                    .background(GlassTokens.AccentPurple.copy(alpha = 0.12f))
                    .border(1.dp, GlassTokens.AccentPurple.copy(alpha = 0.35f), GlassTokens.CornerRadiusMedium)
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Floating System Control Ball",
                            color = Color.White,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "System-wide overlay accessible from any Android app",
                            color = Color.White.copy(alpha = 0.65f),
                            fontSize = 11.5.sp
                        )
                    }
                    Switch(
                        checked = isFloatingOverlayRunning,
                        onCheckedChange = { onToggleFloatingOverlay() },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color.White,
                            checkedTrackColor = GlassTokens.AccentPurple,
                            uncheckedThumbColor = Color.White.copy(alpha = 0.5f),
                            uncheckedTrackColor = GlassTokens.GlassSurface
                        )
                    )
                }
            }
        }
    }
}

@Composable
private fun WidgetToggleRow(
    title: String,
    description: String,
    icon: ImageVector,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(GlassTokens.CornerRadiusMedium)
            .background(GlassTokens.GlassSurface)
            .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
            .padding(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = title,
                    tint = if (checked) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.4f),
                    modifier = Modifier.size(22.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = title,
                        color = Color.White,
                        fontSize = 13.5.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = description,
                        color = Color.White.copy(alpha = 0.6f),
                        fontSize = 11.sp
                    )
                }
            }
            Switch(
                checked = checked,
                onCheckedChange = onCheckedChange,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = GlassTokens.AccentCyan,
                    uncheckedThumbColor = Color.White.copy(alpha = 0.5f),
                    uncheckedTrackColor = GlassTokens.GlassSurfaceLight
                )
            )
        }
    }
}
