package com.animus.smartroom.event.client

import android.util.Log
import com.animus.smartroom.event.model.AgentEventDto
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.Collections
import java.util.LinkedHashSet
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Authoritative Android client for proactive backend event streaming.
 * Periodically polls /api/agent/events/unacked as an ultra-reliable, battery-efficient,
 * zero-external-dependency fallback transport on Android, and submits ACKs.
 */
class AgentWebSocketClient(
    private val hostProvider: () -> String = { "192.168.1.9" },
    private val port: Int = 8095,
    private val pollIntervalMs: Long = 3000L,
    private val maxSeenEventCache: Int = 100
) {
    companion object {
        private const val TAG = "AgentWebSocketClient"
        private const val EVENTS_UNACKED_PATH = "/api/agent/events/unacked"
        private const val EVENTS_ACK_PATH = "/api/agent/events/ack"
    }

    private val isRunning = AtomicBoolean(false)
    private val seenEventIds = Collections.synchronizedSet(LinkedHashSet<String>())
    private val _eventFlow = MutableSharedFlow<AgentEventDto>(extraBufferCapacity = 50)
    val eventFlow: SharedFlow<AgentEventDto> = _eventFlow.asSharedFlow()

    private val clientScope = CoroutineScope(Dispatchers.IO)
    private var streamJob: Job? = null

    val baseUrl: String
        get() = "http://${hostProvider()}:$port"

    fun start() {
        if (isRunning.getAndSet(true)) {
            Log.d(TAG, "Agent event client already running")
            return
        }

        Log.i(TAG, "Starting proactive agent event receiver loop (baseUrl: $baseUrl)")
        streamJob = clientScope.launch {
            while (isActive && isRunning.get()) {
                try {
                    pollAndProcessEvents()
                } catch (e: Exception) {
                    Log.d(TAG, "Error in event polling pass: ${e.message}")
                }
                delay(pollIntervalMs)
            }
        }
    }

    fun stop() {
        Log.i(TAG, "Stopping proactive agent event receiver loop")
        isRunning.set(false)
        streamJob?.cancel()
        streamJob = null
    }

    suspend fun pollAndProcessEvents() {
        val events = fetchUnacknowledgedEvents()
        for (evt in events) {
            // Deduplicate
            if (seenEventIds.contains(evt.eventId)) {
                // Already processed, ensure server has ACK
                acknowledgeEvent(evt.eventId)
                continue
            }

            seenEventIds.add(evt.eventId)
            if (seenEventIds.size > maxSeenEventCache) {
                val iterator = seenEventIds.iterator()
                if (iterator.hasNext()) {
                    iterator.next()
                    iterator.remove()
                }
            }

            Log.i(TAG, "[event-received] Proactive Event [${evt.eventType}] id=${evt.eventId}: '${evt.message}'")
            _eventFlow.emit(evt)

            // Submit ACK back to server
            acknowledgeEvent(evt.eventId)
        }
    }

    private fun fetchUnacknowledgedEvents(): List<AgentEventDto> {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$EVENTS_UNACKED_PATH")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 5000
                readTimeout = 15000
                setRequestProperty("Accept", "application/json")
            }

            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val text = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                val jsonArray = org.json.JSONArray(text)
                val list = mutableListOf<AgentEventDto>()
                for (i in 0 until jsonArray.length()) {
                    val obj = jsonArray.getJSONObject(i)
                    list.add(AgentEventDto.fromJson(obj))
                }
                return list
            }
        } catch (e: Exception) {
            Log.d(TAG, "Failed to poll unacknowledged events: ${e.message}")
        } finally {
            try {
                connection?.disconnect()
            } catch (_: Exception) {}
        }
        return emptyList()
    }

    private fun acknowledgeEvent(eventId: String): Boolean {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$EVENTS_ACK_PATH/$eventId")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 5000
                readTimeout = 8000
            }
            return connection.responseCode == HttpURLConnection.HTTP_OK
        } catch (e: Exception) {
            Log.d(TAG, "Failed to ACK event $eventId: ${e.message}")
            return false
        } finally {
            try {
                connection?.disconnect()
            } catch (_: Exception) {}
        }
    }
}
