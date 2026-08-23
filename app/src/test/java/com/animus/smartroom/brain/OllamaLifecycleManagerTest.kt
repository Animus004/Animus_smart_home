package com.animus.smartroom.brain.provider

import com.animus.smartroom.core.brain.model.BrainState
import com.animus.smartroom.core.brain.model.LocalBrainConfig
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

class OllamaLifecycleManagerTest {

    private fun respond(socket: Socket, statusCode: Int, body: String, statusText: String = "OK") {
        val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
        var contentLength = 0
        while (true) {
            val line = reader.readLine() ?: break
            if (line.isEmpty()) break
            if (line.startsWith("Content-Length:", ignoreCase = true)) {
                contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
            }
        }
        if (contentLength > 0) {
            val buf = CharArray(contentLength)
            reader.read(buf, 0, contentLength)
        }
        val bytes = body.toByteArray(Charsets.UTF_8)
        val header = "HTTP/1.1 $statusCode $statusText\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\n\r\n"
        socket.getOutputStream().write(header.toByteArray(Charsets.UTF_8))
        socket.getOutputStream().write(bytes)
        socket.getOutputStream().flush()
        socket.close()
    }

    @Test
    fun `test OllamaLifecycleManager initial state is OFFLINE`() {
        val config = LocalBrainConfig(host = "127.0.0.1", port = 11434)
        val client = OllamaLocalLlmClient { config }
        val manager = OllamaLifecycleManager(client) { config }

        assertEquals(BrainState.OFFLINE, manager.state.value)
    }

    @Test
    fun `test OllamaLifecycleManager single-flight warmup transitions to READY`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort
        val warmupCount = AtomicInteger(0)

        val serverThread = thread {
            try {
                // Ping handler /v1/models
                val socket1 = server.accept()
                respond(socket1, 200, "{}")

                // Warmup handler /v1/chat/completions
                val socket2 = server.accept()
                warmupCount.incrementAndGet()
                respond(socket2, 200, """{"choices":[{"message":{"content":"READY"}}]}""")
            } catch (e: Exception) {
                // ignore
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 5000)
        val client = OllamaLocalLlmClient { config }
        val manager = OllamaLifecycleManager(client) { config }

        val ready = manager.ensureReady()
        assertTrue(ready)
        assertEquals(BrainState.READY, manager.state.value)
        assertEquals(1, warmupCount.get())

        serverThread.join(2000)
    }

    @Test
    fun `test OllamaLifecycleManager concurrent callers await single in-flight warmup`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort
        val requestCounter = AtomicInteger(0)

        val serverThread = thread {
            try {
                // Ping handler
                val socket1 = server.accept()
                respond(socket1, 200, "{}")

                // Single warmup handler with simulated delay
                val socket2 = server.accept()
                requestCounter.incrementAndGet()
                Thread.sleep(100)
                respond(socket2, 200, """{"choices":[{"message":{"content":"READY"}}]}""")
            } catch (e: Exception) {
                // ignore
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 5000)
        val client = OllamaLocalLlmClient { config }
        val manager = OllamaLifecycleManager(client) { config }

        // Launch 4 concurrent calls to ensureReady
        val jobs = (1..4).map {
            async { manager.ensureReady() }
        }
        val results = jobs.awaitAll()

        results.forEach { assertTrue(it) }
        assertEquals(BrainState.READY, manager.state.value)
        assertEquals(1, requestCounter.get())

        serverThread.join(2000)
    }

    @Test
    fun `test OllamaLifecycleManager transient 409 conflict retries and succeeds`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        val serverThread = thread {
            try {
                // 1. Ping
                val s1 = server.accept()
                respond(s1, 200, "{}")

                // 2. Warmup
                val s2 = server.accept()
                respond(s2, 200, """{"choices":[{"message":{"content":"READY"}}]}""")

                // 3. Inference Attempt 1: 409 Conflict
                val s3 = server.accept()
                respond(s3, 409, """{"error":"model is loading"}""", statusText = "Conflict")

                // 4. Inference Attempt 2: 200 Success
                val s4 = server.accept()
                respond(s4, 200, """{"choices":[{"message":{"content":"{\"type\":\"command\"}"}}]}""")
            } catch (e: Exception) {
                // ignore
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port, timeoutMs = 5000, warmupTimeoutMs = 5000)
        val client = OllamaLocalLlmClient { config }
        val manager = OllamaLifecycleManager(client) { config }

        val res = manager.executeInference("turn on AC")
        assertTrue(res.isSuccess)
        assertEquals("{\"type\":\"command\"}", res.getOrNull())

        serverThread.join(2000)
    }
}
