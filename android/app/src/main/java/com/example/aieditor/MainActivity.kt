package com.example.aieditor

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

val Bg = Color(0xFF0D0D0D)
val CardBg = Color(0xFF1A1A1A)
val Red = Color(0xFFE50914)
val Txt = Color(0xFFF5F5F5)
val Grey = Color(0xFF888888)

fun onMain(block: () -> Unit) = Handler(Looper.getMainLooper()).post(block)

data class Msg(val role: String, val text: String)
data class Proj(val id: String, val name: String, val status: String)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { App() }
    }
}

@Composable
fun App() {
    val ctx = LocalContext.current
    val prefs = remember { ctx.getSharedPreferences("plab", 0) }
    var serverIp by remember { mutableStateOf(prefs.getString("ip", "192.168.1.10") ?: "192.168.1.10") }
    var screen by remember { mutableStateOf("home") }
    var projects by remember { mutableStateOf(listOf<Proj>()) }
    var currentPid by remember { mutableStateOf("") }
    var currentName by remember { mutableStateOf("") }
    var isGeneralChat by remember { mutableStateOf(true) }

    fun base() = "http://$serverIp:8000"

    fun refresh() {
        httpGet("${base()}/projects") { body ->
            try {
                val arr = JSONArray(body)
                val list = (0 until arr.length()).map {
                    val o = arr.getJSONObject(it)
                    Proj(o.getString("id"), o.optString("name"), o.optString("status"))
                }
                onMain { projects = list }
            } catch (_: Exception) {}
        }
    }

    Surface(Modifier.fillMaxSize().background(Bg), color = Bg) {
        when (screen) {
            "home" -> HomeScreen(serverIp, { serverIp = it; prefs.edit().putString("ip", it).apply() },
                projects, { refresh() },
                { pid, name -> currentPid = pid; currentName = name; isGeneralChat = false; screen = "chat" },
                { screen = "chat"; isGeneralChat = true; currentPid = "general"; currentName = "General Chat" },
                { screen = "new" })
            "new" -> NewProjectScreen(base(), { refresh(); screen = "home" }, { screen = "home" })
            "chat" -> ChatScreen(base(), currentPid, currentName, isGeneralChat,
                onPickVideo = { uri -> uploadVideo(ctx, base(), currentPid, uri) })
        }
    }
}

@Composable
fun HomeScreen(ip: String, onIp: (String) -> Unit, projects: List<Proj>, onRefresh: () -> Unit,
               openProject: (String, String) -> Unit, openGeneral: () -> Unit, onNew: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("THE PRIVACY LAB", color = Red, fontSize = 26.sp, fontWeight = FontWeight.Black)
        Text("AI EDITOR v2.2", color = Grey, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(value = ip, onValueChange = onIp, label = { Text("PC ka IP (ipconfig se dekho)", color = Grey) },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Red, unfocusedBorderColor = Grey, focusedTextColor = Txt, unfocusedTextColor = Txt))
        Spacer(Modifier.height(12.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(onClick = onRefresh, colors = ButtonDefaults.buttonColors(containerColor = CardBg), modifier = Modifier.weight(1f)) { Text("Refresh", color = Red) }
            Button(onClick = onNew, colors = ButtonDefaults.buttonColors(containerColor = Red), modifier = Modifier.weight(1f)) { Text("+ Naya Project", color = Txt) }
        }
        Spacer(Modifier.height(12.dp))
        Button(onClick = openGeneral, colors = ButtonDefaults.buttonColors(containerColor = CardBg), modifier = Modifier.fillMaxWidth()) {
            Text("💬 General Chat — baat karke project banao", color = Txt)
        }
        Spacer(Modifier.height(16.dp))
        Text("PROJECTS", color = Grey, fontSize = 13.sp)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(projects) { p ->
                Card(colors = CardDefaults.cardColors(containerColor = CardBg), modifier = Modifier.fillMaxWidth(),
                    onClick = { openProject(p.id, p.name) }) {
                    Row(Modifier.padding(14.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column {
                            Text(p.name, color = Txt, fontSize = 16.sp)
                            Text(p.id, color = Grey, fontSize = 11.sp)
                        }
                        Text(p.status.uppercase(), color = if (p.status == "done") Color(0xFF2ECC71) else Red, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
fun NewProjectScreen(base: String, done: () -> Unit, back: () -> Unit) {
    var name by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("edit") }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("NAYA PROJECT", color = Red, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Project ka naam", color = Grey) },
            modifier = Modifier.fillMaxWidth(), colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Txt, unfocusedTextColor = Txt, focusedBorderColor = Red))
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("edit" to "🎬 Video Edit", "test" to "🧪 App Test").forEach { (m, label) ->
                FilterChip(selected = mode == m, onClick = { mode = m }, label = { Text(label) },
                colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Red, selectedLabelColor = Txt))
            }
        }
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            httpPostForm("$base/projects", mapOf("name" to name, "mode" to mode)) { done() }
        }, colors = ButtonDefaults.buttonColors(containerColor = Red), modifier = Modifier.fillMaxWidth()) {
            Text("Banao", color = Txt)
        }
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = back) { Text("← Wapas", color = Grey) }
    }
}

@Composable
fun ChatScreen(base: String, pid: String, title: String, isGeneral: Boolean, onPickVideo: (android.net.Uri) -> Unit) {
    var msgs by remember { mutableStateOf(listOf<Msg>()) }
    var input by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val pickVideo = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { onPickVideo(it); msgs = msgs + Msg("user", "📎 Video upload ho rahi hai...") }
    }

    Column(Modifier.fillMaxSize().padding(12.dp)) {
        Text(title, color = Red, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(if (isGeneral) "General Chat — project banane se pehle expert se baat" else "Project Chat — editing memory ke saath",
            color = Grey, fontSize = 12.sp)
        Spacer(Modifier.height(8.dp))
        LazyColumn(state = listState, modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(msgs) { m ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = if (m.role == "user") Arrangement.End else Arrangement.Start) {
                    Surface(color = if (m.role == "user") Red else CardBg, shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.widthIn(max = 300.dp)) {
                        Text(m.text, color = Txt, modifier = Modifier.padding(10.dp), fontSize = 14.sp)
                    }
                }
            }
        }
        if (!isGeneral) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { pickVideo.launch("video/*") }, colors = ButtonDefaults.buttonColors(containerColor = CardBg)) { Text("📎 Video", color = Red) }
                Button(onClick = {
                    msgs = msgs + Msg("user", "▶ Auto Edit shuru")
                    httpPostForm("$base/projects/$pid/edit", mapOf()) {
                        onMain { msgs = msgs + Msg("editor", "✅ Queue mein lag gayi. Din bhar mein slow speed, raat ko fast. Status 'Refresh' se dekho.") }
                    }
                }, colors = ButtonDefaults.buttonColors(containerColor = Red)) { Text("▶ Auto Edit", color = Txt) }
            }
            Spacer(Modifier.height(8.dp))
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(value = input, onValueChange = { input = it },
                placeholder = { Text("Editor ko bolo...", color = Grey) },
                modifier = Modifier.weight(1f), colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Txt, unfocusedTextColor = Txt, focusedBorderColor = Red))
            Spacer(Modifier.width(8.dp))
            Button(onClick = {
                if (input.isBlank()) return@Button
                val msg = input; input = ""; busy = true
                msgs = msgs + Msg("user", msg)
                httpPostForm("$base/projects/$pid/chat", mapOf("message" to msg)) { body ->
                    onMain {
                        busy = false
                        try { msgs = msgs + Msg("editor", JSONObject(body).getString("reply")) }
                        catch (_: Exception) { msgs = msgs + Msg("editor", "PC se connect nahi ho paya — IP check karo, PC on hai?") }
                    }
                }
            }, colors = ButtonDefaults.buttonColors(containerColor = Red)) { Text("➤") }
        }
    }
}

fun client() = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS)
    .writeTimeout(120, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).build()

fun httpGet(url: String, cb: (String) -> Unit) {
    Thread {
        try { cb(client().newCall(Request.Builder().url(url).build()).execute().body!!.string()) }
        catch (_: Exception) { cb("") }
    }.start()
}

fun httpPostForm(url: String, fields: Map<String, String>, cb: (String) -> Unit = {}) {
    Thread {
        try {
            val body = FormBody.Builder().apply { fields.forEach { (k, v) -> add(k, v) } }.build()
            cb(client().newCall(Request.Builder().url(url).post(body).build()).execute().body!!.string())
        } catch (_: Exception) { cb("") }
    }.start()
}

fun uploadVideo(ctx: android.content.Context, base: String, pid: String, uri: android.net.Uri) {
    Thread {
        try {
            val stream = ctx.contentResolver.openInputStream(uri)!!
            val tmp = File.createTempFile("up", ".mp4", ctx.cacheDir)
            tmp.writeBytes(stream.readBytes())
            val body = MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart("file", "video.mp4", tmp.asRequestBody("video/mp4".toMediaType())).build()
            client().newCall(Request.Builder().url("$base/projects/$pid/upload").post(body).build()).execute()
            tmp.delete()
        } catch (_: Exception) {}
    }.start()
}
