package com.animus.smartroom.media.resolver

import android.util.Log
import com.animus.smartroom.brain.validator.YouTubeVideoIdExtractor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

interface YouTubeDataApiClient {
    suspend fun searchCandidates(apiKey: String, query: String, maxResults: Int = 5): Result<List<YouTubeSearchCandidate>> =
        searchVideo(apiKey, query).map { listOf(it) }

    suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> =
        searchCandidates(apiKey, query).mapCatching { list ->
            val scored = list.map { candidate ->
                candidate.copy(score = MusicCandidateScorer.score(query, candidate))
            }.sortedByDescending { it.score }
            scored.firstOrNull() ?: throw NoSuchElementException("No candidates found for '$query'")
        }
}

class DefaultYouTubeDataApiClient(
    private val packageName: String = "com.animus.smartroom",
    private val certSha1: String = "5ADD1B777BB258081FFA07AA4E4E3E71EF2701E9"
) : YouTubeDataApiClient {

    companion object {
        private const val TAG = "YouTubeDataApiClient"
        private const val BASE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
        private const val BASE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
    }

    override suspend fun searchCandidates(
        apiKey: String,
        query: String,
        maxResults: Int
    ): Result<List<YouTubeSearchCandidate>> = withContext(Dispatchers.IO) {
        val trimmedKey = apiKey.trim()
        if (trimmedKey.isBlank()) {
            return@withContext Result.failure(IllegalArgumentException("YouTube API key cannot be empty."))
        }

        val encodedQuery = URLEncoder.encode(query.trim(), "UTF-8")
        val searchEndpoint = "$BASE_SEARCH_URL?part=snippet&type=video&videoCategoryId=10&maxResults=$maxResults&q=$encodedQuery&key=$trimmedKey"

        try {
            com.animus.smartroom.diagnostics.DiagnosticBus.log(
                tag = "youtube-api",
                stage = com.animus.smartroom.diagnostics.DiagnosticStage.REQUESTED,
                message = "search.list (maxResults=$maxResults, cat=10)"
            )

            val searchResponse = executeGet(searchEndpoint)
            val searchJson = JSONObject(searchResponse)
            val items = searchJson.optJSONArray("items")

            if (items == null || items.length() == 0) {
                Log.w(TAG, "[yt-api] No items found in YouTube search response for query '$query'")
                return@withContext Result.failure(NoSuchElementException("No video items returned for query: '$query'"))
            }

            val rawCandidates = mutableListOf<YouTubeSearchCandidate>()
            val videoIds = mutableListOf<String>()

            for (i in 0 until items.length()) {
                val item = items.getJSONObject(i)
                val idObj = item.optJSONObject("id")
                val videoId = idObj?.optString("videoId", "") ?: ""
                val snippet = item.optJSONObject("snippet")
                val title = snippet?.optString("title", "") ?: ""
                val channelTitle = snippet?.optString("channelTitle", "") ?: ""

                if (YouTubeVideoIdExtractor.isValidVideoId(videoId)) {
                    videoIds.add(videoId)
                    rawCandidates.add(
                        YouTubeSearchCandidate(
                            videoId = videoId,
                            title = title,
                            channelTitle = channelTitle
                        )
                    )
                }
            }

            if (rawCandidates.isEmpty()) {
                return@withContext Result.failure(IllegalStateException("No valid video IDs found in search results."))
            }

            com.animus.smartroom.diagnostics.DiagnosticBus.log(
                tag = "youtube-api",
                stage = com.animus.smartroom.diagnostics.DiagnosticStage.DEVICE_RESPONSE,
                message = "search.list returned ${rawCandidates.size} candidates"
            )

            // Batch videos.list lookup for rich metadata (duration, licensing, embeddability)
            val enrichedCandidates = try {
                enrichWithVideosBatch(rawCandidates, videoIds, trimmedKey)
            } catch (e: Exception) {
                Log.w(TAG, "[yt-api] Failed to enrich candidates with videos.list batch, using search candidates directly", e)
                rawCandidates
            }

            Result.success(enrichedCandidates)
        } catch (e: Exception) {
            Log.e(TAG, "[yt-api] Error during candidate search for '$query'", e)
            com.animus.smartroom.diagnostics.DiagnosticBus.log(
                tag = "youtube-api",
                stage = com.animus.smartroom.diagnostics.DiagnosticStage.FAILED,
                message = "API error: ${e.message}"
            )
            Result.failure(e)
        }
    }

    override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
        val candidatesResult = searchCandidates(apiKey, query, maxResults = 5)
        return candidatesResult.mapCatching { list ->
            // Score candidates and return best
            val scored = list.map { candidate ->
                candidate.copy(score = MusicCandidateScorer.score(query, candidate))
            }.sortedByDescending { it.score }

            scored.firstOrNull() ?: throw NoSuchElementException("No candidates available for '$query'")
        }
    }

    private fun enrichWithVideosBatch(
        candidates: List<YouTubeSearchCandidate>,
        videoIds: List<String>,
        apiKey: String
    ): List<YouTubeSearchCandidate> {
        val joinedIds = videoIds.joinToString(",")
        val videosEndpoint = "$BASE_VIDEOS_URL?part=snippet,contentDetails,status&id=$joinedIds&key=$apiKey"
        val videosResponse = executeGet(videosEndpoint)
        val videosJson = JSONObject(videosResponse)
        val items = videosJson.optJSONArray("items") ?: return candidates

        val detailsMap = mutableMapOf<String, JSONObject>()
        for (i in 0 until items.length()) {
            val item = items.getJSONObject(i)
            val id = item.optString("id", "")
            if (id.isNotBlank()) {
                detailsMap[id] = item
            }
        }

        return candidates.map { candidate ->
            val detail = detailsMap[candidate.videoId]
            if (detail != null) {
                val contentDetails = detail.optJSONObject("contentDetails")
                val status = detail.optJSONObject("status")
                val duration = contentDetails?.optString("duration", "") ?: ""
                val licensedContent = contentDetails?.optBoolean("licensedContent", false) ?: false
                val embeddable = status?.optBoolean("embeddable", true) ?: true

                candidate.copy(
                    duration = duration,
                    licensedContent = licensedContent,
                    embeddable = embeddable
                )
            } else {
                candidate
            }
        }
    }

    private fun executeGet(endpointUrl: String): String {
        var connection: HttpURLConnection? = null
        try {
            val url = URL(endpointUrl)
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                setRequestProperty("Accept", "application/json")
                setRequestProperty("X-Android-Package", packageName)
                setRequestProperty("X-Android-Cert", certSha1)
                connectTimeout = 8000
                readTimeout = 10000
                doInput = true
            }

            val responseCode = connection.responseCode
            if (responseCode == HttpURLConnection.HTTP_OK) {
                return BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use {
                    it.readText()
                }
            } else {
                val errorStream = connection.errorStream
                val rawError = if (errorStream != null) {
                    BufferedReader(InputStreamReader(errorStream, Charsets.UTF_8)).use { it.readText() }
                } else {
                    "HTTP $responseCode: ${connection.responseMessage}"
                }
                val parsedReason = parseGoogleApiError(responseCode, rawError)
                throw RuntimeException(parsedReason)
            }
        } finally {
            connection?.disconnect()
        }
    }

    private fun parseGoogleApiError(code: Int, rawBody: String): String {
        return try {
            val json = JSONObject(rawBody)
            val errorObj = json.optJSONObject("error")
            val message = errorObj?.optString("message", "") ?: ""
            val status = errorObj?.optString("status", "") ?: ""
            "YouTube API HTTP $code ($status): $message"
        } catch (e: Exception) {
            "YouTube API HTTP $code: $rawBody"
        }
    }
}
