package com.travelai.gateway

import android.Manifest
import android.app.Activity
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {
    private lateinit var logView: TextView
    private lateinit var permView: TextView
    private val logListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == GatewayConfig.K_LOG) runOnUiThread { logView.text = GatewayConfig.logText(this) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = GatewayConfig.prefs(this)

        fun field(hint: String, value: String, secret: Boolean = false) = EditText(this).apply {
            this.hint = hint
            setText(value)
            setSingleLine()
            if (secret) inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val url = field("Backend URL, e.g. http://192.168.1.20:8000", GatewayConfig.url(this))
        val secret = field("Gateway secret (same as GATEWAY_SHARED_SECRET)", GatewayConfig.secret(this), true)
        val allow = field("Only these senders, comma separated (blank = every number)", GatewayConfig.allowedRaw(this))
        val on = Switch(this).apply { text = "Gateway on"; isChecked = GatewayConfig.enabled(this@MainActivity) }
        permView = TextView(this)
        logView = TextView(this).apply { text = GatewayConfig.logText(this@MainActivity); textSize = 12f }

        fun save() {
            prefs.edit()
                .putString(GatewayConfig.K_URL, url.text.toString().trim())
                .putString(GatewayConfig.K_SECRET, secret.text.toString())
                .putString(GatewayConfig.K_ALLOW, allow.text.toString().trim())
                .putBoolean(GatewayConfig.K_ON, on.isChecked)
                .apply()
        }

        val grant = Button(this).apply {
            text = "Allow SMS access"
            setOnClickListener { requestPermissions(arrayOf(Manifest.permission.RECEIVE_SMS, Manifest.permission.SEND_SMS), 1) }
        }
        val test = Button(this).apply {
            text = "Save and test backend"
            setOnClickListener {
                save()
                Thread {
                    val msg = try {
                        val c = URL("${GatewayConfig.url(this@MainActivity)}/api/health").openConnection() as HttpURLConnection
                        c.connectTimeout = 5_000
                        c.readTimeout = 5_000
                        "Backend answered HTTP ${c.responseCode}"
                    } catch (e: Exception) {
                        "Cannot reach backend: ${e.javaClass.simpleName}"
                    }
                    GatewayConfig.log(this@MainActivity, msg)
                }.start()
            }
        }
        on.setOnCheckedChangeListener { _, _ -> save() }

        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 40, 40, 40)
            val warn = TextView(this@MainActivity).apply {
                text = "Use a dedicated demo SIM. While on, text messages from phone numbers are sent to the backend " +
                    "and answered by SMS from this SIM, which your operator may charge for."
            }
            listOf(warn, url, secret, allow, on, permView, grant, test, logView).forEach { addView(it, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)) }
        }
        setContentView(ScrollView(this).apply { addView(col) })
    }

    override fun onResume() {
        super.onResume()
        GatewayConfig.prefs(this).registerOnSharedPreferenceChangeListener(logListener)
        val ok = listOf(Manifest.permission.RECEIVE_SMS, Manifest.permission.SEND_SMS)
            .all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        permView.text = if (ok) "SMS access: granted" else "SMS access: missing. Tap Allow SMS access."
        logView.text = GatewayConfig.logText(this)
    }

    override fun onPause() {
        GatewayConfig.prefs(this).unregisterOnSharedPreferenceChangeListener(logListener)
        super.onPause()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        onResume()
    }
}
