package com.animus.smartroom.media

import com.animus.smartroom.media.provider.PcLocalMusicProvider
import com.animus.smartroom.media.provider.ProviderResult
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.OutputStreamWriter
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

class PcLocalMusicProviderIntegrationTest {

    private var serverSocket: ServerSocket? = null
    private var port: Int = 0

    @Before
    fun setUp() {
        serverSocket = ServerSocket(0)
        port = serverSocket!!.localPort
    }

    @After
    fun tearDown() {
        try {
            serverSocket?.close()
        } catch (ignored: Exception) {}
    }

    @Test
    fun `test health check success returns true`() {
        thread {
            try {
                for (i in 0..1) {
                    val socket = serverSocket?.accept() ?: break
                    val reader = socket.getInputStream().bufferedReader()
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (line.isEmpty()) break
                    }
                    val response = """{"status":"UP","service":"animus-music-daemon","version":"1.1.0"}"""
                    val bodyBytes = response.toByteArray(Charsets.UTF_8)
                    val out = socket.getOutputStream()
                    out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                    out.write(bodyBytes)
                    out.flush()
                    socket.close()
                }
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 1000
        )

        assertTrue(provider.checkHealth())
        assertTrue(provider.isInstalled())
        assertEquals("pc_local_music", provider.providerId)
    }

    @Test
    fun `test health check offline returns false`() {
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                socket.getInputStream().bufferedReader().apply {
                    while (true) {
                        val line = readLine() ?: break
                        if (line.isEmpty()) break
                    }
                }
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 1000
        )

        assertFalse(provider.checkHealth())
    }

    @Test
    fun `test searchAndPlay sends structured json and parses success response`() {
        var recordedBody = ""
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                val reader = socket.getInputStream().bufferedReader()
                var contentLength = 0
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.lowercase().startsWith("content-length:")) {
                        contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                    }
                    if (line.isEmpty()) break
                }
                if (contentLength > 0) {
                    val chars = CharArray(contentLength)
                    reader.read(chars, 0, contentLength)
                    recordedBody = String(chars)
                }

                val response = """{"success":true,"status":"PLAYING","title":"Zara Zara","artist":"Bombay Jayashri","duration":298,"video_id":"IWjbBSMsQJg","audio_device_id":"wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}"}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        val result = provider.searchAndPlay("Zara Zara", "Bombay Jayashri")
        assertTrue(result is ProviderResult.PlaybackConfirmed)
        assertTrue(recordedBody.contains("Zara Zara"))
        assertTrue(recordedBody.contains("Bombay Jayashri"))
    }

    @Test
    fun `test playDirectTrack sends direct_video_id`() {
        var recordedBody = ""
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                val reader = socket.getInputStream().bufferedReader()
                var contentLength = 0
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.lowercase().startsWith("content-length:")) {
                        contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                    }
                    if (line.isEmpty()) break
                }
                if (contentLength > 0) {
                    val chars = CharArray(contentLength)
                    reader.read(chars, 0, contentLength)
                    recordedBody = String(chars)
                }

                val response = """{"success":true,"status":"PLAYING","title":"Zara Zara","video_id":"IWjbBSMsQJg"}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        val result = provider.playDirectTrack(videoId = "IWjbBSMsQJg", title = "Zara Zara", artist = null)
        assertTrue(result is ProviderResult.PlaybackConfirmed)
        assertTrue(recordedBody.contains("IWjbBSMsQJg"))
    }

    @Test
    fun `test pause dispatches correctly`() {
        var requestedPath = ""
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                val reader = socket.getInputStream().bufferedReader()
                val requestLine = reader.readLine() ?: ""
                requestedPath = requestLine.split(" ")[1]
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val response = """{"success":true,"status":"PAUSED"}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        assertTrue(provider.pause())
        assertEquals("/api/music/pause", requestedPath)
    }

    @Test
    fun `test resume dispatches correctly`() {
        var requestedPath = ""
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                val reader = socket.getInputStream().bufferedReader()
                val requestLine = reader.readLine() ?: ""
                requestedPath = requestLine.split(" ")[1]
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val response = """{"success":true,"status":"PLAYING"}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        assertTrue(provider.resume())
        assertEquals("/api/music/resume", requestedPath)
    }

    @Test
    fun `test setVolume sends json percentage`() {
        var recordedBody = ""
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                val reader = socket.getInputStream().bufferedReader()
                var contentLength = 0
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.lowercase().startsWith("content-length:")) {
                        contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                    }
                    if (line.isEmpty()) break
                }
                if (contentLength > 0) {
                    val chars = CharArray(contentLength)
                    reader.read(chars, 0, contentLength)
                    recordedBody = String(chars)
                }

                val response = """{"success":true,"status":"PLAYING","volume":75}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        assertTrue(provider.setVolume(75))
        assertTrue(recordedBody.contains("75"))
    }

    @Test
    fun `test searchAndPlay handles daemon failure gracefully`() {
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                socket.getInputStream().bufferedReader().apply {
                    while (true) {
                        val line = readLine() ?: break
                        if (line.isEmpty()) break
                    }
                }
                val response = """{"success":false,"status":"FAILED","error":"Could not resolve track"}"""
                val bodyBytes = response.toByteArray(Charsets.UTF_8)
                val out = socket.getOutputStream()
                out.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bodyBytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.UTF_8))
                out.write(bodyBytes)
                out.flush()
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 1000,
            readTimeoutMs = 2000
        )

        val result = provider.searchAndPlay("UnknownTrack123", null)
        assertTrue(result is ProviderResult.Failed)
        assertEquals("Could not resolve track", (result as ProviderResult.Failed).reason)
    }

    @Test
    fun `test searchAndPlay handles network timeout gracefully without throwing`() {
        thread {
            try {
                val socket = serverSocket?.accept() ?: return@thread
                Thread.sleep(1500)
                socket.close()
            } catch (ignored: Exception) {}
        }

        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port,
            connectTimeoutMs = 200,
            readTimeoutMs = 200
        )

        val result = provider.searchAndPlay("Zara Zara", null)
        assertTrue(result is ProviderResult.Failed)
    }

    @Test
    fun `test supportsDirectPlayback is true`() {
        val provider = PcLocalMusicProvider(
            host = "127.0.0.1",
            port = port
        )
        assertTrue(provider.supportsDirectPlayback())
    }
}
