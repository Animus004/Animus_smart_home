package com.animus.smartroom.media.provider

import android.app.SearchManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import android.util.Log

class GenericMusicProvider(
    private val context: Context
) : MusicProvider {

    companion object {
        private const val TAG = "GenericMusicProvider"
        const val PROVIDER_ID = "generic"
    }

    override val providerId: String = PROVIDER_ID
    override val displayName: String = "Default Player"

    override fun isInstalled(): Boolean = true

    override fun supportsDirectPlayback(): Boolean = false

    override fun searchAndPlay(title: String, artist: String?): ProviderResult {
        Log.i(TAG, "[provider] Generic searchAndPlay: title='$title', artist='$artist'")
        val query = if (artist.isNullOrBlank()) title else "$title $artist"

        val playIntent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
            putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/audio")
            putExtra(SearchManager.QUERY, query)
            putExtra(MediaStore.EXTRA_MEDIA_TITLE, title)
            if (!artist.isNullOrBlank()) {
                putExtra(MediaStore.EXTRA_MEDIA_ARTIST, artist)
            }
        }

        return try {
            if (playIntent.resolveActivity(context.packageManager) != null) {
                context.startActivity(playIntent)
                ProviderResult.SearchOpenedRequiresUserPlay
            } else {
                openSearch(title, artist)
            }
        } catch (e: Exception) {
            Log.w(TAG, "[provider] Generic play intent failed", e)
            openSearch(title, artist)
        }
    }

    override fun openSearch(title: String, artist: String?): ProviderResult {
        val query = if (artist.isNullOrBlank()) title else "$title $artist"
        val searchUri = "https://www.google.com/search?q=" + Uri.encode("$query song")
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(searchUri)).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        return try {
            context.startActivity(intent)
            ProviderResult.SearchOpenedRequiresUserPlay
        } catch (e: Exception) {
            Log.e(TAG, "[provider] Fallback web search failed", e)
            ProviderResult.Failed(e.message ?: "Failed to open web search")
        }
    }
}
