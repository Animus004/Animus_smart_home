package com.animus.smartroom.device.ac

import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Authoritative Android client for backend Air Conditioner REST API.
 * Dispatches mutations and queries to Python Phase F backend AcController.
 * Android never opens TCP 6668 or stores Tuya local_key.
 */
open class BackendAcClient(
    private val hostProvider: () -> String = { "192.168.1.4" },
    private val port: Int = 8095,
    private val timeoutMs: Int = 10000
) {
    companion object {
        private const val TAG = "BackendAcClient"
        private const val AC_STATUS_PATH = "/api/ac/status"
        private const val AC_POWER_PATH = "/api/ac/power"
        private const val AC_TEMP_PATH = "/api/ac/temperature"
        private const val AC_MODE_PATH = "/api/ac/mode"
        private const val AC_FAN_PATH = "/api/ac/fan"
    }

    val baseUrl: String
        get() = "http://${hostProvider()}:$port"

    open suspend fun getStatus(): Result<JSONObject> = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$AC_STATUS_PATH")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                setRequestProperty("Accept", "application/json")
            }

            val code = connection.responseCode
            if (code in 200..299) {
                val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                Result.success(JSONObject(responseText))
            } else {
                val errText = BufferedReader(InputStreamReader(connection.errorStream ?: connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                Result.failure(Exception("HTTP $code: $errText"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get AC status from $baseUrl: ${e.message}", e)
            Result.failure(e)
        } finally {
            try { connection?.disconnect() } catch (_: Exception) {}
        }
    }

    open suspend fun setPower(on: Boolean): Result<JSONObject> = withContext(Dispatchers.IO) {
        postJson(AC_POWER_PATH, JSONObject().apply { put("on", on) })
    }

    open suspend fun setTemperature(celsius: Int): Result<JSONObject> = withContext(Dispatchers.IO) {
        postJson(AC_TEMP_PATH, JSONObject().apply { put("temperature", celsius) })
    }

    open suspend fun setMode(modeStr: String): Result<JSONObject> = withContext(Dispatchers.IO) {
        postJson(AC_MODE_PATH, JSONObject().apply { put("mode", modeStr.uppercase()) })
    }

    open suspend fun setFanSpeed(fanStr: String): Result<JSONObject> = withContext(Dispatchers.IO) {
        postJson(AC_FAN_PATH, JSONObject().apply { put("speed", fanStr.uppercase()) })
    }

    private fun postJson(endpoint: String, body: JSONObject): Result<JSONObject> {
        var connection: HttpURLConnection? = null
        return try {
            val url = URL("$baseUrl$endpoint")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(body.toString())
                writer.flush()
            }

            val code = connection.responseCode
            if (code in 200..299) {
                val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                Result.success(JSONObject(responseText))
            } else {
                val errText = BufferedReader(InputStreamReader(connection.errorStream ?: connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                Result.failure(Exception("HTTP $code: $errText"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error posting to $endpoint: ${e.message}", e)
            Result.failure(e)
        } finally {
            try { connection?.disconnect() } catch (_: Exception) {}
        }
    }
}
