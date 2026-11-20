package com.zinou.store

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

object AppInstaller {

    fun ensurePermission(activity: Activity): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
            !activity.packageManager.canRequestPackageInstalls()
        ) {
            activity.startActivity(
                Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${activity.packageName}")
                )
            )
            return false
        }
        return true
    }

    /** ينزّل الملف ويكمل من حيث توقف إذا انقطع الإنترنت */
    suspend fun download(
        activity: Activity,
        app: StoreApp,
        onProgress: (Int) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val dir = File(activity.cacheDir, "apks").apply { mkdirs() }
        val file = File(dir, "${app.packageName}-${app.versionCode}.apk")
        if (file.exists()) return@withContext file
        val part = File(dir, file.name + ".part")

        var attempt = 0
        while (true) {
            try {
                downloadOnce(activity, app.apkUrl, part, onProgress)
                break
            } catch (e: Exception) {
                attempt++
                if (attempt >= 4) throw e
                Thread.sleep(2000L * attempt)
            }
        }
        part.renameTo(file)
        file
    }

    private fun downloadOnce(activity: Activity, url: String, part: File, onProgress: (Int) -> Unit) {
        val have = if (part.exists()) part.length() else 0L
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 20000
        conn.readTimeout = 30000
        if (have > 0) conn.setRequestProperty("Range", "bytes=$have-")
        try {
            val code = conn.responseCode
            if (code == 416) return // الملف مكتمل مسبقاً
            if (code !in 200..299) error("HTTP $code")
            val resumed = code == 206
            var done = if (resumed) have else 0L
            val total = if (conn.contentLengthLong > 0) conn.contentLengthLong + done else -1L
            var lastPct = -1
            conn.inputStream.use { input ->
                FileOutputStream(part, resumed).use { out ->
                    val buf = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        done += n
                        if (total > 0) {
                            val pct = (done * 100 / total).toInt().coerceIn(1, 100)
                            if (pct != lastPct) {
                                lastPct = pct
                                activity.runOnUiThread { onProgress(pct) }
                            }
                        }
                    }
                }
            }
            if (total > 0 && done < total) error("incomplete")
        } finally {
            conn.disconnect()
        }
    }

    fun install(activity: Activity, file: File) {
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.files", file)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
    }
}
