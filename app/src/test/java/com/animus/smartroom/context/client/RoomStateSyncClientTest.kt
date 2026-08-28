package com.animus.smartroom.context.client

import com.animus.smartroom.context.model.RoomStateDto
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RoomStateSyncClientTest {

    @Test
    fun testRoomStateDtoParsing() {
        val jsonStr = """
            {
                "timestamp": 1724683000.0,
                "is_consistent": true,
                "projector": {
                    "power_state": "ON",
                    "input_source": "HDMI_1",
                    "brightness": 75,
                    "has_signal": true,
                    "is_connected": true
                },
                "ac": {
                    "power": true,
                    "target_temperature": 23,
                    "ambient_temperature": 26,
                    "hvac_mode": "COOL",
                    "fan_speed": "AUTO",
                    "is_online": true
                },
                "fire_tv": {
                    "power_state": "ON",
                    "current_app": "Netflix",
                    "playback_state": "PLAYING",
                    "soundbar_connected": true,
                    "is_online": true
                },
                "pc": {
                    "is_online": true,
                    "volume": 65,
                    "is_muted": false,
                    "active_endpoint": "LG SNC4R",
                    "soundbar_connected": false
                },
                "soundbar": {
                    "is_connected": true,
                    "connected_device": "FIRE_TV",
                    "power_state": "ON"
                },
                "environment": {
                    "mode": "MOVIE",
                    "active_audio_route": "FIRE_TV_A2DP"
                }
            }
        """.trimIndent()

        val json = JSONObject(jsonStr)
        val dto = RoomStateDto.fromJson(json)

        assertTrue(dto.isConsistent)
        assertEquals(1724683000.0, dto.timestamp, 0.001)

        // Projector
        assertEquals("ON", dto.projector.powerState)
        assertTrue(dto.projector.isPowerOn)
        assertEquals("HDMI_1", dto.projector.inputSource)
        assertEquals(75, dto.projector.brightness)
        assertTrue(dto.projector.hasSignal)
        assertTrue(dto.projector.isConnected)

        // AC
        assertTrue(dto.ac.power)
        assertEquals(23, dto.ac.targetTemperature)
        assertEquals(26, dto.ac.ambientTemperature)
        assertEquals("COOL", dto.ac.hvacMode)
        assertEquals("AUTO", dto.ac.fanSpeed)
        assertTrue(dto.ac.isOnline)

        // Fire TV
        assertEquals("ON", dto.fireTv.powerState)
        assertTrue(dto.fireTv.isPowerOn)
        assertEquals("Netflix", dto.fireTv.currentApp)
        assertEquals("PLAYING", dto.fireTv.playbackState)
        assertTrue(dto.fireTv.soundbarConnected)

        // Soundbar
        assertTrue(dto.soundbar.isConnected)
        assertEquals("FIRE_TV", dto.soundbar.connectedDevice)

        // Environment
        assertEquals("MOVIE", dto.environment.mode)
        assertEquals("FIRE_TV_A2DP", dto.environment.activeAudioRoute)
    }

    @Test
    fun testRoomStateDtoEmptyJsonDefaultsGracefully() {
        val json = JSONObject()
        val dto = RoomStateDto.fromJson(json)

        assertTrue(dto.isConsistent)
        assertEquals("UNKNOWN", dto.projector.powerState)
        assertFalse(dto.projector.isPowerOn)
        assertEquals("UNKNOWN", dto.fireTv.powerState)
        assertFalse(dto.ac.power)
        assertEquals(24, dto.ac.targetTemperature)
        assertEquals("DISCONNECTED", dto.soundbar.connectedDevice)
    }

    @Test
    fun testRoomStateDtoLiveProvenanceWrappedFormat() {
        val liveJsonStr = """
            {
                "timestamp": 1787758078.55,
                "is_consistent": true,
                "projector": {
                    "power": {"value": true, "provenance": "OBSERVED"},
                    "input_source": {"value": "HDMI_1", "provenance": "OBSERVED"},
                    "brightness": {"value": 40, "provenance": "OBSERVED"},
                    "signal_active": {"value": true, "provenance": "DERIVED"},
                    "content_title": {"value": "Fire TV Home", "provenance": "DERIVED"}
                },
                "ac": {
                    "power": {"value": true, "provenance": "OBSERVED"},
                    "target_temperature": {"value": 24, "provenance": "OBSERVED"},
                    "ambient_temperature": {"value": 23, "provenance": "OBSERVED"},
                    "mode": {"value": "COOL", "provenance": "OBSERVED"},
                    "fan_speed": {"value": "LOW", "provenance": "OBSERVED"}
                },
                "fire_tv": {
                    "online": {"value": true, "provenance": "OBSERVED"},
                    "power_state": {"value": "AWAKE", "provenance": "OBSERVED"},
                    "foreground_app": {"value": "com.amazon.tv.launcher", "provenance": "OBSERVED"},
                    "content_title": {"value": "Fire TV Home", "provenance": "OBSERVED"}
                },
                "pc": {
                    "online": {"value": true, "provenance": "OBSERVED"},
                    "master_volume": {"value": 40, "provenance": "OBSERVED"},
                    "default_audio_endpoint": {"value": "2270W", "provenance": "OBSERVED"}
                },
                "soundbar": {
                    "current_owner": {"value": "PC", "provenance": "DERIVED"},
                    "is_connected": {"value": true, "provenance": "DERIVED"}
                },
                "environment": {
                    "active_audio_route": {"value": "PC_DIRECT", "provenance": "DERIVED"}
                }
            }
        """.trimIndent()

        val json = JSONObject(liveJsonStr)
        val dto = RoomStateDto.fromJson(json)

        assertTrue(dto.projector.isPowerOn)
        assertEquals("HDMI_1", dto.projector.inputSource)
        assertEquals(40, dto.projector.brightness)
        assertTrue(dto.projector.hasSignal)

        assertTrue(dto.ac.power)
        assertEquals(24, dto.ac.targetTemperature)
        assertEquals(23, dto.ac.ambientTemperature)
        assertEquals("COOL", dto.ac.hvacMode)
        assertEquals("LOW", dto.ac.fanSpeed)

        assertTrue(dto.fireTv.isPowerOn)
        assertEquals("Fire TV Home", dto.fireTv.currentApp)

        assertTrue(dto.soundbar.isConnected)
        assertEquals("PC", dto.soundbar.connectedDevice)

        assertTrue(dto.pc.isOnline)
        assertEquals(40, dto.pc.volume)
        assertEquals("2270W", dto.pc.activeEndpoint)
    }

    @Test
    fun testClientInstantiation() {
        val client = RoomStateSyncClient(hostProvider = { "127.0.0.1" }, port = 8095)
        assertEquals("http://127.0.0.1:8095", client.baseUrl)
        assertNotNull(client.roomStateFlow)
        assertNotNull(client.isConnectedFlow)
    }
}
