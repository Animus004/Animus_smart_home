package com.animus.smartroom.media.resolver

import java.util.Locale

data class YouTubeSearchCandidate(
    val videoId: String,
    val title: String,
    val channelTitle: String,
    val duration: String? = null,
    val licensedContent: Boolean = false,
    val embeddable: Boolean = true,
    val score: Int = 0
)

object MusicCandidateScorer {

    private val OFFICIAL_LABELS = listOf(
        "vevo",
        "t-series",
        "sony",
        "tips",
        "yrf",
        "zee music",
        "saregama",
        "speed records",
        "eros",
        "warner",
        "universal music",
        "atlantic",
        "columbia records",
        "coke studio"
    )

    fun score(query: String, candidate: YouTubeSearchCandidate): Int {
        var score = 50
        val tLower = candidate.title.lowercase(Locale.ROOT)
        val qLower = query.lowercase(Locale.ROOT)
        val cLower = candidate.channelTitle.lowercase(Locale.ROOT)

        val isTopic = cLower.endsWith(" - topic")
        val isOfficialLabel = OFFICIAL_LABELS.any { cLower.contains(it) }

        // User intent flags
        val isCoverRequested = qLower.contains("cover")
        val isRemixRequested = qLower.contains("remix") || qLower.contains("mix")
        val isAcousticRequested = qLower.contains("acoustic") || qLower.contains("unplugged")
        val isLiveRequested = qLower.contains("live") || qLower.contains("concert")
        val isInstrumentalRequested = qLower.contains("instrumental") || qLower.contains("karaoke")
        val isLongRequested = qLower.contains("sleep") || qLower.contains("hours") || qLower.contains("compilation") || qLower.contains("meditation")

        // 1. Channel authority
        if (isTopic) {
            score += 35 // Direct YouTube Music studio master track
        } else if (isOfficialLabel) {
            score += 25
        }

        // 2. Licensing
        if (candidate.licensedContent) {
            score += 15
        }

        // 3. Positive title keywords
        if (tLower.contains("official audio")) {
            score += 20
        } else if (tLower.contains("official music video") || tLower.contains("official video")) {
            score += 15
        } else if (tLower.contains("original soundtrack") || tLower.contains("soundtrack") || tLower.contains("full song")) {
            score += 10
        }

        // 4. User-requested modifier bonuses
        if (isAcousticRequested && (tLower.contains("acoustic") || tLower.contains("unplugged"))) {
            score += 30
        }
        if (isLiveRequested && (tLower.contains("live") || tLower.contains("concert"))) {
            score += 30
        }
        if (isRemixRequested && (tLower.contains("remix") || tLower.contains("mix"))) {
            score += 30
        }
        if (isCoverRequested && tLower.contains("cover")) {
            score += 20
        }
        if (isInstrumentalRequested && (tLower.contains("instrumental") || tLower.contains("karaoke"))) {
            score += 20
        }

        // 5. Negative penalties (only when user did NOT request them)
        if (tLower.contains("status") || tLower.contains("shorts") || tLower.contains("whatsapp")) {
            score -= 50
        }
        if (tLower.contains("reaction") || tLower.contains("trailer") || tLower.contains("teaser") || tLower.contains("making of") || tLower.contains("behind the scenes")) {
            score -= 40
        }
        if (!isCoverRequested && tLower.contains("cover")) {
            score -= 30
        }
        if (tLower.contains("slowed") || tLower.contains("reverb") || tLower.contains("sped up")) {
            score -= 30
        }
        if (!isInstrumentalRequested && (tLower.contains("karaoke") || tLower.contains("instrumental"))) {
            score -= 25
        }
        if (!isRemixRequested && tLower.contains("remix")) {
            score -= 20
        }

        // 6. Duration penalties
        val dur = candidate.duration ?: ""
        if (isShortsDuration(dur)) {
            score -= 50
        } else if (!isLongRequested && isExcessivelyLongDuration(dur)) {
            score -= 30
        }

        return score
    }

    private fun isShortsDuration(isoDuration: String): Boolean {
        if (isoDuration.isBlank()) return false
        // PT30S, PT45S, PT59S (under 1 minute)
        return isoDuration.startsWith("PT") && !isoDuration.contains("M") && !isoDuration.contains("H")
    }

    private fun isExcessivelyLongDuration(isoDuration: String): Boolean {
        if (isoDuration.isBlank()) return false
        // Contains hours (PT1H, PT2H) or over 25 minutes
        if (isoDuration.contains("H")) return true
        if (isoDuration.contains("M")) {
            val minutePart = isoDuration.substringAfter("PT").substringBefore("M")
            val minutes = minutePart.toIntOrNull() ?: 0
            return minutes >= 25
        }
        return false
    }
}
