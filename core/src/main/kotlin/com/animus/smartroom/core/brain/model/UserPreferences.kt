package com.animus.smartroom.core.brain.model

data class UserPreferences(
    val preferredSpeaker: String? = null,
    val preferredTemperatureCelsius: Int = 24,
    val preferredMusicGenres: List<String> = emptyList(),
    val customAliases: Map<String, String> = emptyMap()
)
