package com.animus.smartroom.ui.glass

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Print
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.UUID

data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val isUser: Boolean,
    val text: String,
    val timestamp: Long = System.currentTimeMillis()
)

@Composable
fun GlassChatPanel(
    chatHistory: List<ChatMessage>,
    onSendMessage: (String) -> Unit,
    onClose: () -> Unit,
    onPrintFileRequested: ((filename: String, bytes: ByteArray) -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    var selectedFileName by remember { mutableStateOf<String?>(null) }
    var selectedFileBytes by remember { mutableStateOf<ByteArray?>(null) }

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            var name = "document"
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex >= 0 && cursor.moveToFirst()) {
                    name = cursor.getString(nameIndex)
                }
            }
            selectedFileName = name
            try {
                selectedFileBytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            } catch (e: Exception) {
                selectedFileBytes = null
            }
        }
    }

    LaunchedEffect(chatHistory.size) {
        if (chatHistory.isNotEmpty()) {
            listState.animateScrollToItem(chatHistory.size - 1)
        }
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentBlue)
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
                            .background(GlassTokens.AccentBlue.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Forum,
                            contentDescription = "Chat",
                            tint = GlassTokens.AccentBlue,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Animus Conversation",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Conversational Room Intelligence",
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

            Spacer(modifier = Modifier.height(14.dp))

            // Chat Messages List
            LazyColumn(
                state = listState,
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                if (chatHistory.isEmpty()) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 40.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "Ask anything or command your smart room naturally.",
                                color = Color.White.copy(alpha = 0.45f),
                                fontSize = 13.sp
                            )
                        }
                    }
                } else {
                    items(chatHistory, key = { it.id }) { msg ->
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = if (msg.isUser) Alignment.CenterEnd else Alignment.CenterStart
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth(0.82f)
                                    .clip(
                                        RoundedCornerShape(
                                            topStart = 16.dp,
                                            topEnd = 16.dp,
                                            bottomStart = if (msg.isUser) 16.dp else 4.dp,
                                            bottomEnd = if (msg.isUser) 4.dp else 16.dp
                                        )
                                    )
                                    .background(
                                        if (msg.isUser) {
                                            Brush.horizontalGradient(
                                                listOf(
                                                    GlassTokens.AccentBlue.copy(alpha = 0.35f),
                                                    GlassTokens.AccentPurple.copy(alpha = 0.35f)
                                                )
                                            )
                                        } else {
                                            Brush.horizontalGradient(
                                                listOf(
                                                    GlassTokens.GlassSurfaceLight,
                                                    GlassTokens.GlassSurface
                                                )
                                            )
                                        }
                                    )
                                    .border(
                                        width = 1.dp,
                                        color = if (msg.isUser) GlassTokens.AccentBlue.copy(alpha = 0.45f) else GlassTokens.BorderLight,
                                        shape = RoundedCornerShape(
                                            topStart = 16.dp,
                                            topEnd = 16.dp,
                                            bottomStart = if (msg.isUser) 16.dp else 4.dp,
                                            bottomEnd = if (msg.isUser) 4.dp else 16.dp
                                        )
                                    )
                                    .padding(horizontal = 14.dp, vertical = 10.dp)
                            ) {
                                Text(
                                    text = msg.text,
                                    color = Color.White.copy(alpha = 0.95f),
                                    fontSize = 13.5.sp,
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Attachment Preview Chip (if a file is selected)
            if (selectedFileName != null && selectedFileBytes != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(GlassTokens.CornerRadiusSmall)
                        .background(GlassTokens.AccentBlue.copy(alpha = 0.15f))
                        .border(1.dp, GlassTokens.AccentBlue.copy(alpha = 0.4f), GlassTokens.CornerRadiusSmall)
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(
                            imageVector = Icons.Default.AttachFile,
                            contentDescription = "Attached File",
                            tint = GlassTokens.AccentBlue,
                            modifier = Modifier.size(16.dp)
                        )
                        Text(
                            text = "${selectedFileName} (${selectedFileBytes!!.size / 1024} KB)",
                            color = Color.White,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 1
                        )
                    }

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Button(
                            onClick = {
                                val name = selectedFileName ?: "document"
                                val bytes = selectedFileBytes ?: byteArrayOf()
                                if (onPrintFileRequested != null) {
                                    onPrintFileRequested(name, bytes)
                                } else {
                                    onSendMessage("Print file '$name' on HP Ink Tank 310")
                                }
                                selectedFileName = null
                                selectedFileBytes = null
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = GlassTokens.AccentBlue),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp),
                            modifier = Modifier.height(28.dp),
                            shape = GlassTokens.CornerRadiusSmall
                        ) {
                            Icon(
                                imageVector = Icons.Default.Print,
                                contentDescription = "Print",
                                tint = Color.White,
                                modifier = Modifier.size(13.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(text = "Print to HP 310", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }

                        IconButton(
                            onClick = {
                                selectedFileName = null
                                selectedFileBytes = null
                            },
                            modifier = Modifier.size(26.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Remove File",
                                tint = Color.White.copy(alpha = 0.6f),
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
            }

            // Input Row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(GlassTokens.CornerRadiusMedium)
                    .background(GlassTokens.GlassSurface)
                    .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                    .padding(horizontal = 10.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { filePickerLauncher.launch("*/*") },
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.AttachFile,
                        contentDescription = "Attach File to Print",
                        tint = if (selectedFileName != null) GlassTokens.AccentBlue else Color.White.copy(alpha = 0.45f),
                        modifier = Modifier.size(19.dp)
                    )
                }

                TextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    placeholder = {
                        Text(
                            text = "Type message or command...",
                            color = Color.White.copy(alpha = 0.35f),
                            fontSize = 13.sp
                        )
                    },
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        disabledContainerColor = Color.Transparent,
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        cursorColor = GlassTokens.AccentBlue,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent
                    ),
                    modifier = Modifier.weight(1f)
                )

                IconButton(
                    onClick = {
                        val trimmed = inputText.trim()
                        if (trimmed.isNotBlank()) {
                            onSendMessage(trimmed)
                            inputText = ""
                        }
                    },
                    enabled = inputText.isNotBlank()
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (inputText.isNotBlank()) GlassTokens.AccentBlue else Color.White.copy(alpha = 0.2f),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }
    }
}
