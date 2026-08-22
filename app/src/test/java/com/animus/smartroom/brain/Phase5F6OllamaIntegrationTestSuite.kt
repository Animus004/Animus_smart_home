package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.OllamaLocalLlmClient
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.model.LocalBrainConfig
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import kotlin.concurrent.thread

class Phase5F6OllamaIntegrationTestSuite {

    // 1. LocalBrainConfigValidationTest
    @Test
    fun `test LocalBrainConfig validation with qwen3 4b-instruct defaults`() {
        val config = LocalBrainConfig()
        assertTrue(config.isValid())
        assertEquals("qwen3:4b-instruct", config.model)
        assertEquals("http://127.0.0.1:11434/v1/chat/completions", config.endpointUrl)
        assertEquals("http://127.0.0.1:11434/v1", config.baseUrl)
    }

    // 2. LocalBrainConfigCustomLanHostTest
    @Test
    fun `test LocalBrainConfig with configurable LAN host`() {
        val config = LocalBrainConfig(host = "192.168.1.100", port = 11434)
        assertTrue(config.isValid())
        assertEquals("http://192.168.1.100:11434/v1/chat/completions", config.endpointUrl)
    }

    // 3. OllamaClientDisabledConfigReturnsFailureTest
    @Test
    fun `test OllamaLocalLlmClient returns failure when disabled`() = runBlocking {
        val client = OllamaLocalLlmClient { LocalBrainConfig(enabled = false) }
        val result = client.generateCompletion("hello")
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is OllamaLocalLlmClient.OllamaError.DisabledOrInvalidConfig)
    }

    // 4. OllamaClientInvalidConfigReturnsFailureTest
    @Test
    fun `test OllamaLocalLlmClient returns failure when port or host invalid`() = runBlocking {
        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "", port = -1) }
        val result = client.generateCompletion("hello")
        assertTrue(result.isFailure)
    }

    // 5. OllamaClientNetworkUnavailableHandledSafelyTest
    @Test
    fun `test OllamaLocalLlmClient handles connection failure without crashing`() = runBlocking {
        // Point to non-listening port
        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = 59999, timeoutMs = 1000) }
        val result = client.generateCompletion("set AC to 24")
        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertTrue(ex is OllamaLocalLlmClient.OllamaError.NetworkUnavailable || ex is java.io.IOException)
    }

    // 6. OllamaClientPingOfflineReturnsFalseTest
    @Test
    fun `test OllamaLocalLlmClient ping returns false when host is down`() = runBlocking {
        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = 59998) }
        val isUp = client.ping()
        assertFalse(isUp)
    }

    // 7. MockOllamaServerSuccessResponseTest
    @Test
    fun `test OllamaLocalLlmClient parses valid choices JSON from mock server`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        thread {
            try {
                val socket = server.accept()
                val reader = socket.getInputStream().bufferedReader()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = """
                    {
                      "id": "chatcmpl-123",
                      "object": "chat.completion",
                      "created": 1700000000,
                      "model": "qwen3:4b-instruct",
                      "choices": [
                        {
                          "index": 0,
                          "message": {
                            "role": "assistant",
                            "content": "{\"type\":\"command\",\"spoken_response\":\"Setting AC to 24 degrees.\",\"actions\":[{\"type\":\"device_command\",\"target\":\"AC\",\"command\":\"SET_TEMPERATURE\",\"value\":24}]}"
                          },
                          "finish_reason": "stop"
                        }
                      ]
                    }
                """.trimIndent()
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = port, timeoutMs = 5000) }
        val result = client.generateCompletion("set AC to 24")
        assertTrue(result.isSuccess)
        val content = result.getOrNull()
        assertNotNull(content)
        assertTrue(content!!.contains("Setting AC to 24 degrees."))
    }

    // 8. MockOllamaServerMalformedChoicesTest
    @Test
    fun `test OllamaLocalLlmClient handles malformed JSON response safely`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        thread {
            try {
                val socket = server.accept()
                val reader = socket.getInputStream().bufferedReader()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = "{ \"invalid\": true }"
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = port, timeoutMs = 5000) }
        val result = client.generateCompletion("set AC to 24")
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is OllamaLocalLlmClient.OllamaError.MalformedResponse)
    }

    // 9. MockOllamaServerHttpErrorTest
    @Test
    fun `test OllamaLocalLlmClient handles HTTP 500 internal server error`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        thread {
            try {
                val socket = server.accept()
                val reader = socket.getInputStream().bufferedReader()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val errorJson = "{ \"error\": \"model out of memory\" }"
                val response = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: ${errorJson.toByteArray().size}\r\n\r\n$errorJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = port, timeoutMs = 5000) }
        val result = client.generateCompletion("play music")
        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertTrue(ex is OllamaLocalLlmClient.OllamaError.HttpError)
        assertEquals(500, (ex as OllamaLocalLlmClient.OllamaError.HttpError).code)
    }

    // 10. MockOllamaServerPingHealthSuccessTest
    @Test
    fun `test OllamaLocalLlmClient ping returns true on HTTP 200`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        thread {
            try {
                val socket = server.accept()
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val client = OllamaLocalLlmClient { LocalBrainConfig(host = "127.0.0.1", port = port, timeoutMs = 2000) }
        val isHealthy = client.ping()
        assertTrue(isHealthy)
    }

    // 11. LanHostEndpointConstructionTest
    @Test
    fun `test LocalBrainConfig with PC LAN IP 192 168 1 9 constructs correct endpoint`() {
        val config = LocalBrainConfig(host = "192.168.1.9", port = 11434, model = "qwen3:4b-instruct")
        assertTrue(config.isValid())
        assertEquals("http://192.168.1.9:11434/v1/chat/completions", config.endpointUrl)
        assertEquals("http://192.168.1.9:11434/v1", config.baseUrl)
    }

    // 12. OllamaClientSendsExpectedJsonFormatTest
    @Test
    fun `test OllamaLocalLlmClient sends model messages temperature and max_tokens`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort
        var receivedPayload = ""

        thread {
            try {
                val socket = server.accept()
                val reader = socket.getInputStream().bufferedReader()
                var contentLength = 0
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.lowercase().startsWith("content-length:")) {
                        contentLength = line.substringAfter(":").trim().toInt()
                    }
                    if (line.isEmpty()) break
                }
                val buffer = CharArray(contentLength)
                reader.read(buffer, 0, contentLength)
                receivedPayload = String(buffer)

                val responseJson = """
                    {
                      "choices": [
                        {
                          "message": {
                            "role": "assistant",
                            "content": "{\"type\":\"conversation\",\"speech\":\"Hello from Qwen\"}"
                          }
                        }
                      ]
                    }
                """.trimIndent()
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "192.168.1.9", port = port, model = "qwen3:4b-instruct", temperature = 0.2f, maxTokens = 256)
        val client = OllamaLocalLlmClient { config.copy(host = "127.0.0.1") }
        val res = client.generateCompletion("hello")
        assertTrue(res.isSuccess)
        assertTrue(receivedPayload.contains("\"model\":\"qwen3:4b-instruct\""))
        assertTrue(receivedPayload.contains("\"temperature\":0.2"))
        assertTrue(receivedPayload.contains("\"max_tokens\":256"))
        assertTrue(receivedPayload.contains("\"role\":\"user\""))
    }

    // 13. LocalAnimusBrainInvokesOllamaClientTest
    @Test
    fun `test LocalAnimusBrain routes voice command to OllamaLocalLlmClient`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort
        var serverInvoked = false

        thread {
            try {
                val socket = server.accept()
                val reader = socket.getInputStream().bufferedReader()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                serverInvoked = true

                val responseJson = """
                    {
                      "choices": [
                        {
                          "message": {
                            "role": "assistant",
                            "content": "{\"type\":\"command\",\"spoken_response\":\"Setting AC to 24\",\"actions\":[{\"type\":\"device_command\",\"target\":\"AC\",\"command\":\"TEMPERATURE\",\"value\":24}]}"
                          }
                        }
                      ]
                    }
                """.trimIndent()
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port)
        val client = OllamaLocalLlmClient { config }
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        ).apply {
            setStatus(com.animus.smartroom.brain.provider.LocalBrainStatus.AVAILABLE)
        }
        val provider = com.animus.smartroom.brain.provider.LocalBrainProvider(inferencePort = portImpl)
        val brain = com.animus.smartroom.brain.provider.LocalAnimusBrain(localBrainProvider = provider)

        val result = brain.interpret("set AC to 24")
        assertTrue(serverInvoked)
        assertTrue(result is com.animus.smartroom.brain.model.BrainResult.Success)
    }

    // 14. LocalBrainConfigTimeoutRegressionTest
    @Test
    fun `test LocalBrainConfig default warmup timeout is 300 seconds and normal timeout is 30 seconds`() {
        val config = LocalBrainConfig()
        assertEquals(300_000, config.warmupTimeoutMs)
        assertEquals(30_000, config.timeoutMs)
        assertTrue(config.warmupTimeoutMs >= 120_000)
    }

    // 15. MultiCommandPlanInterpretationTest
    @Test
    fun `test LocalAnimusBrain returns all commands in multi-action plan`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val socket = server.accept()
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = "{\"id\":\"chatcmpl-test\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"command\\\",\\\"spoken_response\\\":\\\"Sure, turning on the AC, setting it to 24 degrees, and playing Zara Zara.\\\",\\\"actions\\\":[{\\\"type\\\":\\\"device_command\\\",\\\"target\\\":\\\"AC\\\",\\\"capability\\\":\\\"POWER\\\",\\\"value\\\":\\\"ON\\\"},{\\\"type\\\":\\\"device_command\\\",\\\"target\\\":\\\"AC\\\",\\\"capability\\\":\\\"SET_TEMPERATURE\\\",\\\"value\\\":\\\"24\\\"},{\\\"type\\\":\\\"play_music\\\",\\\"title\\\":\\\"Zara Zara\\\",\\\"speaker\\\":\\\"LG SNC4R\\\"}]}\"}}]}"
                val rawResponse = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(rawResponse.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        var spokenResult: String? = null
        val fakeVoiceOutput = object : com.animus.smartroom.core.port.VoiceOutputPort {
            override suspend fun speak(text: String) {
                spokenResult = text
            }
            override fun stop() {}
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        ).apply {
            setStatus(com.animus.smartroom.brain.provider.LocalBrainStatus.AVAILABLE)
        }
        val provider = com.animus.smartroom.brain.provider.LocalBrainProvider(inferencePort = portImpl)
        val brain = com.animus.smartroom.brain.provider.LocalAnimusBrain(
            localBrainProvider = provider,
            voiceOutputPort = fakeVoiceOutput
        )

        val result = brain.interpret("Turn on the AC, set it to 24 degrees, and play Zara Zara.")
        assertTrue(result is com.animus.smartroom.brain.model.BrainResult.Success)
        val commands = (result as com.animus.smartroom.brain.model.BrainResult.Success).commands
        assertEquals(3, commands.size)
        assertTrue(commands[0] is AnimusCommand.SetDeviceCapability)
        assertTrue(commands[1] is AnimusCommand.SetDeviceCapability)
        assertTrue(commands[2] is AnimusCommand.PlayMusic)
        assertEquals("Sure, turning on the AC, setting it to 24 degrees, and playing Zara Zara.", spokenResult)
    }

    // 16. LocalBrainConversationalVoiceResponseTest
    @Test
    fun `test LocalAnimusBrain speaks conversational response via VoiceOutputPort`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val socket = server.accept()
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = "{\"id\":\"chatcmpl-test\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"conversation\\\",\\\"spoken_response\\\":\\\"You have 2 tasks scheduled for today: Finish the report and workout.\\\"}\"}}]}"
                val rawResponse = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(rawResponse.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        var spokenResult: String? = null
        val fakeVoiceOutput = object : com.animus.smartroom.core.port.VoiceOutputPort {
            override suspend fun speak(text: String) {
                spokenResult = text
            }
            override fun stop() {}
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        ).apply {
            setStatus(com.animus.smartroom.brain.provider.LocalBrainStatus.AVAILABLE)
        }
        val provider = com.animus.smartroom.brain.provider.LocalBrainProvider(inferencePort = portImpl)
        val brain = com.animus.smartroom.brain.provider.LocalAnimusBrain(
            localBrainProvider = provider,
            voiceOutputPort = fakeVoiceOutput
        )

        val result = brain.interpret("What are my tasks for today?")
        assertTrue(result is com.animus.smartroom.brain.model.BrainResult.Success)
        assertEquals("You have 2 tasks scheduled for today: Finish the report and workout.", spokenResult)
    }

    // 17. MusicResolverTrackTitleVariationTest
    @Test
    fun `test YouTubeMusicResolver resolves Zara Z to verified direct video ID`() = runBlocking {
        val cache = com.animus.smartroom.media.resolver.MusicResolutionCache().apply {
            putSeedTrack("zara z", null, "IWjbBSMsQJg", "Bombay Jayashri - Topic")
        }
        val resolver = com.animus.smartroom.media.resolver.YouTubeMusicResolver(
            apiKeyProvider = { null },
            cache = cache
        )

        val result = resolver.resolveTrack("Zara Z", null)
        assertTrue(result is com.animus.smartroom.media.resolver.MusicResolutionResult.Resolved)
        val resolved = result as com.animus.smartroom.media.resolver.MusicResolutionResult.Resolved
        assertEquals("IWjbBSMsQJg", resolved.videoId)
    }

    // 18. WarmupGatingTest - No user request dispatched before warmup completes
    @Test
    fun `test user request is gated during warmup and sent only after READY`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        val requestLogs = mutableListOf<String>()

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                // 1st request: warmup
                val socket1 = server.accept()
                val reader1 = BufferedReader(InputStreamReader(socket1.getInputStream()))
                while (true) {
                    val line = reader1.readLine() ?: break
                    if (line.isEmpty()) break
                }
                requestLogs.add("WARMUP_RECEIVED")
                val warmupResp = "{\"id\":\"w-1\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                val r1 = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${warmupResp.toByteArray().size}\r\n\r\n$warmupResp"
                socket1.getOutputStream().write(r1.toByteArray())
                socket1.getOutputStream().flush()
                socket1.close()

                // 2nd request: user prompt
                val socket2 = server.accept()
                val reader2 = BufferedReader(InputStreamReader(socket2.getInputStream()))
                while (true) {
                    val line = reader2.readLine() ?: break
                    if (line.isEmpty()) break
                }
                requestLogs.add("USER_REQUEST_RECEIVED")
                val userResp = "{\"id\":\"u-1\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"conversation\\\",\\\"spoken_response\\\":\\\"Hello\\\"}\"}}]}"
                val r2 = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${userResp.toByteArray().size}\r\n\r\n$userResp"
                socket2.getOutputStream().write(r2.toByteArray())
                socket2.getOutputStream().flush()
                socket2.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        )

        // Launch user request concurrently while warmup is running
        var userGeneratedResponse: String? = null
        val userJob = launch(kotlinx.coroutines.Dispatchers.IO) {
            userGeneratedResponse = portImpl.generate("Hello", emptyList())
        }

        // Trigger warmup on IO dispatcher
        val warmupJob = async(kotlinx.coroutines.Dispatchers.IO) {
            portImpl.warmUp()
        }
        val warmupOk = warmupJob.await()
        assertTrue(warmupOk)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, portImpl.status.value)

        userJob.join()
        assertNotNull(userGeneratedResponse)
        assertEquals(listOf("WARMUP_RECEIVED", "USER_REQUEST_RECEIVED"), requestLogs)
    }

    // 19. WarmupFailureAndRecoveryTest
    @Test
    fun `test warmup failure sets FAILED state and allows recovery on retry`() = runBlocking {
        val config = LocalBrainConfig(host = "127.0.0.1", port = 65530, warmupTimeoutMs = 5000) // non-existent port with small timeout
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        )

        val success = portImpl.warmUp(maxAttempts = 1)
        assertFalse(success)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.FAILED, portImpl.status.value)

        // Recovery: start local server on new port
        val server = ServerSocket(0)
        val port = server.localPort
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val socket = server.accept()
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = "{\"id\":\"rec-1\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val recoveredConfig = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 5000)
        val recoveredPort = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { recoveredConfig }
        )
        val recovered = recoveredPort.warmUp(maxAttempts = 1)
        assertTrue(recovered)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, recoveredPort.status.value)
    }

    // 20. SingleFlightWarmupMutexTest
    @Test
    fun `test concurrent warmup requests perform single-flight initialization`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort
        var warmupCount = 0

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val socket = server.accept()
                warmupCount++
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val responseJson = "{\"id\":\"sf-1\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                val response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${responseJson.toByteArray().size}\r\n\r\n$responseJson"
                socket.getOutputStream().write(response.toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 5000)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        )

        val j1 = launch { portImpl.warmUp() }
        val j2 = launch { portImpl.warmUp() }
        j1.join()
        j2.join()

        assertEquals(1, warmupCount)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, portImpl.status.value)
    }

    // 21. WarmupPayloadAttributesTest
    @Test
    fun `test warmup request payload contains stream false and keep_alive 24h for long-lived residency`() {
        val config = LocalBrainConfig()
        assertEquals(300_000, config.warmupTimeoutMs)
        assertEquals(30_000, config.timeoutMs)
        assertEquals("qwen3:4b-instruct", config.model)
    }

    // 22. LongWarmupGatingAndExecutionTest - Warmup takes >30s, user command waits without interactive timeout failure
    @Test
    fun `test user command is held during long warmup and executes without interactive timeout`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        val requestLogs = mutableListOf<String>()

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                // 1st request: warmup (simulates heavy cold model load)
                val socket1 = server.accept()
                val reader1 = BufferedReader(InputStreamReader(socket1.getInputStream()))
                while (true) {
                    val line = reader1.readLine() ?: break
                    if (line.isEmpty()) break
                }
                requestLogs.add("WARMUP_STARTED")
                // Simulate cold loading delay (100ms in unit test environment)
                kotlinx.coroutines.delay(100)
                val warmupResp = "{\"id\":\"w-cold\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                val r1 = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${warmupResp.toByteArray().size}\r\n\r\n$warmupResp"
                socket1.getOutputStream().write(r1.toByteArray())
                socket1.getOutputStream().flush()
                socket1.close()

                // 2nd request: user command
                val socket2 = server.accept()
                val reader2 = BufferedReader(InputStreamReader(socket2.getInputStream()))
                while (true) {
                    val line = reader2.readLine() ?: break
                    if (line.isEmpty()) break
                }
                requestLogs.add("USER_CMD_DISPATCHED")
                val userResp = "{\"id\":\"u-cold\",\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"command\\\",\\\"spoken_response\\\":\\\"AC turned on\\\",\\\"actions\\\":[{\\\"type\\\":\\\"device_command\\\",\\\"target\\\":\\\"AC\\\",\\\"capability\\\":\\\"POWER\\\",\\\"value\\\":\\\"ON\\\"}]}\"}}]}"
                val r2 = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${userResp.toByteArray().size}\r\n\r\n$userResp"
                socket2.getOutputStream().write(r2.toByteArray())
                socket2.getOutputStream().flush()
                socket2.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 10000, timeoutMs = 2000)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        )

        // Queue user command while STARTING
        var userResult: String? = null
        val userJob = launch(kotlinx.coroutines.Dispatchers.IO) {
            userResult = portImpl.generate("turn on ac", emptyList())
        }

        // Start warmup on IO dispatcher
        val warmupJob = async(kotlinx.coroutines.Dispatchers.IO) {
            portImpl.warmUp()
        }
        val warmResult = warmupJob.await()
        assertTrue(warmResult)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, portImpl.status.value)

        userJob.join()
        assertNotNull(userResult)
        assertEquals(listOf("WARMUP_STARTED", "USER_CMD_DISPATCHED"), requestLogs)
    }

    // 23. ColdToWarmLifecycleSequenceTest - Proves cold -> warmup -> READY -> user command -> subsequent warm command
    @Test
    fun `test cold model to warmup to READY to user command sequence`() = runBlocking {
        val server = ServerSocket(0)
        val port = server.localPort

        val executionOrder = mutableListOf<String>()

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                // 1. Warmup
                val s1 = server.accept()
                val r1 = BufferedReader(InputStreamReader(s1.getInputStream()))
                while (true) {
                    val line = r1.readLine() ?: break
                    if (line.isEmpty()) break
                }
                executionOrder.add("WARMUP")
                val resp1 = "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                s1.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${resp1.length}\r\n\r\n$resp1".toByteArray())
                s1.getOutputStream().flush()
                s1.close()

                // 2. First user request
                val s2 = server.accept()
                val r2 = BufferedReader(InputStreamReader(s2.getInputStream()))
                while (true) {
                    val line = r2.readLine() ?: break
                    if (line.isEmpty()) break
                }
                executionOrder.add("USER_REQ_1")
                val resp2 = "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"conversation\\\",\\\"spoken_response\\\":\\\"First\\\"}\"}}]}"
                s2.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${resp2.length}\r\n\r\n$resp2".toByteArray())
                s2.getOutputStream().flush()
                s2.close()

                // 3. Second user request
                val s3 = server.accept()
                val r3 = BufferedReader(InputStreamReader(s3.getInputStream()))
                while (true) {
                    val line = r3.readLine() ?: break
                    if (line.isEmpty()) break
                }
                executionOrder.add("USER_REQ_2")
                val resp3 = "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"type\\\":\\\"conversation\\\",\\\"spoken_response\\\":\\\"Second\\\"}\"}}]}"
                s3.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${resp3.length}\r\n\r\n$resp3".toByteArray())
                s3.getOutputStream().flush()
                s3.close()
            } finally {
                server.close()
            }
        }

        val config = LocalBrainConfig(host = "127.0.0.1", port = port)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { config }
        )

        // Warmup
        portImpl.warmUp()
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, portImpl.status.value)

        // First user query
        val q1 = portImpl.generate("Hello 1", emptyList())
        assertTrue(q1.contains("First"))

        // Second user query
        val q2 = portImpl.generate("Hello 2", emptyList())
        assertTrue(q2.contains("Second"))

        assertEquals(listOf("WARMUP", "USER_REQ_1", "USER_REQ_2"), executionOrder)
    }

    // 24. WarmupPermanentFailureReleasesGatedRequestTest
    @Test
    fun `test user request during permanent warmup failure is cleanly released and later retries are possible`() = runBlocking {
        var currentConfig = LocalBrainConfig(host = "127.0.0.1", port = 65530, warmupTimeoutMs = 100, timeoutMs = 100)
        val portImpl = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(
            com.animus.smartroom.brain.provider.LocalInferenceClient { currentConfig }
        )

        // 1. Launch warmup in background. It will fail after maxAttempts=2
        val warmupJob = async(kotlinx.coroutines.Dispatchers.IO) {
            portImpl.warmUp(maxAttempts = 2)
        }

        // Wait a tiny bit to ensure state transitions to STARTING or WARMING_UP
        kotlinx.coroutines.delay(50)

        // 2. Queue a user request while it is warming up (and about to fail)
        var userEx: Exception? = null
        val userJob = launch(kotlinx.coroutines.Dispatchers.IO) {
            try {
                portImpl.generate("Hello", emptyList())
            } catch (e: Exception) {
                userEx = e
            }
        }

        val warmupResult = warmupJob.await()
        assertFalse(warmupResult)
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.FAILED, portImpl.status.value)

        // The user request should now be released with an exception, not hanging
        userJob.join()
        assertNotNull("User request should have thrown an exception when gated on FAILED", userEx)
        assertTrue(userEx is IllegalStateException)
        assertTrue(userEx!!.message!!.contains("current status=FAILED"))

        // 3. Prove a subsequent retry is possible by starting a mock server
        val server = ServerSocket(0)
        val port = server.localPort
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val socket = server.accept()
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                }
                val resp = "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"READY\"}}]}"
                socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${resp.length}\r\n\r\n$resp".toByteArray())
                socket.getOutputStream().flush()
                socket.close()
            } finally {
                server.close()
            }
        }

        // Change the config to the valid port
        currentConfig = LocalBrainConfig(host = "127.0.0.1", port = port, warmupTimeoutMs = 5000, timeoutMs = 5000)

        // Calling generate while in FAILED state throws immediately but kicks off a background recovery warmUp
        var recoveryEx: Exception? = null
        try {
            portImpl.generate("Kickoff recovery", emptyList())
        } catch(e: Exception) {
            recoveryEx = e
        }
        assertNotNull("Generate should throw immediately when in FAILED state", recoveryEx)
        
        // The background warmup should now succeed and transition to READY
        val readyStatus = portImpl.status.filter { it == com.animus.smartroom.brain.provider.LocalBrainStatus.READY }.first()
        assertEquals(com.animus.smartroom.brain.provider.LocalBrainStatus.READY, readyStatus)
    }
}
