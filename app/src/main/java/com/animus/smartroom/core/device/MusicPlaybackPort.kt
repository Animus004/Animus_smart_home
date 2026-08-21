package com.animus.smartroom.core.device

data class ResolvedTrack(
    val title: String,
    val artist: String? = null,
    val videoId: String? = null
)

/**
 * Platform-independent Music Playback contract.
 */
interface MusicPlaybackPort {
    suspend fun play(track: ResolvedTrack, outputDeviceId: String? = null): Result<Unit>
    suspend fun pause(): Result<Unit>
    suspend fun resume(): Result<Unit>
    suspend fun next(): Result<Unit>
    suspend fun previous(): Result<Unit>
    suspend fun setVolume(percentage: Int): Result<Unit>
}
