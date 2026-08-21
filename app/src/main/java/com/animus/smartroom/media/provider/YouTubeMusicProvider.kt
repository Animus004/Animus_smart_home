package com.animus.smartroom.media.provider

import android.app.SearchManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Log

class YouTubeMusicProvider(
    private val context: Context
) : MusicProvider {

    companion object {
        private const val TAG = "YouTubeMusicProvider"
        const val PROVIDER_ID = "youtube_music"
        const val PACKAGE_NAME = "com.google.android.apps.youtube.music"
        const val MUSIC_ACTIVITY = "com.google.android.apps.youtube.music.activities.MusicActivity"
        const val ACTION_MEDIA_PLAY = "android.intent.action.MEDIA_PLAY"

        // Production mapping for proven direct-playable presets
        const val ZARA_ZARA_VIDEO_ID = "IWjbBSMsQJg"
        private val DIRECT_TRACK_CATALOG = mapOf(
            "zara zara" to ZARA_ZARA_VIDEO_ID
        )
    }

    override val providerId: String = PROVIDER_ID
    override val displayName: String = "YouTube Music"

    override fun isInstalled(): Boolean {
        val pm = context.packageManager
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getApplicationInfo(PACKAGE_NAME, PackageManager.ApplicationInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                pm.getApplicationInfo(PACKAGE_NAME, 0)
            }
            true
        } catch (e: PackageManager.NameNotFoundException) {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    pm.getPackageInfo(PACKAGE_NAME, PackageManager.PackageInfoFlags.of(0))
                } else {
                    @Suppress("DEPRECATION")
                    pm.getPackageInfo(PACKAGE_NAME, 0)
                }
                true
            } catch (e2: Exception) {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    override fun supportsDirectPlayback(): Boolean = true

    /**
     * Direct track playback using the verified YouTube Music ACTION_VIEW intent.
     */
    override fun playDirectTrack(videoId: String, title: String?, artist: String?): ProviderResult {
        if (!isInstalled()) {
            Log.w(TAG, "[ytmusic] YouTube Music ($PACKAGE_NAME) is not installed.")
            com.animus.smartroom.diagnostics.DiagnosticBus.log(
                tag = "youtube",
                stage = com.animus.smartroom.diagnostics.DiagnosticStage.FAILED,
                message = "YouTube Music is not installed"
            )
            return ProviderResult.AppNotInstalled
        }

        val watchUri = Uri.parse("https://music.youtube.com/watch?v=$videoId")
        Log.i(TAG, "[ytmusic] Launching direct track playback: videoId='$videoId', uri='$watchUri'")

        com.animus.smartroom.diagnostics.DiagnosticBus.log(
            tag = "youtube",
            stage = com.animus.smartroom.diagnostics.DiagnosticStage.INTENT,
            message = "act=ACTION_VIEW, uri=https://music.youtube.com/watch?v=$videoId"
        )

        // Verified Intent Configuration (ACTION_VIEW + Package + MusicActivity)
        val directIntent = Intent(Intent.ACTION_VIEW, watchUri).apply {
            setPackage(PACKAGE_NAME)
            component = ComponentName(PACKAGE_NAME, MUSIC_ACTIVITY)
            addCategory(Intent.CATEGORY_DEFAULT)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        return try {
            val packageManager = context.packageManager
            if (directIntent.resolveActivity(packageManager) != null) {
                context.startActivity(directIntent)
                Log.i(TAG, "[ytmusic] Direct track intent launched successfully.")
                com.animus.smartroom.diagnostics.DiagnosticBus.log(
                    tag = "youtube",
                    stage = com.animus.smartroom.diagnostics.DiagnosticStage.PLAYBACK,
                    message = "Direct play intent dispatched to $PACKAGE_NAME"
                )
                ProviderResult.DirectPlayIntentLaunched
            } else {
                Log.w(TAG, "[ytmusic] Explicit component not resolvable, falling back to package intent.")
                val packageIntent = Intent(Intent.ACTION_VIEW, watchUri).apply {
                    setPackage(PACKAGE_NAME)
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(packageIntent)
                com.animus.smartroom.diagnostics.DiagnosticBus.log(
                    tag = "youtube",
                    stage = com.animus.smartroom.diagnostics.DiagnosticStage.PLAYBACK,
                    message = "Package play intent dispatched to $PACKAGE_NAME"
                )
                ProviderResult.DirectPlayIntentLaunched
            }
        } catch (e: Exception) {
            Log.w(TAG, "[ytmusic] Direct track playback failed, falling back to search", e)
            com.animus.smartroom.diagnostics.DiagnosticBus.log(
                tag = "youtube",
                stage = com.animus.smartroom.diagnostics.DiagnosticStage.FAILED,
                message = "Direct track playback failed: ${e.message}"
            )
            openSearch(title ?: videoId, artist)
        }
    }

    override fun searchAndPlay(title: String, artist: String?): ProviderResult {
        Log.i(TAG, "[youtube] searchAndPlay requested: title='$title', artist='$artist'")

        // Check if track has a known direct video ID
        val directVideoId = DIRECT_TRACK_CATALOG[title.trim().lowercase()]
        if (directVideoId != null) {
            Log.i(TAG, "[youtube] Direct video ID match found ($directVideoId) for '$title'. Using direct playback.")
            return playDirectTrack(directVideoId, title, artist)
        }

        val query = if (artist.isNullOrBlank()) title else "$title $artist"

        val playFromSearchIntent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
            setPackage(PACKAGE_NAME)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
            putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/audio")
            putExtra(SearchManager.QUERY, query)
            putExtra(MediaStore.EXTRA_MEDIA_TITLE, title)
            if (!artist.isNullOrBlank()) {
                putExtra(MediaStore.EXTRA_MEDIA_ARTIST, artist)
            }
        }

        val packageManager = context.packageManager
        if (playFromSearchIntent.resolveActivity(packageManager) != null) {
            return try {
                Log.d(TAG, "[youtube] Launching MEDIA_PLAY_FROM_SEARCH intent for query: '$query'")
                context.startActivity(playFromSearchIntent)
                ProviderResult.SearchOpenedRequiresUserPlay
            } catch (e: Exception) {
                Log.w(TAG, "[youtube] MEDIA_PLAY_FROM_SEARCH intent failed, falling back to search URI", e)
                openSearch(title, artist)
            }
        }

        return openSearch(title, artist)
    }

    override fun openSearch(title: String, artist: String?): ProviderResult {
        val query = if (artist.isNullOrBlank()) title else "$title $artist"
        val encodedQuery = Uri.encode(query)
        val searchUri = "https://music.youtube.com/search?q=$encodedQuery"

        Log.d(TAG, "[youtube] openSearch requested: '$query'")

        if (isInstalled()) {
            val ytMusicSearchIntent = Intent(Intent.ACTION_VIEW, Uri.parse(searchUri)).apply {
                setPackage(PACKAGE_NAME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            return try {
                context.startActivity(ytMusicSearchIntent)
                Log.d(TAG, "[youtube] YouTube Music search URI opened: $searchUri")
                ProviderResult.SearchOpenedRequiresUserPlay
            } catch (e: Exception) {
                Log.w(TAG, "[youtube] Failed to open YouTube Music search URI", e)
                fallbackBrowserSearch(searchUri)
            }
        }

        return fallbackBrowserSearch(searchUri)
    }

    private fun fallbackBrowserSearch(searchUri: String): ProviderResult {
        val genericIntent = Intent(Intent.ACTION_VIEW, Uri.parse(searchUri)).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        return try {
            context.startActivity(genericIntent)
            Log.d(TAG, "[youtube] Generic browser search URI opened: $searchUri")
            ProviderResult.SearchOpenedRequiresUserPlay
        } catch (e: Exception) {
            Log.e(TAG, "[youtube] Fallback browser search failed", e)
            ProviderResult.Failed(e.message ?: "Failed to open search")
        }
    }
}
