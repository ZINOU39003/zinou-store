package com.zinou.store

import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import coil.ImageLoader
import coil.decode.SvgDecoder
import coil.load
import com.google.android.material.button.MaterialButton
import com.google.android.material.progressindicator.LinearProgressIndicator

class AppAdapter(private val onAction: (StoreApp) -> Unit) :
    RecyclerView.Adapter<AppAdapter.VH>() {

    private var items: List<StoreApp> = emptyList()
    private var loader: ImageLoader? = null
    private val progress = mutableMapOf<String, Int>()

    fun submit(list: List<StoreApp>) {
        items = list
        notifyDataSetChanged()
    }

    fun setProgress(pkg: String, pct: Int?) {
        if (pct == null) progress.remove(pkg) else progress[pkg] = pct
        val i = items.indexOfFirst { it.packageName == pkg }
        if (i >= 0) notifyItemChanged(i)
    }

    override fun getItemCount() = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_app, parent, false)
    )

    override fun onBindViewHolder(h: VH, position: Int) {
        val app = items[position]
        val ctx = h.itemView.context
        h.name.text = app.name
        h.description.text = app.description
        h.description.visibility = if (app.description.isBlank()) View.GONE else View.VISIBLE
        val il = loader ?: ImageLoader.Builder(ctx.applicationContext)
            .components { add(SvgDecoder.Factory()) }
            .build().also { loader = it }
        h.icon.load(app.icon.ifBlank { null }, il) {
            crossfade(true)
            placeholder(R.drawable.ic_logo)
            error(R.drawable.ic_logo)
        }

        val status = statusOf(ctx, app)
        val ver = ctx.getString(R.string.version_fmt, app.versionName)
        h.version.text = if (app.size.isBlank()) ver else "$ver  •  ${app.size}"
        h.badge.visibility = if (status == AppStatus.UPDATE) View.VISIBLE else View.GONE

        val showNews = status == AppStatus.UPDATE && app.changelog.isNotBlank()
        h.changelog.visibility = if (showNews) View.VISIBLE else View.GONE
        h.changelog.text = ctx.getString(R.string.whats_new, app.changelog)

        val (label, bg, fg) = when (status) {
            AppStatus.NOT_INSTALLED -> Triple(R.string.install, R.color.brand, android.R.color.white)
            AppStatus.UPDATE -> Triple(R.string.update, R.color.accent, android.R.color.white)
            AppStatus.UP_TO_DATE -> Triple(R.string.open, R.color.tonal, R.color.brand)
        }
        h.action.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(ctx, bg))
        h.action.setTextColor(ContextCompat.getColor(ctx, fg))

        val p = progress[app.packageName]
        if (p != null) {
            h.progress.visibility = View.VISIBLE
            h.progress.isIndeterminate = p == 0
            if (p > 0) h.progress.setProgressCompat(p, true)
            h.action.text = if (p > 0) "$p%" else "…"
            h.action.isEnabled = false
        } else {
            h.progress.visibility = View.GONE
            h.action.setText(label)
            h.action.isEnabled = true
        }
        h.action.setOnClickListener { onAction(app) }
        h.itemView.setOnClickListener { if (p == null) onAction(app) }
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val icon: ImageView = v.findViewById(R.id.icon)
        val name: TextView = v.findViewById(R.id.name)
        val version: TextView = v.findViewById(R.id.version)
        val badge: TextView = v.findViewById(R.id.badge)
        val description: TextView = v.findViewById(R.id.description)
        val changelog: TextView = v.findViewById(R.id.changelog)
        val progress: LinearProgressIndicator = v.findViewById(R.id.progress)
        val action: MaterialButton = v.findViewById(R.id.action)
    }
}
