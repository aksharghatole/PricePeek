package com.strangeutility.pricepeek

import java.net.URI
import java.util.Locale

internal data class ListingDraft(val product:String,val store:String,val amount:String,val url:String)

/** Parses only text voluntarily shared by the user. No network, clipboard polling or page access. */
internal object SharedPrice {
    private val links=Regex("https://[^\\s<>]+",RegexOption.IGNORE_CASE)
    private val prices=Regex("(?:₹|\\bINR\\s*|\\bRs\\.?\\s*)\\s*([0-9][0-9,]*(?:\\.[0-9]{1,2})?)(?![0-9.,])",RegexOption.IGNORE_CASE)
    private val ambiguous=Regex("\\b(?:mrp|emi|instalments?|installments?|coupon|cashback|exchange|starting at|up to|save|off|per month|monthly|discount|bank offer|was|list price)\\b|/\\s*(?:mo|month)|%",RegexOption.IGNORE_CASE)
    private val domains=mapOf("amazon.in" to "Amazon India","amzn.in" to "Amazon India","flipkart.com" to "Flipkart","croma.com" to "Croma","reliancedigital.in" to "Reliance Digital","vijaysales.com" to "Vijay Sales","bigbasket.com" to "BigBasket","blinkit.com" to "Blinkit","zepto.com" to "Zepto","zeptonow.com" to "Zepto","swiggy.com" to "Swiggy","jiomart.com" to "JioMart","myntra.com" to "Myntra","ajio.com" to "AJIO")
    fun parse(raw:String):ListingDraft {
        val text=raw.take(4000)
        val allLinks=links.findAll(text).map { it.value.trimEnd('.',',',')','>') }.distinct().toList()
        val url=allLinks.singleOrNull()?.takeIf {
            val uri=runCatching { URI(it) }.getOrNull()
            uri!=null && uri.scheme.equals("https",true) && !uri.host.isNullOrBlank() && uri.userInfo==null && uri.port in listOf(-1,443)
        }.orEmpty()
        val host=runCatching { URI(url).host?.lowercase(Locale.ROOT) }.getOrNull().orEmpty()
        val store=domains.entries.firstOrNull { host==it.key || host.endsWith("."+it.key) }?.value.orEmpty()
        val clean=links.replace(text," ")
        val matches=prices.findAll(clean).toList()
        val values=matches.mapNotNull { match ->
            val rawAmount=match.groupValues[1]
            val normalized=rawAmount.replace(",","")
            val grouping=Regex("(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3})(?:\\.[0-9]{1,2})?")
            if(!grouping.matches(rawAmount) || parsePaise(normalized)==null) null else normalized
        }
        // Never select the lowest number from ambiguous text or infer a conditional price.
        val amount=if(matches.size==1 && values.size==1 && !ambiguous.containsMatchIn(clean)) values[0] else ""
        val title=clean.lineSequence().map { it.trim() }.firstOrNull { line ->
            line.length>=3 && line.any { it.isLetter() } && !prices.containsMatchIn(line) && !ambiguous.containsMatchIn(line)
        }?.take(120) ?: SharedProduct.suggest(url).orEmpty()
        return ListingDraft(title,store,amount,url)
    }
}
