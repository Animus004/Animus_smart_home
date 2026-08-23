package com.animus.smartroom.device.tuya.recovery

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.Arrays
import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec

data class TuyaDiscoveredDevice(
    val ip: String,
    val gwId: String,
    val productKey: String,
    val version: String,
    val active: Int
)

interface TuyaLocalDiscoveryService {
    suspend fun listenForDevice(expectedGwId: String, timeoutMs: Long = 8000L): Result<TuyaDiscoveredDevice>
}

class DefaultTuyaLocalDiscoveryService(
    private val port: Int = 6667
) : TuyaLocalDiscoveryService {

    companion object {
        private const val TAG = "TuyaLocalDiscovery"
        private const val DEFAULT_TUYA_KEY_SEED = "yGAdlopoPVldABfn"
    }

    override suspend fun listenForDevice(
        expectedGwId: String,
        timeoutMs: Long
    ): Result<TuyaDiscoveredDevice> = withContext(Dispatchers.IO) {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket(null).apply {
                reuseAddress = true
                bind(InetSocketAddress(port))
                soTimeout = timeoutMs.coerceIn(1000L, 30000L).toInt()
            }

            val md5 = MessageDigest.getInstance("MD5")
            val keyBytes = md5.digest(DEFAULT_TUYA_KEY_SEED.toByteArray(StandardCharsets.UTF_8))
            val aesKey = SecretKeySpec(keyBytes, "AES")

            val buf = ByteArray(2048)
            val packet = DatagramPacket(buf, buf.size)

            val startTime = System.currentTimeMillis()
            while (System.currentTimeMillis() - startTime < timeoutMs) {
                try {
                    socket.receive(packet)
                    val len = packet.length
                    if (len > 28) {
                        val encrypted = Arrays.copyOfRange(buf, 20, len - 8)
                        val cipher = Cipher.getInstance("AES/ECB/PKCS5Padding")
                        cipher.init(Cipher.DECRYPT_MODE, aesKey)
                        val decrypted = cipher.doFinal(encrypted)
                        val jsonStr = String(decrypted, StandardCharsets.UTF_8)
                        val json = JSONObject(jsonStr)

                        val gwId = json.optString("gwId", "")
                        val ip = json.optString("ip", packet.address.hostAddress ?: "")
                        val productKey = json.optString("productKey", "")
                        val version = json.optString("version", "3.3")
                        val active = json.optInt("active", 2)

                        if (gwId.equals(expectedGwId, ignoreCase = true) || expectedGwId.isBlank()) {
                            val discovered = TuyaDiscoveredDevice(
                                ip = ip,
                                gwId = gwId,
                                productKey = productKey,
                                version = version,
                                active = active
                            )
                            Log.i(TAG, "[discovered] AC found on LAN: IP=$ip, gwId=$gwId, ver=$version")
                            return@withContext Result.success(discovered)
                        }
                    }
                } catch (e: java.net.SocketTimeoutException) {
                    break
                } catch (e: Exception) {
                    Log.w(TAG, "[packet-parse] Error parsing UDP packet: ${e.message}")
                }
            }
            Result.failure(NoSuchElementException("No discovery packet received for device '$expectedGwId' within ${timeoutMs}ms."))
        } catch (e: Exception) {
            Log.e(TAG, "[listen] UDP discovery error: ${e.message}", e)
            Result.failure(e)
        } finally {
            try {
                socket?.close()
            } catch (_: Exception) {}
        }
    }
}
