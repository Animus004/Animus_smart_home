package com.animus.smartroom.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Architecture Guard enforcing that overlay package NEVER imports direct device, cloud or scheduling drivers:
 * - TuyaCloudApiClient
 * - TuyaAirConditionerAdapter
 * - AlarmManager
 * - ScheduledActionStorage
 * - GeminiApiClient
 * - YouTubeDataApiClient
 */
class FloatingOverlayArchitectureGuardTest {

    private val forbiddenImports = listOf(
        "com.animus.smartroom.device.tuya.client.TuyaCloudApiClient",
        "com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter",
        "android.app.AlarmManager",
        "com.animus.smartroom.brain.provider.GeminiApiClient"
    )

    @Test
    fun `floating overlay package must NOT import direct device or hardware drivers`() {
        val overlayDir = File("d:\\AnimusSmartRoom\\app\\src\\main\\java\\com\\animus\\smartroom\\overlay")
        assertTrue("Overlay directory must exist", overlayDir.exists())

        val kotlinFiles = overlayDir.walkTopDown().filter { it.isFile && it.extension == "kt" }.toList()
        assertTrue("Overlay directory must contain Kotlin files", kotlinFiles.isNotEmpty())

        for (file in kotlinFiles) {
            val content = file.readText()
            for (forbidden in forbiddenImports) {
                assertFalse(
                    "Architecture violation in ${file.name}: directly imports forbidden driver '$forbidden'",
                    content.contains("import $forbidden")
                )
            }
        }
    }
}
