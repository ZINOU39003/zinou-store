package com.zinou.store

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/** يفحص المتجر في الخلفية كل 6 ساعات ويرسل إشعاراً عند وجود تحديث */
class UpdateWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        val apps = try {
            StoreRepository.fetch(applicationContext)
        } catch (e: Exception) {
            return Result.retry()
        }
        val updates = apps.filter { statusOf(applicationContext, it) == AppStatus.UPDATE }
        if (updates.isNotEmpty()) notify(updates)
        return Result.success()
    }

    private fun notify(updates: List<StoreApp>) {
        val ctx = applicationContext
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(
                    CHANNEL, ctx.getString(R.string.channel_name),
                    NotificationManager.IMPORTANCE_DEFAULT
                )
            )
        }
        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setColor(ContextCompat.getColor(ctx, R.color.brand))
            .setContentTitle(ctx.getString(R.string.updates_title))
            .setContentText(updates.joinToString(", ") { it.name })
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(1, n)
    }

    companion object {
        private const val CHANNEL = "updates"

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<UpdateWorker>(6, TimeUnit.HOURS)
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
                )
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                "zinou-updates", ExistingPeriodicWorkPolicy.KEEP, req
            )
        }
    }
}
