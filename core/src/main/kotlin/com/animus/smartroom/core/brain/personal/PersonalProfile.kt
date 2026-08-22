package com.animus.smartroom.core.brain.personal

import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory

data class PersonalProfile(
    val preferredName: String = "User",
    val interactionStyle: String = "Concise and precise",
    val primarySpeaker: String = "LG SNC4R",
    val primaryAcDevice: String = "Tuya Inverter AC",
    val preferredAcTemperatureCelsius: Int = 24,
    val activeProjects: List<String> = listOf("Animus Smart Room Assistant"),
    val primaryGoals: List<String> = listOf("Automate daily routines and personal workflows"),
    val customNotes: List<String> = emptyList()
) {
    companion object {
        const val MAX_PROFILE_ITEMS = 50
        const val MAX_TEXT_LENGTH = 300
    }
}

data class PersonalContextSummary(
    val preferredName: String,
    val primarySpeaker: String?,
    val preferredAcTemp: Int?,
    val activeProjects: List<String> = emptyList(),
    val primaryGoals: List<String> = emptyList(),
    val relevantPersonalKnowledge: List<String> = emptyList()
)

object PersonalProfileBootstrap {

    fun createInitialMemories(): List<Memory> = listOf(
        Memory(
            content = "User preferred AC temperature is 24 degrees Celsius",
            category = MemoryCategory.PREFERENCE,
            source = "BOOTSTRAP"
        ),
        Memory(
            content = "User primary bedroom speaker is LG SNC4R soundbar",
            category = MemoryCategory.FACT,
            source = "BOOTSTRAP"
        ),
        Memory(
            content = "User is building the Animus personal assistant project",
            category = MemoryCategory.PROJECT,
            source = "BOOTSTRAP"
        ),
        Memory(
            content = "User goal is to turn Animus into an autonomous smart assistant",
            category = MemoryCategory.GOAL,
            source = "BOOTSTRAP"
        )
    )
}
