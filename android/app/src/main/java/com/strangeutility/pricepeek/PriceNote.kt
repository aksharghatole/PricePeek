package com.strangeutility.pricepeek

import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode

internal data class PriceNote(val id:String,val product:String,val store:String,val itemPaise:Long,val deliveryPaise:Long,val url:String,val recordedAt:String) {
    val totalPaise:Long get()=itemPaise+deliveryPaise
}
internal fun parsePaise(raw:String,allowZero:Boolean=false):Long? {
    if(!raw.trim().matches(Regex("[0-9]{1,8}(\\.[0-9]{1,2})?"))) return null
    return runCatching {
        val value=BigDecimal(raw.trim()).movePointRight(2).setScale(0,RoundingMode.UNNECESSARY).longValueExact()
        if(value < 0 || (!allowZero && value==0L) || value>10_000_000_000L) null else value
    }.getOrNull()
}
internal fun readNotes(raw:String):List<PriceNote> = runCatching {
    val array=JSONArray(raw)
    (0 until minOf(array.length(),200)).mapNotNull { index ->
        val row=array.optJSONObject(index) ?: return@mapNotNull null
        val item=row.optLong("item",-1)
        val delivery=row.optLong("delivery",-1)
        if(item !in 1L..10_000_000_000L || delivery !in 0L..10_000_000_000L) null
        else PriceNote(row.getString("id"),row.getString("product"),row.getString("store"),item,delivery,row.optString("url"),row.getString("recorded"))
    }
}.getOrDefault(emptyList())
internal fun encodeNotes(notes:List<PriceNote>):String = JSONArray().apply {
    notes.take(200).forEach { note ->
        put(JSONObject().put("id",note.id).put("product",note.product).put("store",note.store).put("item",note.itemPaise).put("delivery",note.deliveryPaise).put("url",note.url).put("recorded",note.recordedAt))
    }
}.toString()
