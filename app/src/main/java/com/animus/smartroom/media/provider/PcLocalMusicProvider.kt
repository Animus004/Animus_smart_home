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
 * and volume control to the Animus Music Daemon running on the home PC (http://192.168.1.9:8095).
 */
class PcLocalMusicProvider(
    private val host: String = "192.168.1.9",
    private val port: Int = 8095,
    private val connectTimeoutMs: Int = 2000,
    private val readTimeoutMs: Int = 10000
) : MusicProvider {

    companion object {
        private const val TAG = "PcLocalMusicProvider"
        const val PROVIDER_ID = "pc_local_music"
    }

    val baseUrl: String = "http://$host:$port"

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
