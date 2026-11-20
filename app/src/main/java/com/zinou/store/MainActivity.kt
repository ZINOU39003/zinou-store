package com.zinou.store

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var adapter: AppAdapter
    private lateinit var swipe: SwipeRefreshLayout
    private lateinit var empty: TextView
    private lateinit var chipUpdates: Chip
    private var allApps: List<StoreApp> = emptyList()
    private var query = ""
    private var filter = R.id.chipAll

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // حذف ملفات التنزيل القديمة (أقدم من يومين)
        val old = System.currentTimeMillis() - 2 * 24 * 3600 * 1000L
        java.io.File(cacheDir, "apks").listFiles()?.filter { it.lastModified() < old }
            ?.forEach { it.delete() }

        adapter = AppAdapter(::onAction)
        findViewById<RecyclerView>(R.id.list).apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = this@MainActivity.adapter
        }
        empty = findViewById(R.id.empty)
        chipUpdates = findViewById(R.id.chipUpdates)
        swipe = findViewById(R.id.swipe)
        swipe.setColorSchemeResources(R.color.brand, R.color.brand_blue, R.color.accent)
        swipe.setOnRefreshListener { load() }

        findViewById<EditText>(R.id.search).addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                query = s?.toString()?.trim().orEmpty()
                render()
            }
        })
        findViewById<ChipGroup>(R.id.filters).setOnCheckedStateChangeListener { _, ids ->
            filter = ids.firstOrNull() ?: R.id.chipAll
            render()
        }
        findViewById<ImageButton>(R.id.btnLanguage).setOnClickListener { chooseLanguage() }

        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        UpdateWorker.schedule(this)
        load()
    }

    override fun onResume() {
        super.onResume()
        render() // تحديث الأزرار بعد الرجوع من شاشة التثبيت
    }

    private fun load() {
        swipe.isRefreshing = true
        lifecycleScope.launch {
            try {
                allApps = StoreRepository.fetch(this@MainActivity)
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, R.string.load_error, Toast.LENGTH_LONG).show()
            } finally {
                swipe.isRefreshing = false
                render()
            }
        }
    }

    private fun render() {
        if (!::adapter.isInitialized) return
        val updates = allApps.count { statusOf(this, it) == AppStatus.UPDATE }
        chipUpdates.text = if (updates > 0) "${getString(R.string.filter_updates)} ($updates)"
                           else getString(R.string.filter_updates)

        val list = allApps.filter { app ->
            val s = statusOf(this, app)
            val okFilter = when (filter) {
                R.id.chipUpdates -> s == AppStatus.UPDATE
                R.id.chipInstalled -> s != AppStatus.NOT_INSTALLED
                else -> true
            }
            okFilter && (query.isEmpty() ||
                app.name.contains(query, ignoreCase = true) ||
                app.description.contains(query, ignoreCase = true))
        }.sortedBy { if (statusOf(this, it) == AppStatus.UPDATE) 0 else 1 }

        adapter.submit(list)
        empty.visibility = if (list.isEmpty() && !swipe.isRefreshing) View.VISIBLE else View.GONE
    }

    private fun chooseLanguage() {
        val names = arrayOf("العربية", "Français", "English")
        val tags = arrayOf("ar", "fr", "en")
        val current = tags.indexOf(getString(R.string.lang))
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.language)
            .setSingleChoiceItems(names, current) { d, which ->
                d.dismiss()
                AppCompatDelegate.setApplicationLocales(
                    LocaleListCompat.forLanguageTags(tags[which])
                )
            }
            .show()
    }

    private fun onAction(app: StoreApp) {
        if (statusOf(this, app) == AppStatus.UP_TO_DATE) {
            packageManager.getLaunchIntentForPackage(app.packageName)?.let { startActivity(it) }
            return
        }
        if (!AppInstaller.ensurePermission(this)) {
            Toast.makeText(this, R.string.allow_install, Toast.LENGTH_LONG).show()
            return
        }
        adapter.setProgress(app.packageName, 0)
        lifecycleScope.launch {
            try {
                val file = AppInstaller.download(this@MainActivity, app) { pct ->
                    adapter.setProgress(app.packageName, pct)
                }
                adapter.setProgress(app.packageName, null)
                AppInstaller.install(this@MainActivity, file)
            } catch (e: Exception) {
                adapter.setProgress(app.packageName, null)
                Toast.makeText(
                    this@MainActivity,
                    getString(R.string.download_error) + ": " + e.message,
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }
}
