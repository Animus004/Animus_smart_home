package com.animus.smartroom.device.tuya.client

import android.util.Log
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

interface TuyaApiClient {
    suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>>
    suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean>
}

class TuyaCloudApiClient(
    private val accessIdProvider: () -> String,
    private val accessSecretProvider: () -> String,
    private val endpointProvider: () -> String = { "https://openapi.tuyain.com" }
) : TuyaApiClient {

    companion object {
        private const val TAG = "TuyaCloudApiClient"
    }

    private var cachedToken: String? = null
    private var tokenExpireTimeMs: Long = 0L

    override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> = withContext(Dispatchers.IO) {
        val accessId = accessIdProvider().trim()
        val accessSecret = accessSecretProvider().trim()
        val endpoint = endpointProvider().trim()

        if (accessId.isBlank() || accessSecret.isBlank()) {
            return@withContext Result.failure(IllegalStateException("Tuya credentials are not configured."))
        }

        val tokenResult = getOrFetchToken(accessId, accessSecret, endpoint)
        val token = tokenResult.getOrElse {
            return@withContext Result.failure(it)
        }

        val path = "/v1.0/devices/$deviceId/status"
        val response = executeRequest(
            method = "GET",
            endpoint = endpoint,
            path = path,
            accessId = accessId,
            accessSecret = accessSecret,
            token = token,
            payload = null
        )

        response.mapCatching { jsonStr ->
            val json = JSONObject(jsonStr)
            if (!json.optBoolean("success", false)) {
                val code = json.optInt("code", -1)
                val msg = json.optString("msg", "Unknown Tuya error")
                throw RuntimeException("Tuya API Error ($code): $msg")
            }

            val resultList = mutableListOf<TuyaDeviceStatusItem>()
            val resultArray = json.optJSONArray("result")
            if (resultArray != null) {
                for (i in 0 until resultArray.length()) {
                    val item = resultArray.getJSONObject(i)
                    val code = item.optString("code", "")
                    val value = item.opt("value")
                    if (code.isNotBlank()) {
                        resultList.add(TuyaDeviceStatusItem(code = code, value = value))
                    }
                }
            }
            resultList
        }
    }

    override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> = withContext(Dispatchers.IO) {
        val accessId = accessIdProvider().trim()
        val accessSecret = accessSecretProvider().trim()
        val endpoint = endpointProvider().trim()

        if (accessId.isBlank() || accessSecret.isBlank()) {
            return@withContext Result.failure(IllegalStateException("Tuya credentials are not configured."))
        }

        val tokenResult = getOrFetchToken(accessId, accessSecret, endpoint)
        val token = tokenResult.getOrElse {
            return@withContext Result.failure(it)
        }

        val path = "/v1.0/devices/$deviceId/commands"
        val commandsArray = JSONArray()
        for (cmd in commands) {
            val cmdObj = JSONObject()
            for ((k, v) in cmd) {
                cmdObj.put(k, v)
            }
            commandsArray.put(cmdObj)
        }

        val payloadObj = JSONObject().apply {
            put("commands", commandsArray)
        }

        val response = executeRequest(
            method = "POST",
            endpoint = endpoint,
            path = path,
            accessId = accessId,
            accessSecret = accessSecret,
            token = token,
            payload = payloadObj.toString()
        )

        response.mapCatching { jsonStr ->
            val json = JSONObject(jsonStr)
            val success = json.optBoolean("success", false)
            if (!success) {
                val code = json.optInt("code", -1)
                val msg = json.optString("msg", "Unknown Tuya error")
                throw RuntimeException("Tuya Command Error ($code): $msg")
            }
            true
        }
    }

    private suspend fun getOrFetchToken(accessId: String, accessSecret: String, endpoint: String): Result<String> {
        val now = System.currentTimeMillis()
        val currentToken = cachedToken
        if (currentToken != null && now < tokenExpireTimeMs - 60_000L) {
            return Result.success(currentToken)
        }

        val t = System.currentTimeMillis()
        val path = "/v1.0/token?grant_type=1"
        val stringToSign = "GET\n" + sha256Hex("") + "\n\n" + path
        val signStr = accessId + t + stringToSign
        val sign = hmacSha256(signStr, accessSecret)

        return try {
            val url = URL(endpoint + path)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                setRequestProperty("client_id", accessId)
                setRequestProperty("sign", sign)
                setRequestProperty("t", t.toString())
                setRequestProperty("sign_method", "HMAC-SHA256")
                connectTimeout = 8000
                readTimeout = 10000
            }

            val code = conn.responseCode
            val body = if (code == HttpURLConnection.HTTP_OK) {
                BufferedReader(InputStreamReader(conn.inputStream, StandardCharsets.UTF_8)).use { it.readText() }
            } else {
                val errStream = conn.errorStream ?: conn.inputStream
                BufferedReader(InputStreamReader(errStream, StandardCharsets.UTF_8)).use { it.readText() }
            }

            val json = JSONObject(body)
            if (json.optBoolean("success", false)) {
                val resultObj = json.optJSONObject("result")
                val token = resultObj?.optString("access_token", "") ?: ""
                val expireTimeSec = resultObj?.optLong("expire_time", 7200L) ?: 7200L
                if (token.isNotBlank()) {
                    cachedToken = token
                    tokenExpireTimeMs = now + (expireTimeSec * 1000L)
                    Result.success(token)
                } else {
                    Result.failure(RuntimeException("Empty access token in Tuya response"))
                }
            } else {
                val errCode = json.optInt("code", -1)
                val errMsg = json.optString("msg", "Failed to fetch Tuya access token")
                Result.failure(RuntimeException("Tuya Token Error ($errCode): $errMsg"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[token] Failed to fetch Tuya token: ${e.message}", e)
            Result.failure(e)
        }
    }

    private fun executeRequest(
        method: String,
        endpoint: String,
        path: String,
        accessId: String,
        accessSecret: String,
        token: String,
        payload: String?
    ): Result<String> {
        return try {
            val t = System.currentTimeMillis()
            val bodyPayload = payload ?: ""
            val stringToSign = "$method\n" + sha256Hex(bodyPayload) + "\n\n" + path
            val signStr = accessId + token + t + stringToSign
            val sign = hmacSha256(signStr, accessSecret)

            val url = URL(endpoint + path)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = method
                setRequestProperty("client_id", accessId)
                setRequestProperty("access_token", token)
                setRequestProperty("sign", sign)
                setRequestProperty("t", t.toString())
                setRequestProperty("sign_method", "HMAC-SHA256")
                connectTimeout = 8000
                readTimeout = 10000

                if (method == "POST" && payload != null) {
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    doOutput = true
                    OutputStreamWriter(outputStream, StandardCharsets.UTF_8).use { writer ->
                        writer.write(payload)
                        writer.flush()
                    }
                }
            }

            val code = conn.responseCode
            val responseText = if (code == HttpURLConnection.HTTP_OK) {
                BufferedReader(InputStreamReader(conn.inputStream, StandardCharsets.UTF_8)).use { it.readText() }
            } else {
                val errStream = conn.errorStream ?: conn.inputStream
                BufferedReader(InputStreamReader(errStream, StandardCharsets.UTF_8)).use { it.readText() }
            }

            Result.success(responseText)
        } catch (e: Exception) {
            Log.e(TAG, "[request] Error executing $method $path: ${e.message}", e)
            Result.failure(e)
        }
    }

    private fun sha256Hex(text: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(text.toByteArray(StandardCharsets.UTF_8))
        return hash.joinToString("") { "%02x".format(it) }
    }

    private fun hmacSha256(data: String, key: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        val secretKey = SecretKeySpec(key.toByteArray(StandardCharsets.UTF_8), "HmacSHA256")
        mac.init(secretKey)
        val rawHmac = mac.doFinal(data.toByteArray(StandardCharsets.UTF_8))
        return rawHmac.joinToString("") { "%02x".format(it) }.uppercase()
    }
}
