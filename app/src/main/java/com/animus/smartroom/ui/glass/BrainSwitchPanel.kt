package com.animus.smartroom.ui.glass

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.brain.model.BrainProviderType

enum class OperationMode(val displayName: String, val subtitle: String) {
    LOCAL_ROOM("Local Room Mode", "Connected to physical smart room hardware (AC, Projector, Soundbar, Fire TV)"),
    REMOTE("Remote Mode", "Away mode: Room hardware disabled. Music, portable audio & Gemini search active")
}

@Composable
fun BrainSwitchPanel(
    currentOperationMode: OperationMode,
    onSetOperationMode: (OperationMode) -> Unit,
    activeBrainProvider: BrainProviderType,
    onSetBrainProvider: (BrainProviderType) -> Unit,
    maskedApiKey: String?,
    onSaveApiKey: (String?) -> Unit,
    onTestApiKey: (String?, (Boolean, String) -> Unit) -> Unit,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    var apiKeyInput by remember { mutableStateOf("") }
    var testResultMsg by remember { mutableStateOf<String?>(null) }
    var isTesting by remember { mutableStateOf(false) }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentGreen)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState())
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
                            .background(GlassTokens.AccentGreen.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Psychology,
                            contentDescription = "Brain Switch",
                            tint = GlassTokens.AccentGreen,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Brain & Operation Mode",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Environment & Neural Provider Settings",
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

            // SECTION 1: OPERATION ENVIRONMENT MODE
            Text(
                text = "OPERATION ENVIRONMENT",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))

            OperationModeCard(
                mode = OperationMode.LOCAL_ROOM,
                isSelected = currentOperationMode == OperationMode.LOCAL_ROOM,
                icon = Icons.Default.Home,
                onClick = { onSetOperationMode(OperationMode.LOCAL_ROOM) }
            )

            Spacer(modifier = Modifier.height(10.dp))

            OperationModeCard(
                mode = OperationMode.REMOTE,
                isSelected = currentOperationMode == OperationMode.REMOTE,
                icon = Icons.Default.FlightTakeoff,
                onClick = { onSetOperationMode(OperationMode.REMOTE) }
            )

            Spacer(modifier = Modifier.height(24.dp))

            // SECTION 2: AI BRAIN PROVIDER
            Text(
                text = "COMMAND INTERPRETER PROVIDER",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Local Qwen Option
                val isLocal = activeBrainProvider == BrainProviderType.LOCAL
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(GlassTokens.CornerRadiusMedium)
                        .background(
                            if (isLocal) GlassTokens.AccentGreen.copy(alpha = 0.2f)
                            else GlassTokens.GlassSurface
                        )
                        .border(
                            1.dp,
                            if (isLocal) GlassTokens.AccentGreen else GlassTokens.BorderLight,
                            GlassTokens.CornerRadiusMedium
                        )
                        .clickable { onSetBrainProvider(BrainProviderType.LOCAL) }
                        .padding(14.dp)
                ) {
                    Column {
                        Icon(
                            imageVector = Icons.Default.Memory,
                            contentDescription = "Local Ollama",
                            tint = if (isLocal) GlassTokens.AccentGreen else Color.White.copy(alpha = 0.6f),
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Local Qwen 2.5 / 3",
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Ollama on PC / Device",
                            color = Color.White.copy(alpha = 0.6f),
                            fontSize = 11.sp
                        )
                    }
                }

                // Gemini Cloud Option
                val isGemini = activeBrainProvider == BrainProviderType.GEMINI
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(GlassTokens.CornerRadiusMedium)
                        .background(
                            if (isGemini) GlassTokens.AccentCyan.copy(alpha = 0.2f)
                            else GlassTokens.GlassSurface
                        )
                        .border(
                            1.dp,
                            if (isGemini) GlassTokens.AccentCyan else GlassTokens.BorderLight,
                            GlassTokens.CornerRadiusMedium
                        )
                        .clickable { onSetBrainProvider(BrainProviderType.GEMINI) }
                        .padding(14.dp)
                ) {
                    Column {
                        Icon(
                            imageVector = Icons.Default.Cloud,
                            contentDescription = "Gemini Cloud",
                            tint = if (isGemini) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.6f),
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Gemini Cloud 1.5",
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Google AI Studio API",
                            color = Color.White.copy(alpha = 0.6f),
                            fontSize = 11.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // SECTION 3: GEMINI API KEY CONFIGURATION
            Text(
                text = "GEMINI KNOWLEDGE BRIDGE API KEY",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))

            if (!maskedApiKey.isNullOrBlank()) {
                Text(
                    text = "Saved Key: $maskedApiKey",
                    color = GlassTokens.AccentCyan,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(6.dp))
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(GlassTokens.CornerRadiusMedium)
                    .background(GlassTokens.GlassSurface)
                    .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                    .padding(horizontal = 12.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextField(
                    value = apiKeyInput,
                    onValueChange = { apiKeyInput = it },
                    placeholder = {
                        Text("Paste Gemini API key...", color = Color.White.copy(alpha = 0.35f), fontSize = 12.sp)
                    },
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        disabledContainerColor = Color.Transparent,
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        cursorColor = GlassTokens.AccentCyan,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent
                    ),
                    modifier = Modifier.weight(1f)
                )

                TextButton(
                    onClick = {
                        val key = apiKeyInput.trim().ifBlank { null }
                        onSaveApiKey(key)
                        apiKeyInput = ""
                    },
                    enabled = apiKeyInput.isNotBlank()
                ) {
                    Text("Save", color = GlassTokens.AccentCyan, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        isTesting = true
                        testResultMsg = "Testing..."
                        onTestApiKey(null) { success, msg ->
                            isTesting = false
                            testResultMsg = msg
                        }
                    },
                    enabled = !isTesting,
                    shape = GlassTokens.CornerRadiusMedium,
                    border = GlassTokens.glassBorder(GlassTokens.AccentCyan),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = GlassTokens.AccentCyan),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Test Connection", fontSize = 11.5.sp)
                }

                if (!maskedApiKey.isNullOrBlank()) {
                    OutlinedButton(
                        onClick = { onSaveApiKey(null) },
                        shape = GlassTokens.CornerRadiusMedium,
                        border = GlassTokens.glassBorder(GlassTokens.AccentRed),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = GlassTokens.AccentRed),
                        modifier = Modifier.weight(0.7f)
                    ) {
                        Text("Clear Key", fontSize = 11.5.sp)
                    }
                }
            }

            if (testResultMsg != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = testResultMsg ?: "",
                    color = if (testResultMsg?.contains("successful") == true) GlassTokens.AccentGreen else GlassTokens.AccentRed,
                    fontSize = 11.5.sp
                )
            }
        }
    }
}

@Composable
private fun OperationModeCard(
    mode: OperationMode,
    isSelected: Boolean,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit
) {
    val accentColor = if (mode == OperationMode.LOCAL_ROOM) GlassTokens.AccentGreen else GlassTokens.AccentPurple

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(GlassTokens.CornerRadiusMedium)
            .background(
                if (isSelected) accentColor.copy(alpha = 0.22f)
                else GlassTokens.GlassSurface
            )
            .border(
                width = 1.dp,
                color = if (isSelected) accentColor else GlassTokens.BorderLight,
                shape = GlassTokens.CornerRadiusMedium
            )
            .clickable { onClick() }
            .padding(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = mode.displayName,
                tint = if (isSelected) accentColor else Color.White.copy(alpha = 0.5f),
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = mode.displayName,
                        color = Color.White,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                    if (isSelected) {
                        Text(
                            text = "ACTIVE",
                            color = accentColor,
                            fontSize = 10.5.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = mode.subtitle,
                    color = Color.White.copy(alpha = 0.65f),
                    fontSize = 11.5.sp
                )
            }
        }
    }
}
