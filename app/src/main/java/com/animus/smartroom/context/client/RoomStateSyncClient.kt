package com.animus.smartroom.context.client

import android.util.Log
import com.animus.smartroom.context.model.RoomStateDto
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Authoritative Android client for continuous RoomState synchronization with Animus Python backend.
 * Periodically polls GET /api/room/state to hydrate physical telemetry into the UI.
 */
class RoomStateSyncClient(
    private val hostProvider: () -> String = { "192.168.1.9" },
    private val port: Int = 8095,
    private val pollIntervalMs: Long = 4000L,
    private val connectTimeoutMs: Int = 5000,
    private val readTimeoutMs: Int = 15000
) {
    companion object {
        private const val TAG = "RoomStateSyncClient"
        private const val ROOM_STATE_PATH = "/api/room/state"
    }

    private val isRunning = AtomicBoolean(false)
    private val _roomStateFlow = MutableStateFlow<RoomStateDto?>(null)
    val roomStateFlow: StateFlow<RoomStateDto?> = _roomStateFlow.asStateFlow()

    private val _isConnectedFlow = MutableStateFlow(false)
    val isConnectedFlow: StateFlow<Boolean> = _isConnectedFlow.asStateFlow()

    private val clientScope = CoroutineScope(Dispatchers.IO)
    private var syncJob: Job? = null

    val baseUrl: String
        get() = "http://${hostProvider()}:$port"

    fun start() {
        if (isRunning.getAndSet(true)) {
            Log.d(TAG, "Room state sync client already running")
            return
        }

        Log.i(TAG, "Starting RoomState synchronization loop (baseUrl: $baseUrl, interval: ${pollIntervalMs}ms)")
        syncJob = clientScope.launch {
            while (isActive && isRunning.get()) {
                try {
                    val state = fetchRoomState()
                    if (state != null) {
                        _roomStateFlow.value = state
                        _isConnectedFlow.value = true
                    } else {
                        _isConnectedFlow.value = false
                    }
                } catch (e: Exception) {
                    Log.d(TAG, "RoomState polling error: ${e.message}")
                    _isConnectedFlow.value = false
                }
                delay(pollIntervalMs)
            }
        }
    }

    fun stop() {
        Log.i(TAG, "Stopping RoomState synchronization loop")
        isRunning.set(false)
        syncJob?.cancel()
        syncJob = null
    }

    suspend fun pollOnce(): RoomStateDto? = withContext(Dispatchers.IO) {
        val state = fetchRoomState()
        if (state != null) {
            _roomStateFlow.value = state
            _isConnectedFlow.value = true
        } else {
            _isConnectedFlow.value = false
        }
        state
    }

    fun fetchRoomState(): RoomStateDto? {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$ROOM_STATE_PATH")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                setRequestProperty("Accept", "application/json")
            }

            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val text = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                val json = JSONObject(text)
                return RoomStateDto.fromJson(json)
            } else {
                Log.d(TAG, "GET $ROOM_STATE_PATH returned HTTP ${connection.responseCode}")
            }
        } catch (e: Exception) {
            Log.d(TAG, "Failed to fetch room state from $baseUrl: ${e.message}")
        } finally {
            try {
                connection?.disconnect()
            } catch (_: Exception) {}
        }
        return null
    }
}
