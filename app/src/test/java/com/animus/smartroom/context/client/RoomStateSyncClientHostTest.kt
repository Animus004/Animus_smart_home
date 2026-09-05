package com.animus.smartroom.context.client

import org.junit.Assert.assertEquals
import org.junit.Test

class RoomStateSyncClientHostTest {

    @Test
    fun testDefaultHostIsPcLanIp() {
        val client = RoomStateSyncClient()
        assertEquals("http://192.168.1.4:8095", client.baseUrl)
    }

    @Test
    fun testDynamicHostResolution() {
        var currentHost = "192.168.1.4"
        val client = RoomStateSyncClient(hostProvider = { currentHost })
        assertEquals("http://192.168.1.4:8095", client.baseUrl)

        currentHost = "192.168.1.100"
        assertEquals("http://192.168.1.100:8095", client.baseUrl)
    }

    @Test
    fun testAutoDiscoveryCallbackWiring() {
        var discoveredHost: String? = null
        val client = RoomStateSyncClient(
            hostProvider = { "192.168.1.9" },
            onHostAutoDiscovered = { discoveredHost = it }
        )
        // Verify callback is wired
        client.onHostAutoDiscovered?.invoke("192.168.1.4")
        assertEquals("192.168.1.4", discoveredHost)
    }

    @Test
    fun testParseRoomStateDto() {
        val rawJson = """
            {
                "timestamp": 1788609164.24,
                "is_consistent": true,
                "projector": {
                    "power": {"value": false}
                },
                "ac": {
                    "power": {"value": true},
                    "target_temperature": {"value": 24}
                },
                "environment": {
                    "room_mode": {"value": "WORK"}
                }
            }
        """.trimIndent()
        val dto = com.animus.smartroom.context.model.RoomStateDto.fromJson(org.json.JSONObject(rawJson))
        org.junit.Assert.assertNotNull(dto)
        assertEquals(true, dto.ac.power)
        assertEquals(24, dto.ac.targetTemperature)
        assertEquals("WORK", dto.environment.mode)
    }
}
