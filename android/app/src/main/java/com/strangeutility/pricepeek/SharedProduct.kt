package com.strangeutility.pricepeek

import java.net.URI
import java.util.Locale

internal fun validGtin(code: String): Boolean =
    code.length in setOf(8,12,13,14) && code.all { it in '0'..'9' } &&
        code.reversed().mapIndexed { index, c -> (c-'0') * if (index % 2 == 0) 1 else 3 }.sum() % 10 == 0

/** Offline, editable title suggestions only. Never resolve redirects or trust URL query parameters. */
internal object SharedProduct {
    private val urls = Regex("https?://[^\\s<>]+",RegexOption.IGNORE_CASE)
    private val slugPattern = Regex("[\\p{L}\\p{N}][\\p{L}\\p{N} _-]{2,159}")
    private val amazon = setOf("www.amazon.in","amazon.in")
    private val flipkart = setOf("www.flipkart.com","flipkart.com")
    private val croma = setOf("www.croma.com","croma.com")
    private val reliance = setOf("www.reliancedigital.in","reliancedigital.in")
    fun suggest(text: String): String? {
        val bounded = text.take(2000)
        val sharedTitle = urls.replace(bounded," ").replace(Regex("[\\r\\n]+")," ").trim()
        if (sharedTitle.length >= 3 && sharedTitle.any { it.isLetterOrDigit() }) {
            return sharedTitle.take(120)
        }
        val raw = urls.find(bounded)?.value?.trimEnd('.',',',')','>') ?: return null
        val uri = runCatching { URI(raw) }.getOrNull() ?: return null
        if (uri.scheme?.lowercase(Locale.ROOT) !in setOf("https","http") || uri.userInfo != null || uri.port !in listOf(-1,80,443)) return null
        val host = uri.host?.lowercase(Locale.ROOT) ?: return null
        val parts = uri.path.orEmpty().split('/').filter { it.isNotBlank() }
        val i = parts.indexOf("p")
        val dp = parts.indexOf("dp")
        val slug = when {
            host in amazon && dp > 0 && parts.getOrNull(dp-1) != "gp" -> parts[dp-1]
            host in flipkart && i == 1 -> parts[0]
            host in croma && i > 0 -> parts[i-1]
            host in reliance && i > 0 -> parts[i-1]
            else -> return null
        }
        if (!slugPattern.matches(slug) || !slug.contains('-') || slug.startsWith("http",true)) return null
        return slug.replace('-',' ').replace('_',' ').replace(Regex("\\s+")," ").trim().take(120)
    }
}
