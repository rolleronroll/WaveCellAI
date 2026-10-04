package com.travelai.gateway

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import java.util.UUID

class SmsReceiver : BroadcastReceiver() {
    private val phoneLike = Regex("^\\+?\\d{7,15}$")

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        if (!GatewayConfig.enabled(context)) return
        val parts = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return

        // A long SMS arrives as several parts from the same sender; join them.
        for ((sender, group) in parts.groupBy { it.originatingAddress.orEmpty() }) {
            // Skip operator and service senders (names like "bKash"); replying to them costs money.
            if (!phoneLike.matches(sender)) {
                GatewayConfig.log(context, "skipped a non-number sender")
                continue
            }
            if (!GatewayConfig.allowed(context, sender)) {
                GatewayConfig.log(context, "skipped ${GatewayConfig.mask(sender)} (not in allowed list)")
                continue
            }
            val body = group.joinToString("") { it.messageBody.orEmpty() }.trim()
            if (body.isEmpty()) continue

            val work = OneTimeWorkRequestBuilder<WebhookForwarder>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setInputData(
                    workDataOf(
                        "sender" to sender,
                        "body" to body,
                        "id" to UUID.randomUUID().toString(),
                        "at" to group.first().timestampMillis,
                    )
                )
                .build()
            WorkManager.getInstance(context).enqueue(work)
            GatewayConfig.log(context, "received from ${GatewayConfig.mask(sender)} (${body.length} chars)")
        }
    }
}
