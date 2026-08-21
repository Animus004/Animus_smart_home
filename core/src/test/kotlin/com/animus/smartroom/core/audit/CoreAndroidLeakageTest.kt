package com.animus.smartroom.core.audit

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Architectural guard test ensuring ZERO Android framework dependencies enter the :core module.
 */
class CoreAndroidLeakageTest {

    private val forbiddenPatterns = listOf(
        "import android.",
        "import androidx.",
        "import com.google.android.",
        "android.content.Context",
        "android.content.Intent",
        "android.app.Activity",
        "android.app.AlarmManager",
        "android.content.SharedPreferences",
        "android.content.BroadcastReceiver",
        "android.bluetooth.BluetoothAdapter",
        "android.media.MediaPlayer"
    )

    @Test
    fun `Verify zero Android framework dependencies in core main source files`() {
        val coreSrcDir = File("src/main/kotlin")
        assertTrue("Core source directory must exist", coreSrcDir.exists())

        val violations = mutableListOf<String>()

        coreSrcDir.walkTopDown().filter { it.isFile && it.extension == "kt" }.forEach { file ->
            val lines = file.readLines()
            lines.forEachIndexed { index, line ->
                val trimmed = line.trim()
                forbiddenPatterns.forEach { forbidden ->
                    if (trimmed.startsWith(forbidden) || trimmed.contains(forbidden)) {
                        violations.add("${file.relativeTo(coreSrcDir).path}:${index + 1} -> '$trimmed'")
                    }
                }
            }
        }

        assertTrue(
            "Found forbidden Android dependencies in :core module:\n${violations.joinToString("\n")}",
            violations.isEmpty()
        )
    }
}
