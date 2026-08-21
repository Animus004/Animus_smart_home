package com.animus.smartroom.core.diagnostics.sanitizer

/**
 * Sanitizes diagnostic messages and metadata to guarantee zero credential leakage.
 */
object EventSanitizer {

    private val SENSITIVE_PATTERNS = listOf(
        Regex("""(?i)(AIza[0-9A-Za-z\-_]{10,})""") to "[REDACTED_GEMINI_KEY]",
        Regex("""(?i)(Bearer\s+[A-Za-z0-9\-\._~+/]+=*)""") to "[REDACTED_BEARER_TOKEN]",
        Regex("""(?i)(access_token|refresh_token|accessToken|refreshToken)["':\s=]+([A-Za-z0-9\-_.]+)""") to "$1:[REDACTED_TOKEN]",
        Regex("""(?i)(TUYA_ACCESS|TUYA_SECRET|client_secret|client_id|accessSecret)["':\s=]+([A-Za-z0-9\-_.]+)""") to "$1:[REDACTED_SECRET]",
        Regex("""(?i)(Authorization:\s*)([^\s\r\n,]+)""") to "$1[REDACTED_AUTH_HEADER]",
        Regex("""(?i)(api[_\-]?key)["':\s=]+([A-Za-z0-9\-_.]+)""") to "$1:[REDACTED_API_KEY]"
    )

    private val SENSITIVE_KEYS = setOf(
        "accesstoken", "refreshtoken", "tuyaaccess", "tuyasecret", "secret",
        "clientsecret", "clientid", "authorization", "password", "apikey"
    )

    fun sanitizeText(text: String?): String? {
        if (text == null) return null
        var sanitized: String = text
        for ((pattern, replacement) in SENSITIVE_PATTERNS) {
            sanitized = pattern.replace(sanitized, replacement)
        }
        return sanitized
    }

    fun sanitizeMetadata(metadata: Map<String, String>): Map<String, String> {
        if (metadata.isEmpty()) return emptyMap()
        val sanitized = mutableMapOf<String, String>()
        for ((key, value) in metadata) {
            val normalizedKey = key.lowercase().replace("-", "").replace("_", "")
            if (normalizedKey in SENSITIVE_KEYS || SENSITIVE_KEYS.any { normalizedKey.contains(it) }) {
                sanitized[key] = "[REDACTED]"
            } else {
                sanitized[key] = sanitizeText(value) ?: value
            }
        }
        return sanitized
    }
}
