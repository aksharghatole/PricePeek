package com.strangeutility.pricepeek

import android.content.Intent
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import org.json.JSONObject
import org.json.JSONArray
import java.net.URL
import java.net.URI
import java.net.HttpURLConnection
import java.text.NumberFormat
import java.util.Locale

private const val DEFAULT_BACKEND = "https://pricepeek-api-w4qr.onrender.com"

data class Store(val name: String, val link: String, val status: String)
data class Offer(val name: String, val source: String, val paise: Long, val link: String, val match: String, val stock: String, val method: String, val variant: String)
data class Result(val offers: List<Offer>, val stores: List<Store>, val message: String)
private fun encoded(q: String) = Uri.encode(q)
private fun links(q: String): List<Store> = listOf(
    Store("Amazon India", "https://www.amazon.in/s?k="+encoded(q), "Search on retailer"),
    Store("Flipkart", "https://www.flipkart.com/search?q="+encoded(q), "Search on retailer"),
    Store("Croma", "https://www.croma.com/searchB?q="+encoded(q), "Search on retailer"),
    Store("Reliance Digital", "https://www.reliancedigital.in/search?q="+encoded(q), "Search on retailer"),
    Store("Vijay Sales", "https://www.vijaysales.com/search/"+encoded(q), "Search on retailer")
)
private fun safeHttps(value: String): Boolean = try {
    val uri = URI(value)
    uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null
} catch (_: Exception) { false }
private fun validBase(value: String): Boolean = try {
    val uri = URI(value)
    safeHttps(value) && uri.rawQuery == null && uri.rawFragment == null && (uri.path.isNullOrEmpty() || uri.path == "/")
} catch (_: Exception) { false }
private fun price(paise: Long) = NumberFormat.getCurrencyInstance(Locale("en","IN")).format(paise / 100.0)
private fun JSONArray.objects(): List<JSONObject> = (0 until length()).mapNotNull { optJSONObject(it) }
private fun openLink(context: Context, value: String) {
    if (!safeHttps(value)) return
    try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(value))) }
    catch (_: android.content.ActivityNotFoundException) { android.widget.Toast.makeText(context,"No browser available",android.widget.Toast.LENGTH_SHORT).show() }
}
private suspend fun fetch(base: String, query: String): Result = withContext(Dispatchers.IO) {
    require(validBase(base))
    val barcodeLookup = query.matches(Regex("[0-9]{8}|[0-9]{12,14}"))
    val path = if(barcodeLookup) "/v1/observations?barcode=" else "/v1/search?q="
    val connection = URL(base.trimEnd('/')+path+encoded(query)).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 15000
        connection.readTimeout = 35000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("Accept", "application/json")
        require(connection.responseCode == 200) { "Backend returned HTTP "+connection.responseCode }
        val body = connection.inputStream.bufferedReader().use { reader ->
            val buffer = CharArray(8192)
            val out = StringBuilder()
            while (true) {
                val n = reader.read(buffer)
                if (n < 0) break
                require(out.length + n <= 1_000_000) { "Response too large" }
                out.append(buffer,0,n)
            }
            out.toString()
        }
        val data = JSONObject(body)
        if (barcodeLookup) {
            val observed = (data.optJSONArray("observations") ?: JSONArray()).objects().mapNotNull {
                val url=it.optString("url"); val amount=it.optLong("price_paise",-1)
                if(!safeHttps(url) || amount<=0 || it.optString("currency")!="INR") null
                else Offer(it.optString("name"),it.optString("store"),amount,url,"identifier_match","Observed "+it.optString("date"),"community_observation",it.optString("city"))
            }
            return@withContext Result(observed,links(query),data.optString("notice")+" "+data.optString("attribution"))
        }
        val offers = (data.optJSONArray("offers") ?: JSONArray()).objects().mapNotNull {
            val url = it.optString("url")
            val amount = it.optLong("price_paise",-1)
            if (!safeHttps(url) || amount <= 0 || it.optString("currency") != "INR") null
            else Offer(it.optString("name"),it.optString("source"),amount,url,it.optString("match"),it.optString("availability"),it.optString("data_method"),it.optString("variant"))
        }.sortedBy { it.paise }
        val stores = (data.optJSONArray("sources") ?: JSONArray()).objects().mapNotNull {
            val url = it.optString("search_url")
            if (!safeHttps(url)) null else Store(it.optString("source"),url,it.optString("status").replace('_',' '))
        }
        val checked = data.optString("checked_at","Unknown")
        val freshness = if (data.optBoolean("cached")) "Cached" else "Last checked"
        Result(offers, stores.ifEmpty { links(query) }, "$freshness: $checked. "+data.optString("notice"))
    } finally { connection.disconnect() }
}
class MainActivity : ComponentActivity() {
    private var sharedText by mutableStateOf("")
    private fun readShare(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) sharedText = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty().take(500)
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        readShare(intent)
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        readShare(intent)
        val prefs = getSharedPreferences("pricepeek",MODE_PRIVATE)
        setContent {
            val dark = isSystemInDarkTheme()
            MaterialTheme(colorScheme = if(dark) darkColorScheme(primary=Color(0xFF9ED7BB)) else lightColorScheme(primary=Color(0xFF176847))) {
                var query by rememberSaveable { mutableStateOf("") }
                var base by rememberSaveable { mutableStateOf(prefs.getString("backend",DEFAULT_BACKEND).orEmpty()) }
                var settings by rememberSaveable { mutableStateOf(false) }
                var result by remember { mutableStateOf<Result?>(null) }
                var submitted by rememberSaveable { mutableStateOf("") }
                var busy by remember { mutableStateOf(false) }
                var history by remember { mutableStateOf(runCatching { JSONArray(prefs.getString("history","[]")) }.getOrDefault(JSONArray()).let { a -> (0 until a.length()).map { a.optString(it) } }) }
                var notebook by remember { mutableStateOf(readNotes(prefs.getString("price_notes","[]").orEmpty())) }
                var noteProduct by rememberSaveable { mutableStateOf("") }
                var noteEditor by rememberSaveable { mutableStateOf(false) }
                fun saveNotes(value: List<PriceNote>) {
                    notebook = value
                    prefs.edit().putString("price_notes",encodeNotes(value)).apply()
                }
                val scope = rememberCoroutineScope()
                val scanner = rememberLauncherForActivityResult(ScanContract()) { scan ->
                    val code = scan.contents
                    if (code != null) {
                        if (validGtin(code)) {
                            query = code
                            result = null
                        } else {
                            android.widget.Toast.makeText(this@MainActivity,"Not a valid product barcode. Try again.",android.widget.Toast.LENGTH_SHORT).show()
                        }
                    }
                }
                LaunchedEffect(sharedText) {
                    if (sharedText.isNotBlank()) {
                        val suggested = SharedProduct.suggest(sharedText)
                        if (suggested != null) {
                            query = suggested
                            result = null
                        } else {
                            android.widget.Toast.makeText(this@MainActivity,"No product name found in this link. Enter its name or model.",android.widget.Toast.LENGTH_LONG).show()
                        }
                    }
                }
                fun search() {
                    val input = query.trim()
                    val q = (if (input.startsWith("https://",true) || input.startsWith("http://",true)) SharedProduct.suggest(input) else input)?.take(120)
                    if (q == null) {
                        android.widget.Toast.makeText(this@MainActivity,"This link does not include a product name. Enter the name or model.",android.widget.Toast.LENGTH_LONG).show()
                        return
                    }
                    query = q
                    if (q.length < 2 || busy) return
                    submitted = q
                    busy = true
                    result = null
                    history = (listOf(q)+history.filterNot { it.equals(q,true) }).take(20)
                    prefs.edit().putString("history",JSONArray(history).toString()).apply()
                    val endpoint = base.trim()
                    scope.launch {
                        try {
                            result = if(endpoint.isEmpty()) Result(emptyList(),links(q),"No comparison server configured. Open a retailer to check its current prices.")
                            else fetch(endpoint,q)
                        } catch (e: CancellationException) { throw e }
                        catch (_: Exception) { result = Result(emptyList(),links(q),"Price service unavailable. Retailer search links remain available.") }
                        finally { busy = false }
                    }
                }
                Scaffold(modifier=Modifier.fillMaxSize()) { pad ->
                    LazyColumn(modifier=Modifier.padding(pad).fillMaxSize(),contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                        item {
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                                Text("PricePeek",style=MaterialTheme.typography.headlineLarge)
                                TextButton(onClick={ settings=true },enabled=!busy) { Text("Settings") }
                            }
                            Text("Search once. Compare everywhere.",style=MaterialTheme.typography.bodyMedium)
                            Text(if(base.isBlank()) "Retailer link mode" else "Online comparison · your query is sent to the configured server",style=MaterialTheme.typography.bodySmall)
                        }
                        item {
                            OutlinedTextField(value=query,onValueChange={query=it.take(500)},modifier=Modifier.fillMaxWidth(),label={Text("Product name, model, barcode or link")},singleLine=true,keyboardOptions=KeyboardOptions(imeAction=ImeAction.Search),keyboardActions=KeyboardActions(onSearch={search()}))
                            Spacer(Modifier.height(8.dp))
                            Button(onClick={search()},enabled=query.trim().length>=2 && !busy,modifier=Modifier.fillMaxWidth()) { Text(if(busy) "Searching…" else "Search stores") }
                            OutlinedButton(onClick={scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.PRODUCT_CODE_TYPES).setPrompt("Scan the product barcode").setBeepEnabled(false).setBarcodeImageEnabled(false).setOrientationLocked(false))},enabled=!busy,modifier=Modifier.fillMaxWidth()) { Text("Scan barcode") }
                            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                            TextButton(onClick={
                                val term=query.trim().take(120)
                                openLink(this@MainActivity,"https://www.google.com/search?tbm=shop&q="+encoded(term))
                            },enabled=query.trim().length>=2) { Text("Search shopping web") }
                            TextButton(onClick={
                                noteProduct=query.trim().take(120)
                                noteEditor=true
                            },enabled=query.trim().length>=2) { Text("Record a price manually") }
                        }
                        result?.let { r ->
                            item {
                                Text("Results for "+submitted,style=MaterialTheme.typography.titleLarge)
                                Text(r.message,style=MaterialTheme.typography.bodySmall)
                                if(r.offers.isEmpty()) Text("No matching price records available",style=MaterialTheme.typography.titleMedium)
                            }
                            items(r.offers) { offer ->
                                OutlinedCard(Modifier.fillMaxWidth()) {
                                    Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(5.dp)) {
                                        Text(offer.name,style=MaterialTheme.typography.titleMedium)
                                        Text(offer.source+" · "+offer.stock)
                                        Text(when(offer.method) { "community_observation" -> "Historical community observation — not a live offer"; "provider_snapshot" -> "Provider snapshot — price may be outdated"; "public_web" -> "Retrieved from retailer website"; "affiliate_api" -> "Retailer API price"; else -> "Price source not specified" },style=MaterialTheme.typography.bodySmall)
                                        if(offer.variant.isNotBlank()) Text("Variant: "+offer.variant,style=MaterialTheme.typography.bodySmall)
                                        Text(price(offer.paise),style=MaterialTheme.typography.headlineSmall,color=MaterialTheme.colorScheme.primary)
                                        Text(if(offer.match=="identifier_match") "Identifier match — verify variant" else "Possible match — verify model and variant",style=MaterialTheme.typography.bodySmall)
                                        TextButton(onClick={openLink(this@MainActivity,offer.link)}) { Text(if(offer.method=="community_observation") "View observation" else "View offer") }
                                    }
                                }
                            }
                            item { Text("Retailer search links",style=MaterialTheme.typography.titleLarge) }
                            items(r.stores) { store ->
                                OutlinedCard(Modifier.fillMaxWidth()) {
                                    Column(Modifier.padding(12.dp)) {
                                        Text(store.name,style=MaterialTheme.typography.titleMedium)
                                        Text(store.status,style=MaterialTheme.typography.bodySmall)
                                        TextButton(onClick={openLink(this@MainActivity,store.link)}) { Text("Search retailer") }
                                    }
                                }
                            }
                        }
                        if (notebook.isNotEmpty()) {
                            item {
                                Text("Your price notebook",style=MaterialTheme.typography.titleLarge)
                                Text("Prices you recorded yourself, saved on this device. Verify the exact variant and current price before purchasing.",style=MaterialTheme.typography.bodySmall)
                            }
                            val groups = notebook.groupBy { it.product.trim().lowercase(Locale.ROOT) }
                            groups.values.forEach { records ->
                                item { Text(records.first().product,style=MaterialTheme.typography.titleMedium) }
                                items(records.sortedBy { it.totalPaise }) { note ->
                                    OutlinedCard(Modifier.fillMaxWidth()) {
                                        Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                                            Text(note.store,style=MaterialTheme.typography.titleMedium)
                                            Text(price(note.totalPaise),style=MaterialTheme.typography.headlineSmall)
                                            Text("Item "+price(note.itemPaise)+" + delivery "+price(note.deliveryPaise),style=MaterialTheme.typography.bodySmall)
                                            Text("Recorded "+note.recordedAt.take(10)+" · Manual entry",style=MaterialTheme.typography.bodySmall)
                                            Row {
                                                if(note.url.isNotBlank()) TextButton(onClick={openLink(this@MainActivity,note.url)}) { Text("Open link") }
                                                TextButton(onClick={saveNotes(notebook.filterNot { it.id==note.id })}) { Text("Remove") }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        if (result==null && !busy && history.isNotEmpty()) {
                            item {
                                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                                    Text("Recent searches",style=MaterialTheme.typography.titleMedium)
                                    TextButton(onClick={history=emptyList();prefs.edit().remove("history").apply()}) {Text("Clear")}
                                }
                            }
                            items(history) { previous -> TextButton(onClick={query=previous;search()}) {Text(previous)} }
                        }
                    }
                }
                if(noteEditor) {
                    var product by remember { mutableStateOf(noteProduct) }
                    var store by remember { mutableStateOf("") }
                    var itemAmount by remember { mutableStateOf("") }
                    var delivery by remember { mutableStateOf("0") }
                    var link by remember { mutableStateOf("") }
                    val itemPaise = parsePaise(itemAmount)
                    val deliveryPaise = parsePaise(delivery,allowZero=true)
                    val valid = product.isNotBlank() && store.isNotBlank() && itemPaise!=null && deliveryPaise!=null && (link.isBlank() || safeHttps(link.trim()))
                    AlertDialog(onDismissRequest={noteEditor=false},title={Text("Record a price")},text={
                        Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
                            Text("Enter prices you have checked yourself. Include any known delivery or handling fee.")
                            OutlinedTextField(value=product,onValueChange={product=it.take(120)},label={Text("Exact product / variant")},singleLine=true)
                            OutlinedTextField(value=store,onValueChange={store=it.take(80)},label={Text("Store")},singleLine=true)
                            OutlinedTextField(value=itemAmount,onValueChange={itemAmount=it.take(16)},label={Text("Item price (INR)")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal),singleLine=true)
                            OutlinedTextField(value=delivery,onValueChange={delivery=it.take(16)},label={Text("Delivery / fees (INR)")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal),singleLine=true)
                            OutlinedTextField(value=link,onValueChange={link=it.take(1000)},label={Text("Optional HTTPS link")},singleLine=true)
                        }
                    },confirmButton={TextButton(enabled=valid,onClick={
                        if(itemPaise!=null && deliveryPaise!=null) {
                            val note=PriceNote(java.util.UUID.randomUUID().toString(),product.trim(),store.trim(),itemPaise,deliveryPaise,link.trim(),java.time.Instant.now().toString())
                            saveNotes((listOf(note)+notebook).take(200))
                            noteEditor=false
                        }
                    }){Text("Save")}},dismissButton={TextButton(onClick={noteEditor=false}){Text("Cancel")}})
                }
                if(settings) {
                    var draft by remember { mutableStateOf(base) }
                    val valid = draft.isBlank() || validBase(draft.trim())
                    AlertDialog(onDismissRequest={settings=false},title={Text("Comparison server")},text={
                        Column {
                            Text("PricePeek uses its default free hosted server. Clear the address for retailer-link-only mode. Searches sent to a configured server include your product query.")
                            TextButton(onClick={draft=DEFAULT_BACKEND}) { Text("Restore default server") }
                            OutlinedTextField(value=draft,onValueChange={draft=it},label={Text("https://your-server.example")},singleLine=true,isError=!valid)
                        }
                    },confirmButton={TextButton(enabled=valid,onClick={base=draft.trim();prefs.edit().putString("backend",base).apply();settings=false}){Text("Save")}},dismissButton={TextButton(onClick={settings=false}){Text("Cancel")}})
                }
            }
        }
    }
}
