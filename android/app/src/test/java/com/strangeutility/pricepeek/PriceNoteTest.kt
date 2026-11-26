package com.strangeutility.pricepeek
import org.junit.Assert.*
import org.junit.Test
class PriceNoteTest {
    @Test fun amounts() {
        assertEquals(129950L,parsePaise("1299.50"))
        assertEquals(0L,parsePaise("0",true))
        assertNull(parsePaise("0"))
        assertNull(parsePaise("1.234"))
        assertNull(parsePaise("-1"))
        assertNull(parsePaise("NaN"))
        assertNull(parsePaise("1e4"))
    }
    @Test fun total() {
        assertEquals(12500L,PriceNote("id","item","store",10000,2500,"","2026-11-26").totalPaise)
    }
}
