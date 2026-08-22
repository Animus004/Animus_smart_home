package com.animus.smartroom.media.resolver

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.animus.smartroom.brain.validator.YouTubeVideoIdExtractor
import org.json.JSONObject
import java.util.Locale

data class CachedTrack(
    val videoId: String,
    val title: String,
    val artist: String?,
    val channelTitle: String?,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): String {
        return JSONObject().apply {
            put("videoId", videoId)
            put("title", title)
            put("artist", artist ?: "")
            put("channelTitle", channelTitle ?: "")
            put("timestamp", timestamp)
        }.toString()
    }

    companion object {
        fun fromJson(jsonStr: String): CachedTrack? {
            return try {
                val obj = JSONObject(jsonStr)
                val videoId = obj.getString("videoId")
                val title = obj.getString("title")
                val artist = obj.optString("artist", "").ifBlank { null }
                val channelTitle = obj.optString("channelTitle", "").ifBlank { null }
                val timestamp = obj.optLong("timestamp", System.currentTimeMillis())
                CachedTrack(videoId, title, artist, channelTitle, timestamp)
            } catch (e: Exception) {
                null
            }
        }
    }
}

class MusicResolutionCache(
    private val prefs: SharedPreferences? = null,
    private val maxEntries: Int = 100
) {

    companion object {
        private const val TAG = "MusicResolutionCache"
        private const val PREFS_NAME = "animus_music_resolution_cache"

        fun create(context: Context, maxEntries: Int = 100): MusicResolutionCache {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return MusicResolutionCache(prefs, maxEntries).apply {
                putSeedTrack("zara zara", "Bombay Jayashri", "IWjbBSMsQJg", "Bombay Jayashri - Topic")
                putSeedTrack("zara z", null, "IWjbBSMsQJg", "Bombay Jayashri - Topic")
                putSeedTrack("zara", null, "IWjbBSMsQJg", "Bombay Jayashri - Topic")
            }
        }

        fun normalizeKey(title: String, artist: String?): String {
            val cleanTitle = title.trim().lowercase(Locale.ROOT)
                .replace(Regex("[^a-z0-9\\s]"), " ")
                .replace(Regex("\\s+"), " ")
                .trim()

            val cleanArtist = artist?.trim()?.lowercase(Locale.ROOT)
                ?.replace(Regex("[^a-z0-9\\s]"), " ")
                ?.replace(Regex("\\s+"), " ")
                ?.trim() ?: ""

            return if (cleanArtist.isBlank()) cleanTitle else "$cleanTitle::$cleanArtist"
        }
    }

    // In-memory backing map for fast lookups (and unit tests where SharedPreferences is null)
    private val memoryMap = LinkedHashMap<String, CachedTrack>(16, 0.75f, true)

    init {
        loadFromPrefs()
    }

    fun putSeedTrack(title: String, artist: String?, videoId: String, channelTitle: String?) {
        val key = normalizeKey(title, artist)
        memoryMap[key] = CachedTrack(videoId, title, artist, channelTitle)
    }

    @Synchronized
    private fun loadFromPrefs() {
        prefs?.all?.forEach { (key, value) ->
            if (value is String) {
                val cached = CachedTrack.fromJson(value)
                if (cached != null && YouTubeVideoIdExtractor.isValidVideoId(cached.videoId)) {
                    memoryMap[key] = cached
                }
            }
        }
    }

    @Synchronized
    fun get(title: String, artist: String?): CachedTrack? {
        val key = normalizeKey(title, artist)
        val cached = memoryMap[key] ?: return null

        // Validate that video ID conforms strictly to YouTube standards
        if (!YouTubeVideoIdExtractor.isValidVideoId(cached.videoId)) {
            Log.w(TAG, "[cache] Invalid video ID in cache for key '$key' ('${cached.videoId}'). Evicting.")
            invalidate(title, artist)
            return null
        }

        Log.d(TAG, "[cache] Cache HIT for key '$key' -> videoId='${cached.videoId}', title='${cached.title}'")
        return cached
    }

    @Synchronized
    fun put(title: String, artist: String?, videoId: String, channelTitle: String?) {
        if (!YouTubeVideoIdExtractor.isValidVideoId(videoId)) {
            Log.w(TAG, "[cache] Refusing to cache invalid video ID '$videoId' for title='$title'")
            return
        }

        val key = normalizeKey(title, artist)
        val entry = CachedTrack(
            videoId = videoId,
            title = title,
            artist = artist,
            channelTitle = channelTitle
        )

        // Enforce bounded cache size (LRU eviction)
        if (memoryMap.size >= maxEntries && !memoryMap.containsKey(key)) {
            val oldestKey = memoryMap.keys.firstOrNull()
            if (oldestKey != null) {
                memoryMap.remove(oldestKey)
                prefs?.edit()?.remove(oldestKey)?.apply()
                Log.d(TAG, "[cache] Evicted oldest entry '$oldestKey' to maintain bounded size limit $maxEntries")
            }
        }

        memoryMap[key] = entry
        prefs?.edit()?.putString(key, entry.toJson())?.apply()
        Log.i(TAG, "[cache] Cached track: key='$key', videoId='$videoId' (${memoryMap.size}/$maxEntries entries)")
    }

    @Synchronized
    fun invalidate(title: String, artist: String?) {
        val key = normalizeKey(title, artist)
        val removed = memoryMap.remove(key)
        prefs?.edit()?.remove(key)?.apply()
        if (removed != null) {
            Log.i(TAG, "[cache] Invalidated cache entry for key '$key' (videoId='${removed.videoId}')")
        }
    }

    @Synchronized
    fun clear() {
        memoryMap.clear()
        prefs?.edit()?.clear()?.apply()
        Log.i(TAG, "[cache] Cleared all music resolution cache entries.")
    }

    @Synchronized
    fun size(): Int = memoryMap.size
}
