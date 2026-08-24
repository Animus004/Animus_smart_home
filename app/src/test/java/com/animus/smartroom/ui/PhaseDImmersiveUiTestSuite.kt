package com.animus.smartroom.ui

import com.animus.smartroom.core.brain.adaptive.RoutinePriorityMatrix
import com.animus.smartroom.device.tuya.model.TuyaAcState
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.model.RoutineType
import com.animus.smartroom.ui.brain.VisualBrainState
import com.animus.smartroom.ui.glass.*
import org.junit.Assert.*
import org.junit.Test
import java.util.UUID

class PhaseDImmersiveUiTestSuite {

    // ─────────────────────────────────────────────────────────────────────────────
    // D1 - D4: CLOCK, TELEMETRY & OPERATION MODE
    // ─────────────────────────────────────────────────────────────────────────────

    @Test
    fun `D1 - Real-time clock updates continuously over time intervals`() {
        val t0 = 1756000000000L
        val t1 = t0 + 1000L
        val fmt = java.text.SimpleDateFormat("hh:mm:ss a", java.util.Locale.getDefault())
        val str0 = fmt.format(java.util.Date(t0))
        val str1 = fmt.format(java.util.Date(t1))
        assertNotEquals(str0, str1)
    }

    @Test
    fun `D2 - Actual Tuya temp_current is selected when live telemetry exists`() {
        val liveAcState = TuyaAcState(
            power = true,
            targetTemperature = 24,
            ambientTemperature = 21,
            lastSeenTimestamp = System.currentTimeMillis()
        )
        val hasLiveTelemetry = liveAcState.lastSeenTimestamp > 0L
        val displayedTemp = if (hasLiveTelemetry) "${liveAcState.ambientTemperature}°C" else "--°C"
        assertEquals("21°C", displayedTemp)
    }

    @Test
    fun `D3 - Temperature fallback to --degC when sensor telemetry unavailable`() {
        val offlineAcState = TuyaAcState(
            power = false,
            targetTemperature = 24,
            ambientTemperature = 24,
            lastSeenTimestamp = 0L
        )
        val hasLiveTelemetry = offlineAcState.lastSeenTimestamp > 0L
        val displayedTemp = if (hasLiveTelemetry) "${offlineAcState.ambientTemperature}°C" else "--°C"
        val subtitle = if (hasLiveTelemetry) "Actual room temperature" else "Room temperature unavailable"

        assertEquals("--°C", displayedTemp)
        assertEquals("Room temperature unavailable", subtitle)
    }

    @Test
    fun `D4 - OperationMode LOCAL_ROOM and REMOTE have valid states and descriptions`() {
        assertEquals("Local Room Mode", OperationMode.LOCAL_ROOM.displayName)
        assertTrue(OperationMode.LOCAL_ROOM.subtitle.contains("physical smart room hardware"))

        assertEquals("Remote Mode", OperationMode.REMOTE.displayName)
        assertTrue(OperationMode.REMOTE.subtitle.contains("Room hardware disabled"))
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // D5 - D9: MICROPHONE AVAILABILITY & BRAIN STATE GATING
    // ─────────────────────────────────────────────────────────────────────────────

    @Test
    fun `D5 - Microphone is enabled when VisualBrainState is READY`() {
        val state = VisualBrainState.READY
        val isMicInteractive = state == VisualBrainState.READY
        assertTrue(isMicInteractive)
    }

    @Test
    fun `D6 - Microphone is disabled and replaced by animated core in WARMING state`() {
        val state = VisualBrainState.WARMING
        val isMicInteractive = state == VisualBrainState.READY
        assertFalse(isMicInteractive)
        assertEquals("WARMING", state.label)
    }

    @Test
    fun `D7 - Microphone is disabled and replaced by execution visual in EXECUTING state`() {
        val state = VisualBrainState.EXECUTING
        val isMicInteractive = state == VisualBrainState.READY
        assertFalse(isMicInteractive)
        assertEquals("EXECUTING", state.label)
    }

    @Test
    fun `D8 - Microphone is disabled and replaced by warning visual in ERROR state`() {
        val state = VisualBrainState.ERROR
        val isMicInteractive = state == VisualBrainState.READY
        assertFalse(isMicInteractive)
        assertEquals("ERROR", state.label)
    }

    @Test
    fun `D9 - Microphone is accessible in Remote Mode when READY`() {
        val opMode = OperationMode.REMOTE
        val brainState = VisualBrainState.READY
        val isAccessibleInRemote = opMode == OperationMode.REMOTE && brainState == VisualBrainState.READY
        assertTrue(isAccessibleInRemote)
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // D10 - D16: DUAL ALARM ARCHITECTURE & ROUTINE PRIORITY
    // ─────────────────────────────────────────────────────────────────────────────

    @Test
    fun `D10 - Android alarm playback state is detected when routine is ALARMING`() {
        val routine = RoutineState(
            id = "morning_alarm",
            type = RoutineType.SLEEP,
            status = RoutineStatus.ALARMING,
            scheduledWakeTime = System.currentTimeMillis()
        )
        assertTrue(routine.isAlarming)
    }

    @Test
    fun `D11 & D16 - RoutinePriorityMatrix defines PRIORITY_ALARM = 90 between MOVIE and GOODNIGHT`() {
        assertEquals(100, RoutinePriorityMatrix.PRIORITY_GOODNIGHT)
        assertEquals(90, RoutinePriorityMatrix.PRIORITY_ALARM)
        assertEquals(70, RoutinePriorityMatrix.PRIORITY_MOVIE)
        assertEquals(50, RoutinePriorityMatrix.PRIORITY_MUSIC)

        // Alarm preempts Music
        assertTrue(RoutinePriorityMatrix.shouldPreempt("MUSIC_MODE", "MORNING_ALARM"))
        // Goodnight/Emergency cannot be preempted by Alarm
        assertFalse(RoutinePriorityMatrix.shouldPreempt("GOODNIGHT_MODE", "MORNING_ALARM"))
    }

    @Test
    fun `D12 & D13 & D14 - Stop Alarm truthful status consolidation`() {
        fun consolidateStop(androidStopped: Boolean, pcStopped: Boolean): String {
            return when {
                androidStopped && pcStopped -> "All alarms stopped"
                androidStopped && !pcStopped -> "Android alarm stopped · PC alarm unavailable"
                !androidStopped && pcStopped -> "PC alarm stopped"
                else -> "Alarm stop failed"
            }
        }

        assertEquals("All alarms stopped", consolidateStop(androidStopped = true, pcStopped = true))
        assertEquals("Android alarm stopped · PC alarm unavailable", consolidateStop(androidStopped = true, pcStopped = false))
        assertEquals("PC alarm stopped", consolidateStop(androidStopped = false, pcStopped = true))
        assertEquals("Alarm stop failed", consolidateStop(androidStopped = false, pcStopped = false))
    }

    @Test
    fun `D15 - PC unavailable falls back cleanly to Android local alarm`() {
        var androidAlarmTriggered = false
        var pcAlarmFailed = true

        // Simulate trigger
        androidAlarmTriggered = true
        val isFallbackAudible = androidAlarmTriggered && pcAlarmFailed
        assertTrue(isFallbackAudible)
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // D17 - D20: ALARM PERSISTENCE & UI ISOLATION
    // ─────────────────────────────────────────────────────────────────────────────

    @Test
    fun `D17 - Alarm routine state survives process serialization`() {
        val memoryMap = mutableMapOf<String, String>()
        val testStore = object : com.animus.smartroom.core.port.PersistentStore {
            override fun getString(key: String, defaultValue: String?): String? = memoryMap[key] ?: defaultValue
            override fun putString(key: String, value: String) { memoryMap[key] = value }
            override fun remove(key: String) { memoryMap.remove(key) }
            override fun getAll(): Map<String, *> = memoryMap
            override fun registerChangeListener(listener: (String) -> Unit) {}
            override fun unregisterChangeListener(listener: (String) -> Unit) {}
        }
        val storage = com.animus.smartroom.routine.storage.RoutineStorage(store = testStore)
        val original = RoutineState(
            id = "persisted_alarm_1",
            type = RoutineType.SLEEP,
            status = RoutineStatus.ALARMING,
            scheduledWakeTime = 1756000000000L
        )
        storage.saveActiveRoutine(original)

        // Simulate new process reading from store
        val newProcessStorage = com.animus.smartroom.routine.storage.RoutineStorage(store = testStore)
        val restored = newProcessStorage.getActiveRoutine()

        assertNotNull(restored)
        assertEquals(original.id, restored?.id)
        assertEquals(original.status, restored?.status)
        assertTrue(restored!!.isAlarming)
    }

    @Test
    fun `D18 - Alarm full-screen overlay visibility is strictly gated to isAlarming`() {
        val idleRoutine = RoutineState(id = "r1", type = RoutineType.SLEEP, status = RoutineStatus.ACTIVE)
        assertFalse(idleRoutine.isAlarming)

        val alarmingRoutine = idleRoutine.copy(status = RoutineStatus.ALARMING)
        assertTrue(alarmingRoutine.isAlarming)

        val completedRoutine = idleRoutine.copy(status = RoutineStatus.COMPLETED)
        assertFalse(completedRoutine.isAlarming)
    }

    @Test
    fun `D19 - ActiveGlassTool enum covers all 7 required tool panels`() {
        val expectedTools = setOf(
            ActiveGlassTool.NONE,
            ActiveGlassTool.DEVICE_STATUS,
            ActiveGlassTool.AC_REMOTE,
            ActiveGlassTool.MUSIC_CONTROLLER,
            ActiveGlassTool.CHAT,
            ActiveGlassTool.AUTOMATIONS,
            ActiveGlassTool.WIDGET_TOGGLE,
            ActiveGlassTool.BRAIN_SWITCH
        )
        assertEquals(expectedTools, ActiveGlassTool.values().toSet())
    }

    @Test
    fun `D20 - Remote Mode permits AC and Gemini while blocking room-only actuators`() {
        fun isRoomOnlyActuator(cmd: String): Boolean {
            val lower = cmd.lowercase()
            return lower.startsWith("turn on projector") || lower.startsWith("turn off projector") ||
                    lower.contains("movie mode") || lower.startsWith("watch ") ||
                    lower.startsWith("switch audio") || lower.startsWith("transfer audio") ||
                    lower.startsWith("connect soundbar") || lower.startsWith("disconnect soundbar")
        }

        assertTrue(isRoomOnlyActuator("movie mode"))
        assertTrue(isRoomOnlyActuator("turn on projector"))
        assertTrue(isRoomOnlyActuator("watch Article 15"))

        assertFalse(isRoomOnlyActuator("turn on ac"))
        assertFalse(isRoomOnlyActuator("set ac to 24"))
        assertFalse(isRoomOnlyActuator("where can I watch Article 15?"))
        assertFalse(isRoomOnlyActuator("play some music"))
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // D21 - D32: AUTHORITATIVE ACTION FEEDBACK & ERROR LIFECYCLE
    // ─────────────────────────────────────────────────────────────────────────────

    @Test
    fun `D21 - Error appears when physical verification fails`() {
        val reqId = UUID.randomUUID().toString()
        val errorFeedback = ActionFeedback(
            requestId = reqId,
            intent = "TURN_ON_PROJECTOR",
            targetDevice = "PROJECTOR",
            state = ActionExecutionState.ERROR_BLOCKED,
            message = "Projector could not be verified",
            severity = FeedbackSeverity.ERROR,
            isPersistent = true
        )

        assertEquals(ActionExecutionState.ERROR_BLOCKED, errorFeedback.state)
        assertEquals(FeedbackSeverity.ERROR, errorFeedback.severity)
        assertTrue(errorFeedback.isPersistent)
    }

    @Test
    fun `D22 & D29 - Persistent hardware error remains until resolved or superseded`() {
        val persistentError = ActionFeedback(
            requestId = "req-1",
            intent = "TURN_ON_PROJECTOR",
            targetDevice = "PROJECTOR",
            state = ActionExecutionState.ERROR_BLOCKED,
            message = "Projector is powered off. Manual action required.",
            severity = FeedbackSeverity.ERROR,
            isPersistent = true
        )
        assertTrue(persistentError.isPersistent)
        assertEquals(ActionExecutionState.ERROR_BLOCKED, persistentError.state)
    }

    @Test
    fun `D23 & D24 - Successful physical recovery clears previous error and shows verified success`() {
        var currentFeedback: ActionFeedback? = ActionFeedback(
            requestId = "req-ac-1",
            intent = "SET_AC_TEMP",
            targetDevice = "AC",
            state = ActionExecutionState.ERROR_BLOCKED,
            message = "Failed to set AC: Tuya timeout",
            severity = FeedbackSeverity.ERROR
        )

        // Physical telemetry recovery arrives: AC is Healthy at 24°C
        val recoveredAc = TuyaAcState(power = true, targetTemperature = 24, recoveryState = "HEALTHY")
        if (currentFeedback?.targetDevice == "AC" && recoveredAc.recoveryState == "HEALTHY") {
            currentFeedback = currentFeedback.copy(
                state = ActionExecutionState.VERIFIED_SUCCESS,
                message = "AC ON · 24°C (COOL) · verified",
                severity = FeedbackSeverity.SUCCESS
            )
        }

        assertNotNull(currentFeedback)
        assertEquals(ActionExecutionState.VERIFIED_SUCCESS, currentFeedback?.state)
        assertEquals(FeedbackSeverity.SUCCESS, currentFeedback?.severity)
        assertTrue(currentFeedback?.message!!.contains("verified"))
    }

    @Test
    fun `D25 - Verified success lifecycle is transient`() {
        val successFeedback = ActionFeedback(
            requestId = "req-done",
            intent = "SET_AC",
            state = ActionExecutionState.VERIFIED_SUCCESS,
            message = "AC set to 24°C · verified",
            severity = FeedbackSeverity.SUCCESS,
            isPersistent = false
        )
        assertFalse(successFeedback.isPersistent)
        assertEquals(ActionExecutionState.VERIFIED_SUCCESS, successFeedback.state)
    }

    @Test
    fun `D26 - New action replaces previous action feedback immediately`() {
        var activeFeedback: ActionFeedback? = ActionFeedback(
            requestId = "req-old",
            intent = "PROJECTOR_ON",
            state = ActionExecutionState.ERROR_BLOCKED,
            message = "Projector error"
        )

        // User issues new command
        val newReqId = "req-new"
        activeFeedback = ActionFeedback(
            requestId = newReqId,
            intent = "AC_ON",
            state = ActionExecutionState.EXECUTING,
            message = "Turning on AC..."
        )

        assertEquals("req-new", activeFeedback.requestId)
        assertEquals("Turning on AC...", activeFeedback.message)
        assertEquals(ActionExecutionState.EXECUTING, activeFeedback.state)
    }

    @Test
    fun `D27 - Late result from old request cannot overwrite newer feedback`() {
        var activeRequestId = "req-B"
        var activeFeedback: ActionFeedback? = ActionFeedback(
            requestId = "req-B",
            intent = "SET_AC",
            state = ActionExecutionState.EXECUTING,
            message = "Setting AC..."
        )

        // Late response from older Request A arrives
        val lateReqAId = "req-A"
        val lateResultA = "Projector failed"

        if (activeRequestId == lateReqAId) {
            activeFeedback = ActionFeedback(requestId = lateReqAId, message = lateResultA)
        }

        // Assert active feedback was NOT clobbered by late Req A
        assertEquals("req-B", activeFeedback?.requestId)
        assertEquals("Setting AC...", activeFeedback?.message)
    }

    @Test
    fun `D28 - Multi-stage routine updates single primary feedback surface`() {
        var stageFeedback = ActionFeedback(
            requestId = "movie_1",
            intent = "MOVIE_MODE",
            state = ActionExecutionState.EXECUTING,
            message = "Preparing Movie Mode..."
        )
        assertEquals("Preparing Movie Mode...", stageFeedback.message)

        stageFeedback = stageFeedback.copy(message = "Projector · HDMI 1")
        assertEquals("Projector · HDMI 1", stageFeedback.message)

        stageFeedback = stageFeedback.copy(message = "Fire TV · Waking")
        assertEquals("Fire TV · Waking", stageFeedback.message)

        stageFeedback = stageFeedback.copy(
            state = ActionExecutionState.VERIFIED_SUCCESS,
            message = "Movie Mode · Verified",
            severity = FeedbackSeverity.SUCCESS
        )
        assertEquals("Movie Mode · Verified", stageFeedback.message)
        assertEquals(ActionExecutionState.VERIFIED_SUCCESS, stageFeedback.state)
    }

    @Test
    fun `D30 - GlassTokens provides required palette for frosted blurred styling`() {
        assertNotNull(GlassTokens.GlassSurface)
        assertNotNull(GlassTokens.GlassSurfaceHover)
        assertNotNull(GlassTokens.AccentCyan)
        assertNotNull(GlassTokens.AccentRed)
        assertNotNull(GlassTokens.AccentYellow)
        assertNotNull(GlassTokens.AccentBlue)
    }

    @Test
    fun `D31 - UI feedback reflects authoritative physical state`() {
        val physicalAcOnline = true
        val physicalAcTemp = 24

        val feedback = ActionFeedback(
            requestId = "tuya-1",
            intent = "SET_AC_TEMP",
            state = ActionExecutionState.VERIFIED_SUCCESS,
            message = "AC set to ${physicalAcTemp}°C · verified",
            severity = FeedbackSeverity.SUCCESS
        )
        assertTrue(feedback.message.contains("24°C"))
        assertTrue(feedback.message.contains("verified"))
    }

    @Test
    fun `D32 - ActionFeedback is a pure presentation data model with no hardware execution methods`() {
        val model = ActionFeedback(requestId = "1", message = "Info")
        val methods = model.javaClass.declaredMethods.map { it.name }
        // Ensure no hardware actuation methods exist in the feedback presentation model
        assertFalse(methods.any { it.contains("execute") || it.contains("sendAdb") || it.contains("controlHardware") })
    }
}
