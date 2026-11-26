package com.strangeutility.pricepeek

import android.content.Intent
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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

data class Store(val name: String, val link: String, val status: String)
data class Offer(val name: String, val source: String, val paise: Long, val link: String, val match: String, val stock: String)
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
    val connection = URL(base.trimEnd('/')+"/v1/search?q="+encoded(query)).openConnection() as HttpURLConnection
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
        val offers = (data.optJSONArray("offers") ?: JSONArray()).objects().mapNotNull {
            val url = it.optString("url")
            val amount = it.optLong("price_paise",-1)
            if (!safeHttps(url) || amount <= 0 || it.optString("currency") != "INR") null
            else Offer(it.optString("name"),it.optString("source"),amount,url,it.optString("match"),it.optString("availability"))
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
                var base by rememberSaveable { mutableStateOf(prefs.getString("backend","").orEmpty()) }
                var settings by rememberSaveable { mutableStateOf(false) }
                var result by remember { mutableStateOf<Result?>(null) }
                var submitted by rememberSaveable { mutableStateOf("") }
                var busy by remember { mutableStateOf(false) }
                var history by remember { mutableStateOf(runCatching { JSONArray(prefs.getString("history","[]")) }.getOrDefault(JSONArray()).let { a -> (0 until a.length()).map { a.optString(it) } }) }
                val scope = rememberCoroutineScope()
                LaunchedEffect(sharedText) {
                    if (sharedText.isNotBlank()) {
                        val cleaned = sharedText.replace(Regex("https?://\\S+")," ").trim()
                        if (cleaned.isNotEmpty()) query = cleaned.take(120)
                        else android.widget.Toast.makeText(this@MainActivity,"Shared link received. Enter its product name to compare.",android.widget.Toast.LENGTH_LONG).show()
                    }
                }
                fun search() {
                    val q = query.trim().take(120)
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
                        }
                        item {
                            OutlinedTextField(value=query,onValueChange={query=it.take(120)},modifier=Modifier.fillMaxWidth(),label={Text("Product name or model")},singleLine=true,keyboardOptions=KeyboardOptions(imeAction=ImeAction.Search),keyboardActions=KeyboardActions(onSearch={search()}))
                            Spacer(Modifier.height(8.dp))
                            Button(onClick={search()},enabled=query.trim().length>=2 && !busy,modifier=Modifier.fillMaxWidth()) { Text(if(busy) "Searching…" else "Search stores") }
                            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                        }
                        result?.let { r ->
                            item {
                                Text("Results for "+submitted,style=MaterialTheme.typography.titleLarge)
                                Text(r.message,style=MaterialTheme.typography.bodySmall)
                                if(r.offers.isEmpty()) Text("No verified prices available",style=MaterialTheme.typography.titleMedium)
                            }
                            items(r.offers) { offer ->
                                OutlinedCard(Modifier.fillMaxWidth()) {
                                    Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(5.dp)) {
                                        Text(offer.name,style=MaterialTheme.typography.titleMedium)
                                        Text(offer.source+" · "+offer.stock)
                                        Text(price(offer.paise),style=MaterialTheme.typography.headlineSmall,color=MaterialTheme.colorScheme.primary)
                                        Text(if(offer.match=="identifier_match") "Identifier match — verify variant" else "Possible match — verify model and variant",style=MaterialTheme.typography.bodySmall)
                                        TextButton(onClick={openLink(this@MainActivity,offer.link)}) { Text("View offer") }
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
                if(settings) {
                    var draft by remember { mutableStateOf(base) }
                    val valid = draft.isBlank() || validBase(draft.trim())
                    AlertDialog(onDismissRequest={settings=false},title={Text("Comparison server")},text={
                        Column {
                            Text("Optional HTTPS PricePeek backend. Without a server, only retailer search links are shown. Searches sent to a configured server include your product query.")
                            OutlinedTextField(value=draft,onValueChange={draft=it},label={Text("https://your-server.example")},singleLine=true,isError=!valid)
                        }
                    },confirmButton={TextButton(enabled=valid,onClick={base=draft.trim();prefs.edit().putString("backend",base).apply();settings=false}){Text("Save")}},dismissButton={TextButton(onClick={settings=false}){Text("Cancel")}})
                }
            }
        }
    }
}
