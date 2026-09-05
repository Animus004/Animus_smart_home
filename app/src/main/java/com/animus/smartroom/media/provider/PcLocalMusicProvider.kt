package com.animus.smartroom.media.provider

import android.util.Log
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * PC-local music provider that delegates audio search, playback, pause, resume,
 * and volume control to the Animus Music Daemon running on the home PC (http://192.168.1.4:8095).
 */
open class PcLocalMusicProvider(
    private val host: String = "192.168.1.4",
    private val port: Int = 8095,
    private val connectTimeoutMs: Int = 2000,
    private val readTimeoutMs: Int = 30000,
    private val hostProvider: (() -> String)? = null
) : MusicProvider {

    companion object {
        private const val TAG = "PcLocalMusicProvider"
        const val PROVIDER_ID = "pc_local_music"
    }

    val baseUrl: String
        get() = "http://${hostProvider?.invoke() ?: host}:$port"

    override val providerId: String = PROVIDER_ID
    override val displayName: String = "PC Local Music (Home)"

    override fun isInstalled(): Boolean {
        return checkHealth()
    }

    fun checkHealth(): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val healthUrl = "$baseUrl/api/health"
        Log.d(TAG, "[PC_MUSIC_HEALTH_CHECK] Pinging $healthUrl")
        var connection: HttpURLConnection? = null
        try {
            val url = URL(healthUrl)
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = connectTimeoutMs
                readTimeout = 3000
                doInput = true
            }
            val code = connection.responseCode
            val ok = code == HttpURLConnection.HTTP_OK
            if (ok) {
                Log.i(TAG, "[PC_MUSIC_ONLINE] PC Music Daemon is UP at $baseUrl")
            } else {
                Log.w(TAG, "[PC_MUSIC_OFFLINE] PC Music Daemon returned HTTP $code")
            }
            ok
        } catch (e: Exception) {
            Log.w(TAG, "[PC_MUSIC_OFFLINE] PC Music Daemon unreachable at $baseUrl: ${e.message}")
            false
        } finally {
            connection?.disconnect()
        }
    }

    override fun supportsDirectPlayback(): Boolean = true

    override fun searchAndPlay(title: String, artist: String?): ProviderResult {
        return dispatchPlayRequest(title = title, artist = artist, directVideoId = null)
    }

    override fun openSearch(title: String, artist: String?): ProviderResult {
        return searchAndPlay(title, artist)
    }

    override fun playDirectTrack(videoId: String, title: String?, artist: String?): ProviderResult {
        return dispatchPlayRequest(title = title ?: videoId, artist = artist, directVideoId = videoId)
    }

    fun pause(): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/music/pause"
        Log.i(TAG, "[PC_MUSIC_CONTROL] Sending pause request to $url")
        return@runBlocking dispatchSimpleControl(url)
    }

    fun resume(): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/music/resume"
        Log.i(TAG, "[PC_MUSIC_CONTROL] Sending resume request to $url")
        return@runBlocking dispatchSimpleControl(url)
    }

    fun connectSoundbar(): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/soundbar/connect"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending connect soundbar request to $url")
        return@runBlocking dispatchSimpleControl(url)
    }

    fun disconnectSoundbar(): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/soundbar/disconnect"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending disconnect soundbar request to $url")
        return@runBlocking dispatchSimpleControl(url)
    }

    data class MovieModeResult(
        val success: Boolean,
        val status: String,
        val message: String,
        val spokenResponse: String? = null
    )

    data class WorkModeResult(
        val success: Boolean,
        val status: String,
        val message: String,
        val spokenResponse: String? = null
    )

    fun startMovieModeWithFeedback(contentTitle: String? = null, provider: String? = null): MovieModeResult = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/movie-mode/start"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending start movie mode request to $url (content='$contentTitle', provider='$provider')")
        val json = JSONObject().apply {
            if (!contentTitle.isNullOrBlank()) {
                put("content", contentTitle)
            }
            if (!provider.isNullOrBlank()) {
                put("provider", provider)
            }
        }
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 130000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.toString())
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_MOVIE_MODE_RESPONSE] $url HTTP $code: $responseText")

            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val status = if (jsonResponse.has("status")) jsonResponse.getString("status") else "UNKNOWN"
                val isSuccess = jsonResponse.optBoolean("success", false) || status == "HEALTHY"
                val spoken = if (jsonResponse.has("spoken_response") && !jsonResponse.isNull("spoken_response")) jsonResponse.getString("spoken_response") else null
                val msg = if (jsonResponse.has("message") && !jsonResponse.isNull("message")) jsonResponse.getString("message") else (if (isSuccess) "Movie Mode started" else status)
                MovieModeResult(
                    success = isSuccess,
                    status = status,
                    message = msg,
                    spokenResponse = spoken
                )
            } else {
                MovieModeResult(
                    success = false,
                    status = "HTTP_$code",
                    message = "PC daemon error: $responseText",
                    spokenResponse = "Failed to communicate with PC daemon."
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_MOVIE_MODE_ERROR] Error starting movie mode: ${e.message}", e)
            MovieModeResult(
                success = false,
                status = "NETWORK_ERROR",
                message = e.message ?: "Network error",
                spokenResponse = "Cannot connect to the room controller."
            )
        } finally {
            connection?.disconnect()
        }
    }

    fun startMovieMode(contentTitle: String? = null, provider: String? = null): Boolean {
        return startMovieModeWithFeedback(contentTitle, provider).success
    }

    open fun stopMovieModeWithFeedback(): MovieModeResult = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/movie-mode/stop"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending stop movie mode request to $url")
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 30000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write("{}")
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_MOVIE_MODE_STOP_RESPONSE] $url HTTP $code: $responseText")

            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val status = if (jsonResponse.has("status")) jsonResponse.getString("status") else "OFF"
                val isSuccess = jsonResponse.optBoolean("success", true)
                val spoken = if (jsonResponse.has("spoken_response") && !jsonResponse.isNull("spoken_response")) jsonResponse.getString("spoken_response") else null
                val msg = if (jsonResponse.has("message") && !jsonResponse.isNull("message")) jsonResponse.getString("message") else "Movie Mode stopped."
                MovieModeResult(
                    success = isSuccess,
                    status = status,
                    message = msg,
                    spokenResponse = spoken
                )
            } else {
                MovieModeResult(
                    success = false,
                    status = "HTTP_$code",
                    message = "PC daemon error: $responseText",
                    spokenResponse = "Failed to communicate with PC daemon."
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_MOVIE_MODE_STOP_ERROR] Error stopping movie mode: ${e.message}", e)
            MovieModeResult(
                success = false,
                status = "NETWORK_ERROR",
                message = e.message ?: "Network error",
                spokenResponse = "Cannot connect to the room controller."
            )
        } finally {
            connection?.disconnect()
        }
    }

    open fun stopMovieMode(): Boolean {
        return stopMovieModeWithFeedback().success
    }

    open fun startWorkModeWithFeedback(): WorkModeResult = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/agent/work/start"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending start work mode request to $url")
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 30000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write("{}")
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_WORK_MODE_RESPONSE] $url HTTP $code: $responseText")
            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", true)
                val msg = jsonResponse.optString("message", "Work Mode engaged.")
                WorkModeResult(success = isSuccess, status = "SUCCESS", message = msg, spokenResponse = msg)
            } else {
                WorkModeResult(success = false, status = "HTTP_$code", message = "PC daemon error: $responseText", spokenResponse = "Failed to launch Work Mode.")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_WORK_MODE_ERROR] Error starting work mode: ${e.message}", e)
            WorkModeResult(success = false, status = "NETWORK_ERROR", message = e.message ?: "Network error", spokenResponse = "Cannot connect to PC daemon.")
        } finally {
            connection?.disconnect()
        }
    }

    open fun stopWorkModeWithFeedback(): WorkModeResult = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/agent/work/wrapup"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending wrap up work mode request to $url")
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 30000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write("{}")
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_WORK_WRAPUP_RESPONSE] $url HTTP $code: $responseText")
            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", true)
                val msg = jsonResponse.optString("message", "Work wrap-up completed.")
                WorkModeResult(success = isSuccess, status = "SUCCESS", message = msg, spokenResponse = msg)
            } else {
                WorkModeResult(success = false, status = "HTTP_$code", message = "PC daemon error: $responseText", spokenResponse = "Failed to wrap up work.")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_WORK_WRAPUP_ERROR] Error wrapping up work mode: ${e.message}", e)
            WorkModeResult(success = false, status = "NETWORK_ERROR", message = e.message ?: "Network error", spokenResponse = "Cannot connect to PC daemon.")
        } finally {
            connection?.disconnect()
        }
    }

    open fun startWorkMode(): Boolean {
        return startWorkModeWithFeedback().success
    }

    open fun stopWorkMode(): Boolean {
        return stopWorkModeWithFeedback().success
    }

    open fun setProjectorPower(on: Boolean): Pair<Boolean, String> = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/projector/power"
        val action = if (on) "ON" else "OFF"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending projector power request: $action to $url")
        val json = JSONObject().apply {
            put("action", action)
        }
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 125000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.toString())
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_PROJECTOR_POWER_RESPONSE] $url HTTP $code: $responseText")

            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", false)
                val powerState = jsonResponse.optString("power_state", if (on) "ON" else "OFF")
                val msg = jsonResponse.optString("message", if (isSuccess) "Projector is now $powerState." else "Projector power action failed.")
                Pair(isSuccess, msg)
            } else {
                Pair(false, "Projector command returned HTTP $code: $responseText")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_PROJECTOR_POWER_ERROR] Error controlling projector power: ${e.message}", e)
            Pair(false, "Failed to reach projector controller: ${e.message}")
        } finally {
            connection?.disconnect()
        }
    }

    open fun setProjectorSource(source: String): Pair<Boolean, String> = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/projector/source"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending projector source request: $source to $url")
        val json = JSONObject().apply {
            put("source", source)
        }
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 30000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.toString())
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_PROJECTOR_SOURCE_RESPONSE] $url HTTP $code: $responseText")

            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", false)
                val msg = jsonResponse.optString("message", "Projector source set to $source.")
                Pair(isSuccess, msg)
            } else {
                Pair(false, "Projector source command returned HTTP $code: $responseText")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_PROJECTOR_SOURCE_ERROR] Error setting projector source: ${e.message}", e)
            Pair(false, "Failed to reach projector controller: ${e.message}")
        } finally {
            connection?.disconnect()
        }
    }

    open fun getProjectorStatus(): JSONObject? = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/projector/status"
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = connectTimeoutMs
                readTimeout = 5000
                setRequestProperty("Accept", "application/json")
            }
            val code = connection.responseCode
            if (code in 200..299) {
                val text = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                JSONObject(text)
            } else {
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "[PC_PROJECTOR_STATUS_ERROR] Failed to query projector status: ${e.message}")
            null
        } finally {
            connection?.disconnect()
        }
    }

    open fun switchAudioOwnership(target: String): Pair<Boolean, String> = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/audio/switch"
        Log.i(TAG, "[PC_ROOM_CONTROL] Sending audio ownership switch request to $url (target=$target)")
        val json = JSONObject().apply {
            put("target", target)
        }
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 30000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.toString())
                writer.flush()
            }
            val code = connection.responseCode
            val responseText = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream
                if (err != null) BufferedReader(InputStreamReader(err, Charsets.UTF_8)).use { it.readText() } else "HTTP $code"
            }
            Log.i(TAG, "[PC_AUDIO_SWITCH_RESPONSE] $url HTTP $code: $responseText")

            if (code in 200..299) {
                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", false)
                val msg = jsonResponse.optString("message", if (isSuccess) "Audio ownership switched." else "Audio switch failed.")
                Pair(isSuccess, msg)
            } else {
                Pair(false, "Audio switch returned HTTP $code: $responseText")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[PC_AUDIO_SWITCH_ERROR] Error switching audio ownership: ${e.message}", e)
            Pair(false, "Failed to communicate with audio controller: ${e.message}")
        } finally {
            connection?.disconnect()
        }
    }

    fun getSoundbarStatus(): String = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/room/soundbar/status"
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = connectTimeoutMs
                readTimeout = 4000
            }
            if (connection.responseCode in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                "{\"room_audio_state\": \"DISCONNECTED\"}"
            }
        } catch (e: Exception) {
            "{\"room_audio_state\": \"UNREACHABLE\"}"
        } finally {
            connection?.disconnect()
        }
    }

    fun setVolume(percentage: Int): Boolean = kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
        val url = "$baseUrl/api/music/volume"
        Log.i(TAG, "[PC_MUSIC_CONTROL] Sending volume request to $url: volume=$percentage")
        val json = JSONObject().apply {
            put("volume", percentage)
        }
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 4000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.toString())
                writer.flush()
            }
            val code = connection.responseCode
            val ok = code in 200..299
            Log.i(TAG, "[PC_MUSIC_VOLUME_RESPONSE] HTTP $code (success=$ok)")
            ok
        } catch (e: Exception) {
            Log.e(TAG, "[PC_MUSIC_VOLUME_ERROR] Error setting volume: ${e.message}", e)
            false
        } finally {
            connection?.disconnect()
        }
    }

    private fun dispatchSimpleControl(urlStr: String): Boolean {
        var connection: HttpURLConnection? = null
        return try {
            val url = URL(urlStr)
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 4000
                doOutput = true
                doInput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write("{}")
                writer.flush()
            }
            val code = connection.responseCode
            val ok = code in 200..299
            Log.i(TAG, "[PC_MUSIC_CONTROL_RESPONSE] $urlStr HTTP $code (success=$ok)")
            ok
        } catch (e: Exception) {
            Log.e(TAG, "[PC_MUSIC_CONTROL_ERROR] Error calling $urlStr: ${e.message}", e)
            false
        } finally {
            connection?.disconnect()
        }
    }

    private fun dispatchPlayRequest(title: String, artist: String?, directVideoId: String?): ProviderResult =
        kotlinx.coroutines.runBlocking(kotlinx.coroutines.Dispatchers.IO) {
            val playUrl = "$baseUrl/api/music/play"
            Log.i(TAG, "[PC_MUSIC_REQUEST] Dispatching to $playUrl: title='$title', artist='$artist', directId='$directVideoId'")

            DiagnosticBus.log(
                tag = "pc_music",
                stage = DiagnosticStage.PLAYBACK,
                message = "Sending play request to PC: '$title'"
            )

            val jsonBody = JSONObject().apply {
                put("title", title)
                if (!artist.isNullOrBlank()) {
                    put("artist", artist)
                }
                if (!directVideoId.isNullOrBlank()) {
                    put("direct_video_id", directVideoId)
                }
            }

            var connection: HttpURLConnection? = null
            try {
                val url = URL(playUrl)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = connectTimeoutMs
                    readTimeout = readTimeoutMs
                    doOutput = true
                    doInput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Accept", "application/json")
                }

                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(jsonBody.toString())
                    writer.flush()
                }

                val statusCode = connection.responseCode
                val responseText = if (statusCode in 200..299) {
                    BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                } else {
                    val errorStream = connection.errorStream
                    if (errorStream != null) {
                        BufferedReader(InputStreamReader(errorStream, Charsets.UTF_8)).use { it.readText() }
                    } else {
                        "HTTP $statusCode"
                    }
                }

                Log.i(TAG, "[PC_MUSIC_RESPONSE] HTTP $statusCode: $responseText")

                if (statusCode !in 200..299) {
                    val errorMsg = "HTTP $statusCode: $responseText"
                    DiagnosticBus.log(tag = "pc_music", stage = DiagnosticStage.FAILED, message = errorMsg)
                    return@runBlocking ProviderResult.Failed(errorMsg)
                }

                val jsonResponse = JSONObject(responseText)
                val isSuccess = jsonResponse.optBoolean("success", false)
                val status = jsonResponse.optString("status", "")

                if (isSuccess || status == "PLAYING") {
                    DiagnosticBus.log(
                        tag = "pc_music",
                        stage = DiagnosticStage.PLAYBACK,
                        message = "PC playback confirmed for '$title'"
                    )
                    ProviderResult.PlaybackConfirmed
                } else {
                    val error = jsonResponse.optString("error", "Unknown PC error")
                    DiagnosticBus.log(tag = "pc_music", stage = DiagnosticStage.FAILED, message = error)
                    ProviderResult.Failed(error)
                }
            } catch (e: Exception) {
                Log.e(TAG, "[PC_MUSIC_ERROR] Exception calling PC Music Daemon: ${e.message}", e)
                DiagnosticBus.log(tag = "pc_music", stage = DiagnosticStage.FAILED, message = "Network failure: ${e.message}")
                ProviderResult.Failed(e.message ?: "Network failure")
            } finally {
                connection?.disconnect()
            }
        }
}
