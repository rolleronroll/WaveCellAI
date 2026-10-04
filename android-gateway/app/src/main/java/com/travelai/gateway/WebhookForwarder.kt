package com.travelai.gateway

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import android.telephony.SmsManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Settings and a short activity log, kept in SharedPreferences (demo grade, not encrypted). */
object GatewayConfig {
    const val K_URL = "url"
    const val K_SECRET = "secret"
    const val K_ALLOW = "allow"
    const val K_ON = "on"
    const val K_LOG = "log"

    fun prefs(c: Context): SharedPreferences = c.getSharedPreferences("gateway", Context.MODE_PRIVATE)
    fun url(c: Context) = prefs(c).getString(K_URL, "http://192.168.1.20:8000").orEmpty().trim().trimEnd('/')
    fun secret(c: Context) = prefs(c).getString(K_SECRET, "").orEmpty()
    fun allowedRaw(c: Context) = prefs(c).getString(K_ALLOW, "").orEmpty()
    fun enabled(c: Context) = prefs(c).getBoolean(K_ON, false)

    private fun tail(s: String) = s.filter { it.isDigit() }.takeLast(10)
    fun mask(s: String) = "***" + s.takeLast(4)

    /** Blank list means every numeric sender is forwarded. */
    fun allowed(c: Context, sender: String): Boolean {
        val list = allowedRaw(c).split(",").map { tail(it) }.filter { it.isNotEmpty() }
        return list.isEmpty() || tail(sender) in list
    }

    fun logText(c: Context) = prefs(c).getString(K_LOG, "").orEmpty()

    /** Logs sender tails and lengths only, never message text. */
    @Synchronized
    fun log(c: Context, line: String) {
        val time = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        val lines = (listOf("$time $line") + logText(c).lines().filter { it.isNotBlank() }).take(30)
        prefs(c).edit().putString(K_LOG, lines.joinToString("\n")).apply()
    }
}

/** Posts one incoming SMS to POST /api/sms/inbound, then texts the backend's reply back from this SIM. */
class WebhookForwarder(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {

    override fun doWork(): Result {
        val c = applicationContext
        val sender = inputData.getString("sender") ?: return Result.failure()
        val body = inputData.getString("body") ?: return Result.failure()
        val payload = JSONObject()
            .put("sender", sender)
            .put("body", body)
            .put("message_id", inputData.getString("id") ?: "")
            .put("received_at_ms", inputData.getLong("at", System.currentTimeMillis()))

        return try {
            val conn = (URL("${GatewayConfig.url(c)}/api/sms/inbound").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 10_000
                readTimeout = 45_000          // the backend may wait on an AI model
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("x-gateway-secret", GatewayConfig.secret(c))
            }
            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            when {
                code in 200..299 -> {
                    val reply = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
                    val text = reply.optString("body")
                    val to = reply.optString("to").ifBlank { sender }
                    if (text.isBlank()) {
                        GatewayConfig.log(c, "backend sent an empty reply")
                        Result.failure()
                    } else {
                        sendSms(to, text)
                        GatewayConfig.log(c, "replied to ${GatewayConfig.mask(to)} (${text.length} chars, tier ${reply.optString("tier")})")
                        Result.success()
                    }
                }
                code == 429 || code >= 500 -> retryOrFail("backend busy or down (HTTP $code)")
                else -> {
                    GatewayConfig.log(c, "backend refused the message (HTTP $code). Check the gateway secret.")
                    Result.failure()
                }
            }
        } catch (e: IOException) {
            retryOrFail("cannot reach backend")
        } catch (e: SecurityException) {
            GatewayConfig.log(c, "SMS permission missing. Tap Allow SMS access.")
            Result.failure()
        } catch (e: Exception) {
            GatewayConfig.log(c, "error: ${e.javaClass.simpleName}")
            Result.failure()
        }
    }

    private fun retryOrFail(why: String): Result =
        if (runAttemptCount < 2) {
            GatewayConfig.log(applicationContext, "$why, will retry")
            Result.retry()
        } else {
            GatewayConfig.log(applicationContext, "$why, gave up")
            Result.failure()
        }

    private fun sendSms(to: String, text: String) {
        val sm = if (Build.VERSION.SDK_INT >= 31) applicationContext.getSystemService(SmsManager::class.java)
        else @Suppress("DEPRECATION") SmsManager.getDefault()
        val parts = sm.divideMessage(text)
        if (parts.size == 1) sm.sendTextMessage(to, null, text, null, null)
        else sm.sendMultipartTextMessage(to, null, parts, null, null)
    }
}
