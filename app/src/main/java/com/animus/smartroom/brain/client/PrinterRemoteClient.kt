package com.animus.smartroom.brain.client

import android.util.Base64
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class PrinterUploadResult(
    val success: Boolean,
    val docId: String = "",
    val filename: String = "",
    val message: String = "",
    val error: String? = null
)

/**
 * Android client for communicating with the HP Ink Tank 310 Series subsystem
 * on the PC Music Daemon (Port 8095).
 */
class PrinterRemoteClient(
    private val hostProvider: () -> String = { "192.168.1.4" },
    private val port: Int = 8095,
    private val connectTimeoutMs: Int = 5000,
    private val readTimeoutMs: Int = 30000
) {
    companion object {
        private const val TAG = "PrinterRemoteClient"
        private const val BASE64_UPLOAD_PATH = "/api/printer/upload-base64"
        private const val CANCEL_PATH = "/api/printer/cancel"
        private const val STATUS_PATH = "/api/printer/status"
    }

    val baseUrl: String
        get() = "http://${hostProvider()}:$port"

    suspend fun uploadAndPrintFile(
        filename: String,
        fileBytes: ByteArray,
        copies: Int = 1,
        orientation: String = "portrait",
        autoPrint: Boolean = true
    ): PrinterUploadResult = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$BASE64_UPLOAD_PATH")
            Log.i(TAG, "[uploadAndPrintFile] POST $url -> '$filename' (${fileBytes.size} bytes)")

            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                doInput = true
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }

            val b64Content = Base64.encodeToString(fileBytes, Base64.NO_WRAP)
            val reqJson = JSONObject().apply {
                put("filename", filename)
                put("content_base64", b64Content)
                put("copies", copies)
                put("orientation", orientation)
                put("fit_to_page", true)
                put("auto_print", autoPrint)
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(reqJson.toString())
                writer.flush()
            }

            val code = connection.responseCode
            val responseBody = if (code in 200..299) {
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            } else {
                val err = connection.errorStream?.let {
                    BufferedReader(InputStreamReader(it, Charsets.UTF_8)).use { r -> r.readText() }
                } ?: "HTTP $code"
                return@withContext PrinterUploadResult(success = false, error = err)
            }

            val resJson = JSONObject(responseBody)
            val success = resJson.optBoolean("success", false)
            val docId = resJson.optString("doc_id", "")
            val printRes = resJson.optJSONObject("print_result")
            val msg = printRes?.optString("message") ?: "File spooled to HP Ink Tank 310"

            PrinterUploadResult(
                success = success,
                docId = docId,
                filename = filename,
                message = msg,
                error = if (!success) resJson.optString("error", "Unknown error") else null
            )
        } catch (e: Exception) {
            Log.e(TAG, "[uploadAndPrintFile] Exception: ${e.message}", e)
            PrinterUploadResult(success = false, error = e.message)
        } finally {
            connection?.disconnect()
        }
    }

    suspend fun cancelPrintJobs(): Boolean = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$CANCEL_PATH")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = 5000
                doInput = true
                setRequestProperty("Accept", "application/json")
            }
            connection.responseCode in 200..299
        } catch (e: Exception) {
            Log.e(TAG, "[cancelPrintJobs] Error: ${e.message}")
            false
        } finally {
            connection?.disconnect()
        }
    }
}
