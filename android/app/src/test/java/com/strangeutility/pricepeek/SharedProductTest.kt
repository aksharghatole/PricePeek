package com.strangeutility.pricepeek

import org.junit.Assert.*
import org.junit.Test

class SharedProductTest {
    @Test fun supportedSlugs() {
        assertEquals("Logitech G304 Wireless Mouse",SharedProduct.suggest("https://www.amazon.in/Logitech-G304-Wireless-Mouse/dp/B123456789?tag=abc"))
        assertEquals("samsung galaxy s25",SharedProduct.suggest("https://www.flipkart.com/samsung-galaxy-s25/p/abc"))
        assertEquals("Example Phone",SharedProduct.suggest("Example Phone\nhttps://amzn.in/d/example"))
    }
    @Test fun ambiguousOrUntrustedLinks() {
        assertNull(SharedProduct.suggest("https://www.amazon.in/dp/B123456789"))
        assertNull(SharedProduct.suggest("https://www.amazon.in.evil.invalid/Fake-Product/dp/X"))
        assertNull(SharedProduct.suggest("https://www.amazon.in@evil.invalid/Fake-Product/dp/X"))
        assertNull(SharedProduct.suggest("https://amzn.in/d/short"))
    }
    @Test fun checkDigit() {
        assertTrue(validGtin("4006381333931"))
        assertFalse(validGtin("4006381333932"))
        assertFalse(validGtin("1234"))
    }
}
