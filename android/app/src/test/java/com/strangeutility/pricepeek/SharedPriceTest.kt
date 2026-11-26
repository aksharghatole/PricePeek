package com.strangeutility.pricepeek
import org.junit.Assert.*
import org.junit.Test
class SharedPriceTest {
    @Test fun singlePrice() {
        val draft=SharedPrice.parse("Logitech G304\n₹1,299.50\nhttps://www.amazon.in/Logitech-G304/dp/ABC")
        assertEquals("Logitech G304",draft.product)
        assertEquals("1299.50",draft.amount)
        assertEquals("Amazon India",draft.store)
    }
    @Test fun ambiguous() {
        assertEquals("",SharedPrice.parse("Product ₹999 MRP ₹1499").amount)
        assertEquals("",SharedPrice.parse("Product EMI ₹99").amount)
        assertEquals("",SharedPrice.parse("Product ₹99/month").amount)
        assertEquals("",SharedPrice.parse("Product ₹1,2,3").amount)
        assertEquals("",SharedPrice.parse("Product $999").amount)
        assertEquals("",SharedPrice.parse("Product ₹1.234").amount)
    }
    @Test fun untrustedHost() {
        assertEquals("",SharedPrice.parse("Item ₹99 https://amazon.in.evil.invalid/p").store)
        assertEquals("",SharedPrice.parse("Item ₹99 https://amazon.in@evil.invalid/p").url)
    }
}
