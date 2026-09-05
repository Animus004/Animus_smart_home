package com.animus.smartroom.brain.client

import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.AgentInteractionResponseDto
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.brain.provider.RemotePhaseFBrain
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.port.VoiceOutputPort
import com.animus.smartroom.runtime.RuntimeControlPortImpl
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentApiRemoteClientTest {

    @Test
    fun testDtoParsingValidResponse() {
        val jsonStr = """
            {
                "understood_intent": "TASK_SCHEDULE_QUERY",
                "agent_message": "Here is what you have completed today, buddy:\n- Review window functions",
                "action_taken": false,
                "deterministic_preparation_done": false,
                "followup_required": false,
                "followup_question": null,
                "timestamp": 1787654400.0
            }
        """.trimIndent()

        val json = JSONObject(jsonStr)
        val dto = AgentInteractionResponseDto.fromJson(json)

        assertEquals("TASK_SCHEDULE_QUERY", dto.understoodIntent)
        assertEquals("Here is what you have completed today, buddy:\n- Review window functions", dto.agentMessage)
        assertFalse(dto.actionTaken)
        assertFalse(dto.followupRequired)
        assertNull(dto.followupQuestion)
    }

    @Test
    fun testDtoParsingFollowupRequired() {
        val jsonStr = """
            {
                "understood_intent": "UNCERTAIN_DISAMBIGUATION",
                "agent_message": "25 what — volume, AC temperature, or something else, buddy?",
                "action_taken": false,
                "deterministic_preparation_done": false,
                "followup_required": true,
                "followup_question": "25 what — volume, AC temperature, or something else, buddy?",
                "timestamp": 1787654400.0
            }
        """.trimIndent()

        val json = JSONObject(jsonStr)
        val dto = AgentInteractionResponseDto.fromJson(json)

        assertEquals("UNCERTAIN_DISAMBIGUATION", dto.understoodIntent)
        assertTrue(dto.followupRequired)
        assertEquals("25 what — volume, AC temperature, or something else, buddy?", dto.followupQuestion)
    }

    @Test
    fun testBlankUtteranceFailsFast() = runBlocking {
        val client = AgentApiRemoteClient()
        val res = client.interact("   ")
        assertTrue(res is BrainResult.Failure)
        assertEquals("Utterance was blank", (res as BrainResult.Failure).errorMessage)
    }

    @Test
    fun testRemotePhaseFBrainRoutingInManager() = runBlocking {
        val fakeRemoteBrain = object : AnimusBrain {
            override val providerType = BrainProviderType.REMOTE_PHASE_F
            override suspend fun interpret(input: String): BrainResult {
                return BrainResult.RemoteAgentSuccess(
                    agentMessage = "Setting AC to 24, buddy.",
                    understoodIntent = "CLIMATE_ADJUSTMENT",
                    actionTaken = true,
                    followupRequired = false,
                    followupQuestion = null
                )
            }
        }

        val manager = AnimusBrainManager(
            localBrain = LocalAnimusBrain(),
            cloudBrain = CloudAnimusBrain(),
            remotePhaseFBrain = fakeRemoteBrain,
            initialProvider = BrainProviderType.REMOTE_PHASE_F
        )

        assertEquals(BrainProviderType.REMOTE_PHASE_F, manager.providerType)
        val result = manager.interpret("set ac to 24")
        assertTrue(result is BrainResult.RemoteAgentSuccess)
        val success = result as BrainResult.RemoteAgentSuccess
        assertEquals("Setting AC to 24, buddy.", success.agentMessage)
        assertEquals("CLIMATE_ADJUSTMENT", success.understoodIntent)
        assertTrue(success.actionTaken)
    }

    @Test
    fun testRollbackToLocalBrain() = runBlocking {
        val fakeRemote = object : AnimusBrain {
            override val providerType = BrainProviderType.REMOTE_PHASE_F
            override suspend fun interpret(input: String): BrainResult = BrainResult.Failure("Backend down")
        }

        val manager = AnimusBrainManager(
            localBrain = LocalAnimusBrain(),
            cloudBrain = CloudAnimusBrain(),
            remotePhaseFBrain = fakeRemote,
            initialProvider = BrainProviderType.REMOTE_PHASE_F
        )

        // Switch to LOCAL for rollback
        manager.setProvider(BrainProviderType.LOCAL)
        assertEquals(BrainProviderType.LOCAL, manager.providerType)

        val res = manager.interpret("pause")
        assertTrue(res is BrainResult.Success)
        assertEquals(AnimusCommand.PauseMusic, (res as BrainResult.Success).command)
    }

    @Test
    fun testRuntimeControlPortSpeaksRemoteMessageWithoutLocalDuplicateExecution() = runBlocking {
        var spokenMessage: String? = null
        val fakeVoiceOutput = object : VoiceOutputPort {
            override suspend fun speak(text: String) {
                spokenMessage = text
            }
            override fun stop() {}
            override fun isSpeaking(): Boolean = false
        }

        val fakeRemoteBrain = object : AnimusBrain {
            override val providerType = BrainProviderType.REMOTE_PHASE_F
            override suspend fun interpret(input: String): BrainResult {
                return BrainResult.RemoteAgentSuccess(
                    agentMessage = "Good morning, buddy!",
                    understoodIntent = "MORNING_ROUTINE_BRIEF",
                    actionTaken = false
                )
            }
        }

        val manager = AnimusBrainManager(
            remotePhaseFBrain = fakeRemoteBrain,
            initialProvider = BrainProviderType.REMOTE_PHASE_F
        )

        val fakeStore = com.animus.smartroom.core.port.FakePersistentStore()
        val storage = com.animus.smartroom.scheduler.storage.ScheduledActionStorage(fakeStore)
        val clock = com.animus.smartroom.core.port.SystemClock()

        val port = RuntimeControlPortImpl(
            brainManager = manager,
            commandRouter = CommandRouter(),
            deviceSchedulerEngine = DeviceSchedulerEngine(storage = storage, clock = clock),
            voiceOutputPort = fakeVoiceOutput
        )

        val res = port.submitCommand("Buddy, I'm up.")
        assertTrue(res is BrainResult.RemoteAgentSuccess)
        assertEquals("Good morning, buddy!", spokenMessage)
    }

    @Test
    fun testDynamicHostProviderResolution() {
        var currentIp = "192.168.1.9"
        val client = AgentApiRemoteClient(hostProvider = { currentIp })
        assertEquals("http://192.168.1.9:8095", client.baseUrl)

        currentIp = "192.168.1.15"
        assertEquals("http://192.168.1.15:8095", client.baseUrl)
    }

    @Test
    fun testDefaultHostProviderResolution() {
        val client = AgentApiRemoteClient()
        assertEquals("http://192.168.1.4:8095", client.baseUrl)
    }
}
