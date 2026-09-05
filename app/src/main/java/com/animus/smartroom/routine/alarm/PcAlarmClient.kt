package com.animus.smartroom.routine.alarm

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

sealed interface PcAlarmResult {
    data class Success(val message: String, val audioDevice: String?) : PcAlarmResult
    data class Degraded(val reason: String) : PcAlarmResult
    data class Error(val message: String) : PcAlarmResult
}

class PcAlarmClient(
    private val host: String = "192.168.1.4",
    private val port: Int = 8095,
    private val connectTimeoutMs: Int = 1500,
    private val readTimeoutMs: Int = 3000,
    private val hostProvider: (() -> String)? = null
) {
    companion object {
        private const val TAG = "PcAlarmClient"
    }

    private val baseUrl: String
        get() = "http://${hostProvider?.invoke() ?: host}:$port"

    suspend fun startPcAlarm(): PcAlarmResult = withContext(Dispatchers.IO) {
        var conn: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl/api/room/alarm/start")
            conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                doInput = true
                setRequestProperty("Content-Type", "application/json")
            }

            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) {
                val resp = conn.inputStream.bufferedReader().use { it.readText() }
                val json = JSONObject(resp)
                val success = json.optBoolean("success", false)
                val status = json.optString("status", "")
                val device = if (json.has("audio_device_name") && !json.isNull("audio_device_name")) json.getString("audio_device_name") else null

                if (success) {
                    Log.i(TAG, "[PC_ALARM_START_OK] PC Alarm playing on device: $device")
                    PcAlarmResult.Success("PC Alarm playing", device)
                } else if (status.contains("MOVIE_MODE")) {
                    Log.w(TAG, "[PC_ALARM_DEGRADED] Movie Mode active; PC alarm deferred")
                    PcAlarmResult.Degraded("Movie Mode active; deferred to Android alarm")
                } else {
                    val err = json.optString("error", "Unknown error")
                    PcAlarmResult.Error("PC Alarm start failed: $err")
                }
            } else {
                PcAlarmResult.Error("PC Daemon returned HTTP $code")
            }
        } catch (e: Exception) {
            Log.w(TAG, "[PC_ALARM_UNREACHABLE] PC Daemon unreachable: ${e.message}")
            PcAlarmResult.Error("PC Alarm unavailable: ${e.message}")
        } finally {
            conn?.disconnect()
        }
    }

    suspend fun stopPcAlarm(): PcAlarmResult = withContext(Dispatchers.IO) {
        var conn: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl/api/room/alarm/stop")
            conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                doInput = true
                setRequestProperty("Content-Type", "application/json")
            }

            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_OK) {
                Log.i(TAG, "[PC_ALARM_STOP_OK] PC Alarm stopped successfully")
                PcAlarmResult.Success("PC Alarm stopped", null)
            } else {
                PcAlarmResult.Error("PC Daemon stop returned HTTP $code")
            }
        } catch (e: Exception) {
            Log.w(TAG, "[PC_ALARM_STOP_UNREACHABLE] PC Daemon unreachable: ${e.message}")
            PcAlarmResult.Error("PC Daemon unreachable: ${e.message}")
        } finally {
            conn?.disconnect()
        }
    }
}
