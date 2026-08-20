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

data class YouTubeSearchCandidate(
    val videoId: String,
    val title: String,
    val channelTitle: String
)

interface YouTubeDataApiClient {
    suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate>
}

class DefaultYouTubeDataApiClient(
    private val packageName: String = "com.animus.smartroom",
    private val certSha1: String = "5ADD1B777BB258081FFA07AA4E4E3E71EF2701E9"
) : YouTubeDataApiClient {

    companion object {
        private const val TAG = "YouTubeDataApiClient"
        private const val BASE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    }

    override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> = withContext(Dispatchers.IO) {
        val trimmedKey = apiKey.trim()
        if (trimmedKey.isBlank()) {
            return@withContext Result.failure(IllegalArgumentException("YouTube API key cannot be empty."))
        }

        val encodedQuery = URLEncoder.encode(query.trim(), "UTF-8")
        val endpointUrl = "$BASE_SEARCH_URL?part=snippet&type=video&maxResults=1&q=$encodedQuery&key=$trimmedKey"

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
                val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use {
                    it.readText()
                }

                val json = JSONObject(responseText)
                val items = json.optJSONArray("items")
                if (items != null && items.length() > 0) {
                    val first = items.getJSONObject(0)
                    val idObj = first.optJSONObject("id")
                    val videoId = idObj?.optString("videoId", "") ?: ""
                    val snippet = first.optJSONObject("snippet")
                    val title = snippet?.optString("title", "") ?: ""
                    val channelTitle = snippet?.optString("channelTitle", "") ?: ""

                    if (YouTubeVideoIdExtractor.isValidVideoId(videoId)) {
                        Log.i(TAG, "[yt-api] Found candidate for query '$query': videoId='$videoId', title='$title', channel='$channelTitle'")
                        return@withContext Result.success(
                            YouTubeSearchCandidate(
                                videoId = videoId,
                                title = title,
                                channelTitle = channelTitle
                            )
                        )
                    } else {
                        Log.w(TAG, "[yt-api] Result item contained invalid videoId: '$videoId'")
                        return@withContext Result.failure(IllegalStateException("Invalid YouTube video ID format: '$videoId'"))
                    }
                }

                Log.w(TAG, "[yt-api] No items found in YouTube search response for query '$query'")
                Result.failure(NoSuchElementException("No video items returned for query: '$query'"))
            } else {
                val errorStream = connection.errorStream
                val rawError = if (errorStream != null) {
                    BufferedReader(InputStreamReader(errorStream, Charsets.UTF_8)).use { it.readText() }
                } else {
                    "HTTP $responseCode: ${connection.responseMessage}"
                }

                val parsedReason = parseGoogleApiError(responseCode, rawError)
                Log.w(TAG, "[yt-api] Search failed (HTTP $responseCode): $parsedReason")
                Result.failure(RuntimeException(parsedReason))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[yt-api] Connection error while querying YouTube search API for '$query'", e)
            Result.failure(e)
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
