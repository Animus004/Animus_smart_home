package com.animus.smartroom.media.provider

sealed class ProviderResult {
    object DirectPlaybackStarted : ProviderResult()
    object DirectPlayIntentLaunched : ProviderResult()
    object PlaybackConfirmed : ProviderResult()
    object SearchOpenedRequiresUserPlay : ProviderResult()
    object AppNotInstalled : ProviderResult()
    data class AppInstalledButIntentUnresolvable(val details: String) : ProviderResult()
    data class Failed(val reason: String) : ProviderResult()
}

interface MusicProvider {
    val providerId: String
    val displayName: String

    fun isInstalled(): Boolean
    fun supportsDirectPlayback(): Boolean
    fun searchAndPlay(title: String, artist: String?): ProviderResult
    fun openSearch(title: String, artist: String?): ProviderResult
    fun playDirectTrack(videoId: String, title: String? = null, artist: String? = null): ProviderResult {
        return searchAndPlay(title ?: videoId, artist)
    }
}
