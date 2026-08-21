package com.animus.smartroom.ui.diagnostics

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.diagnostics.DiagnosticEvent
import com.animus.smartroom.diagnostics.DiagnosticStage

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticLogSheet(
    events: List<DiagnosticEvent>,
    onDismiss: () -> Unit,
    onClear: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Color(0xFF0B1120),
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        dragHandle = {
            BottomSheetDefaults.DragHandle(color = Color(0xFF475569))
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .padding(horizontal = 20.dp, vertical = 8.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "SYSTEM DIAGNOSTICS",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        color = Color(0xFF94A3B8)
                    )
                    Text(
                        text = "Live State-by-State Event Bus",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                }

                IconButton(onClick = onClear) {
                    Icon(
                        imageVector = Icons.Default.DeleteOutline,
                        contentDescription = "Clear logs",
                        tint = Color(0xFF94A3B8)
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            if (events.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No diagnostic events recorded yet.",
                        fontSize = 13.sp,
                        color = Color(0xFF64748B)
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    contentPadding = PaddingValues(bottom = 24.dp)
                ) {
                    // Show most recent events at top
                    items(events.reversed()) { event ->
                        DiagnosticEventRow(event)
                    }
                }
            }
        }
    }
}

@Composable
private fun DiagnosticEventRow(event: DiagnosticEvent) {
    val stageColor = when (event.stage) {
        DiagnosticStage.COMPLETED -> Color(0xFF10B981)
        DiagnosticStage.FAILED -> Color(0xFFEF4444)
        DiagnosticStage.EXECUTING, DiagnosticStage.DEVICE_RESPONSE -> Color(0xFF38BDF8)
        DiagnosticStage.ALARM, DiagnosticStage.TRIGGERED -> Color(0xFFF59E0B)
        DiagnosticStage.REQUESTED, DiagnosticStage.VALIDATING -> Color(0xFFA78BFA)
        else -> Color(0xFF94A3B8)
    }

    Surface(
        color = Color(0xFF1E293B),
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, Color(0xFF334155).copy(alpha = 0.6f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.Top
        ) {
            Text(
                text = event.formattedTime,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = Color(0xFF64748B),
                modifier = Modifier.padding(top = 2.dp)
            )

            Spacer(modifier = Modifier.width(8.dp))

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(stageColor.copy(alpha = 0.18f))
                    .padding(horizontal = 6.dp, vertical = 2.dp)
            ) {
                Text(
                    text = "${event.tag.uppercase()} • ${event.stage.name}",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = stageColor
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            Text(
                text = event.message,
                fontSize = 12.sp,
                color = Color.White,
                modifier = Modifier.weight(1f)
            )
        }
    }
}
