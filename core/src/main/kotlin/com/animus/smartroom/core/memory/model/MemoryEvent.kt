package com.animus.smartroom.core.memory.model

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * Base sealed class for all structured personal memory events in Animus.
 */
sealed class MemoryEvent(
    open val id: String = UUID.randomUUID().toString(),
    open val timestamp: Long = System.currentTimeMillis(),
    open val category: MemoryCategory,
    open val source: String = "USER",
    open val summary: String,
    open val metadata: Map<String, Any> = emptyMap()
) {

    abstract fun toJsonObject(): JSONObject

    fun toJson(): String = toJsonObject().toString()

    companion object {
        fun fromJson(jsonStr: String): MemoryEvent? {
            return try {
                val json = JSONObject(jsonStr)
                val category = MemoryCategory.valueOf(json.getString("category"))
                when (category) {
                    MemoryCategory.LEARNING -> LearningEvent.fromJsonObject(json)
                    MemoryCategory.PROJECT -> ProjectProgressEvent.fromJsonObject(json)
                    MemoryCategory.PREFERENCE -> PreferenceEvent.fromJsonObject(json)
                    MemoryCategory.DEVICE_PREFERENCE -> DevicePreferenceEvent.fromJsonObject(json)
                    MemoryCategory.ROUTINE -> RoutineHistoryEvent.fromJsonObject(json)
                    MemoryCategory.DAILY_ACTIVITY -> DailyActivityEvent.fromJsonObject(json)
                    MemoryCategory.SYSTEM_MILESTONE -> SystemMilestoneEvent.fromJsonObject(json)
                }
            } catch (e: Exception) {
                null
            }
        }
    }
}

enum class LearningStatus {
    STUDIED,
    PRACTICED,
    COMPLETED,
    REVIEWED,
    STRUGGLED_WITH,
    MASTERED;

    companion object {
        fun fromString(name: String): LearningStatus =
            entries.firstOrNull { it.name.equals(name.trim(), ignoreCase = true) } ?: STUDIED
    }
}

data class LearningEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "USER",
    val topic: String,
    val subtopic: String? = null,
    val action: String,
    val notes: String? = null,
    val status: LearningStatus = LearningStatus.STUDIED,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.LEARNING,
    source = source,
    summary = "$topic: $action (${status.name.lowercase()})",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("topic", topic)
            if (subtopic != null) put("subtopic", subtopic)
            put("action", action)
            if (notes != null) put("notes", notes)
            put("status", status.name)
            put("summary", summary)
            val metaObj = JSONObject()
            metadata.forEach { (k, v) -> metaObj.put(k, v) }
            put("metadata", metaObj)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): LearningEvent {
            val meta = mutableMapOf<String, Any>()
            json.optJSONObject("metadata")?.let { m ->
                m.keys().forEach { k -> meta[k] = m.get(k) }
            }
            return LearningEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "USER"),
                topic = json.getString("topic"),
                subtopic = json.optString("subtopic", "").ifBlank { null },
                action = json.getString("action"),
                notes = json.optString("notes", "").ifBlank { null },
                status = LearningStatus.fromString(json.optString("status", "STUDIED")),
                metadata = meta
            )
        }
    }
}

enum class ProjectStatus {
    STARTED,
    IN_PROGRESS,
    COMPLETED,
    BLOCKED,
    RESUMED,
    MILESTONE_COMPLETED;

    companion object {
        fun fromString(name: String): ProjectStatus =
            entries.firstOrNull { it.name.equals(name.trim(), ignoreCase = true) } ?: IN_PROGRESS
    }
}

data class ProjectProgressEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "USER",
    val projectName: String,
    val projectId: String? = null,
    val milestone: String,
    val action: String,
    val status: ProjectStatus = ProjectStatus.IN_PROGRESS,
    val notes: String? = null,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.PROJECT,
    source = source,
    summary = "$projectName — $milestone: $action (${status.name.lowercase()})",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("projectName", projectName)
            if (projectId != null) put("projectId", projectId)
            put("milestone", milestone)
            put("action", action)
            put("status", status.name)
            if (notes != null) put("notes", notes)
            put("summary", summary)
            val metaObj = JSONObject()
            metadata.forEach { (k, v) -> metaObj.put(k, v) }
            put("metadata", metaObj)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): ProjectProgressEvent {
            val meta = mutableMapOf<String, Any>()
            json.optJSONObject("metadata")?.let { m ->
                m.keys().forEach { k -> meta[k] = m.get(k) }
            }
            return ProjectProgressEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "USER"),
                projectName = json.getString("projectName"),
                projectId = json.optString("projectId", "").ifBlank { null },
                milestone = json.getString("milestone"),
                action = json.getString("action"),
                status = ProjectStatus.fromString(json.optString("status", "IN_PROGRESS")),
                notes = json.optString("notes", "").ifBlank { null },
                metadata = meta
            )
        }
    }
}

data class PreferenceEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "USER",
    val prefCategory: String,
    val key: String,
    val value: String,
    val confidence: Float = 1.0f,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.PREFERENCE,
    source = source,
    summary = "Preference [$prefCategory] $key = $value (confidence=$confidence)",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("prefCategory", prefCategory)
            put("key", key)
            put("value", value)
            put("confidence", confidence.toDouble())
            put("summary", summary)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): PreferenceEvent {
            return PreferenceEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "USER"),
                prefCategory = json.getString("prefCategory"),
                key = json.getString("key"),
                value = json.getString("value"),
                confidence = json.optDouble("confidence", 1.0).toFloat()
            )
        }
    }
}

data class DevicePreferenceEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "USER",
    val targetDevice: String,
    val preferredState: Map<String, Any> = emptyMap(),
    val contextTag: String? = null,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.DEVICE_PREFERENCE,
    source = source,
    summary = "Device Preference for $targetDevice: $preferredState ${if (contextTag != null) "[$contextTag]" else ""}",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("targetDevice", targetDevice)
            val stateObj = JSONObject()
            preferredState.forEach { (k, v) -> stateObj.put(k, v) }
            put("preferredState", stateObj)
            if (contextTag != null) put("contextTag", contextTag)
            put("summary", summary)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): DevicePreferenceEvent {
            val stateMap = mutableMapOf<String, Any>()
            json.optJSONObject("preferredState")?.let { s ->
                s.keys().forEach { k -> stateMap[k] = s.get(k) }
            }
            return DevicePreferenceEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "USER"),
                targetDevice = json.getString("targetDevice"),
                preferredState = stateMap,
                contextTag = json.optString("contextTag", "").ifBlank { null }
            )
        }
    }
}

data class RoutineHistoryEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "ROUTINE",
    val routineName: String,
    val startedAt: Long,
    val completedAt: Long,
    val outcome: String,
    val routineSummary: String? = null,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.ROUTINE,
    source = source,
    summary = "Routine '$routineName' finished: $outcome",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("routineName", routineName)
            put("startedAt", startedAt)
            put("completedAt", completedAt)
            put("outcome", outcome)
            if (routineSummary != null) put("routineSummary", routineSummary)
            put("summary", summary)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): RoutineHistoryEvent {
            return RoutineHistoryEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "ROUTINE"),
                routineName = json.getString("routineName"),
                startedAt = json.optLong("startedAt", System.currentTimeMillis()),
                completedAt = json.optLong("completedAt", System.currentTimeMillis()),
                outcome = json.getString("outcome"),
                routineSummary = json.optString("routineSummary", "").ifBlank { null }
            )
        }
    }
}

data class DailyActivityEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "USER",
    val title: String,
    val description: String,
    val tags: List<String> = emptyList(),
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.DAILY_ACTIVITY,
    source = source,
    summary = "$title: $description",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("title", title)
            put("description", description)
            val tagArray = JSONArray()
            tags.forEach { tagArray.put(it) }
            put("tags", tagArray)
            put("summary", summary)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): DailyActivityEvent {
            val tagsList = mutableListOf<String>()
            json.optJSONArray("tags")?.let { arr ->
                for (i in 0 until arr.length()) {
                    tagsList.add(arr.getString(i))
                }
            }
            return DailyActivityEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "USER"),
                title = json.getString("title"),
                description = json.getString("description"),
                tags = tagsList
            )
        }
    }
}

data class SystemMilestoneEvent(
    override val id: String = UUID.randomUUID().toString(),
    override val timestamp: Long = System.currentTimeMillis(),
    override val source: String = "SYSTEM",
    val milestoneName: String,
    val description: String,
    val versionOrPhase: String,
    override val metadata: Map<String, Any> = emptyMap()
) : MemoryEvent(
    id = id,
    timestamp = timestamp,
    category = MemoryCategory.SYSTEM_MILESTONE,
    source = source,
    summary = "System Milestone [$versionOrPhase]: $milestoneName",
    metadata = metadata
) {
    override fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("timestamp", timestamp)
            put("category", category.name)
            put("source", source)
            put("milestoneName", milestoneName)
            put("description", description)
            put("versionOrPhase", versionOrPhase)
            put("summary", summary)
        }
    }

    companion object {
        fun fromJsonObject(json: JSONObject): SystemMilestoneEvent {
            return SystemMilestoneEvent(
                id = json.optString("id", UUID.randomUUID().toString()),
                timestamp = json.optLong("timestamp", System.currentTimeMillis()),
                source = json.optString("source", "SYSTEM"),
                milestoneName = json.getString("milestoneName"),
                description = json.getString("description"),
                versionOrPhase = json.getString("versionOrPhase")
            )
        }
    }
}
