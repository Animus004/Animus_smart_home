package com.animus.smartroom.core.device

import android.content.Context
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.provider.ProviderResult
import com.animus.smartroom.media.provider.YouTubeMusicProvider

/**
 * Android implementation of [MusicPlaybackPort] delegating to [YouTubeMusicProvider] and [MusicController].
 */
class AndroidMusicPlaybackPort(
    private val context: Context,
    private val youtubeProvider: YouTubeMusicProvider = YouTubeMusicProvider(context),
    private val musicController: MusicController = MusicController(context)
) : MusicPlaybackPort {

    override suspend fun play(track: ResolvedTrack, outputDeviceId: String?): Result<Unit> {
        val result = if (track.videoId != null) {
            youtubeProvider.playDirectTrack(
                videoId = track.videoId,
                title = track.title,
                artist = track.artist
            )
        } else {
            youtubeProvider.searchAndPlay(
                title = track.title,
                artist = track.artist
            )
        }

        return when (result) {
            is ProviderResult.DirectPlayIntentLaunched,
            is ProviderResult.DirectPlaybackStarted,
            is ProviderResult.PlaybackConfirmed,
            is ProviderResult.SearchOpenedRequiresUserPlay -> Result.success(Unit)
            is ProviderResult.AppNotInstalled -> Result.failure(Exception("YouTube Music is not installed."))
            is ProviderResult.AppInstalledButIntentUnresolvable -> Result.failure(Exception(result.details))
            is ProviderResult.Failed -> Result.failure(Exception(result.reason))
        }
    }

    override suspend fun pause(): Result<Unit> {
        musicController.pause()
        return Result.success(Unit)
    }

    override suspend fun resume(): Result<Unit> {
        musicController.play()
        return Result.success(Unit)
    }

    override suspend fun next(): Result<Unit> {
        musicController.next()
        return Result.success(Unit)
    }

    override suspend fun previous(): Result<Unit> {
        musicController.previous()
        return Result.success(Unit)
    }

    override suspend fun setVolume(percentage: Int): Result<Unit> {
        val percent = (percentage.coerceIn(0, 100) / 100f)
        musicController.setVolume(percent)
        return Result.success(Unit)
    }
}
