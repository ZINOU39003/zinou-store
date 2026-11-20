package com.zinou.store

import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.pm.PackageInfoCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class StoreApp(
    val packageName: String,
    val name: String,
    val description: String,
    val icon: String,
    val versionCode: Long,
    val versionName: String,
    val apkUrl: String,
    val changelog: String,
    val size: String,
) {
    companion object {
        /** يقرأ الحقل بلغة الهاتف إن وُجد (مثل name_ar) وإلا يرجع للحقل العام */
        private fun JSONObject.loc(key: String, lang: String): String =
            optString("${key}_$lang").ifBlank { optString(key) }

        fun from(o: JSONObject, lang: String) = StoreApp(
            packageName = o.getString("packageName"),
            name = o.loc("name", lang),
            description = o.loc("description", lang),
            icon = o.optString("icon"),
            versionCode = o.getLong("versionCode"),
            versionName = o.optString("versionName"),
            apkUrl = o.getString("apkUrl"),
            changelog = o.loc("changelog", lang),
            size = o.optString("size"),
        )
    }
}

enum class AppStatus { NOT_INSTALLED, UPDATE, UP_TO_DATE }

fun installedVersion(ctx: Context, pkg: String): Long? = try {
    PackageInfoCompat.getLongVersionCode(ctx.packageManager.getPackageInfo(pkg, 0))
} catch (e: PackageManager.NameNotFoundException) {
    null
}

fun statusOf(ctx: Context, app: StoreApp): AppStatus {
    val v = installedVersion(ctx, app.packageName) ?: return AppStatus.NOT_INSTALLED
    return if (v < app.versionCode) AppStatus.UPDATE else AppStatus.UP_TO_DATE
}

object StoreRepository {
    suspend fun fetch(ctx: Context): List<StoreApp> = withContext(Dispatchers.IO) {
        val lang = ctx.getString(R.string.lang)
        val conn = URL(BuildConfig.STORE_URL + "?t=" + System.currentTimeMillis())
            .openConnection() as HttpURLConnection
        conn.connectTimeout = 15000
        conn.readTimeout = 15000
        conn.setRequestProperty("Cache-Control", "no-cache")
        try {
            val text = conn.inputStream.bufferedReader().use { it.readText() }
            val arr = JSONObject(text).getJSONArray("apps")
            (0 until arr.length()).map { StoreApp.from(arr.getJSONObject(it), lang) }
        } finally {
            conn.disconnect()
        }
    }
}
