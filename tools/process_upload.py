"""يعالج تطبيقاً مرفوعاً من لوحة التحكم:
يجمع أجزاء ملف APK، يقرأ بياناته وأيقونته، ينشره كإصدار، ويحدّث store/apps.json."""
import glob, json, os, re, shutil, subprocess, sys, zipfile
from pyaxmlparser import APK

OWNER_REPO = os.environ["GITHUB_REPOSITORY"]
MAIN_DIR = sys.argv[1]            # نسخة من الفرع main
INC = "incoming"
RAW = f"https://raw.githubusercontent.com/{OWNER_REPO}/main"
DL = f"https://github.com/{OWNER_REPO}/releases/download/"


def sh(*a, check=True):
    print("+", " ".join(a), flush=True)
    return subprocess.run(a, check=check)


def pick_icon(apk_path, apk):
    """يرجع (bytes, ext) لأيقونة التطبيق، أو None"""
    z = zipfile.ZipFile(apk_path)
    names = set(z.namelist())
    try:
        p = apk.get_app_icon()
    except Exception:
        p = None
    if p and p in names and p.rsplit(".", 1)[-1].lower() in ("png", "webp", "jpg"):
        return z.read(p), p.rsplit(".", 1)[-1].lower()
    best = None
    for n in names:
        ln = n.lower()
        if not ln.startswith("res/") or not ln.endswith((".png", ".webp")):
            continue
        if "launcher" not in ln or any(k in ln for k in ("foreground", "background", "monochrome")):
            continue
        size = z.getinfo(n).file_size
        if best is None or size > best[1]:
            best = (n, size)
    if best:
        return z.read(best[0]), best[0].rsplit(".", 1)[-1].lower()
    return None


def main():
    meta = json.load(open(f"{INC}/meta.json", encoding="utf-8"))
    parts = sorted(glob.glob(f"{INC}/part-*"))
    apk_path = "/tmp/app.apk"
    with open(apk_path, "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                shutil.copyfileobj(f, out)

    apk = APK(apk_path)
    pkg = apk.package
    if not pkg:
        sys.exit("الملف ليس تطبيق APK صالحاً")
    vc = int(apk.version_code or 1)
    vn = apk.version_name or str(vc)
    try:
        label = apk.application or ""
    except Exception:
        label = ""
    label = (meta.get("name") or label or pkg).strip()
    size_mb = os.path.getsize(apk_path) / 1024 / 1024
    print(f"package={pkg} versionCode={vc} versionName={vn} label={label}")

    # ---- إنشاء الإصدار ----
    slug = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-") or pkg.replace(".", "-")
    tag = f"{pkg}-v{vc}"
    asset = f"/tmp/{slug}.apk"
    shutil.copy(apk_path, asset)
    sh("gh", "release", "delete", tag, "-y", "--cleanup-tag", check=False)
    sh("gh", "release", "create", tag, asset, "--target", "main",
       "--title", f"{label} {vn}", "--notes", meta.get("changelog_ar") or meta.get("changelog") or vn,
       "--latest=false")

    # ---- تحديث apps.json ----
    store = os.path.join(MAIN_DIR, "store", "apps.json")
    data = json.load(open(store, encoding="utf-8"))
    apps = data["apps"]
    old = next((a for a in apps if a["packageName"] == pkg), None)
    entry = dict(old) if old else {"packageName": pkg, "name": label}

    if any((meta.get("changelog" + s) or "").strip() for s in ("", "_ar", "_fr")):
        for s in ("", "_ar", "_fr"):
            entry.pop("changelog" + s, None)   # ملاحظات الإصدار الجديد فقط
    for key in ("name", "description", "changelog"):
        for suf in ("", "_ar", "_fr"):
            v = (meta.get(key + suf) or "").strip()
            if v:
                entry[key + suf] = v
    if not old and not meta.get("name"):
        entry["name"] = label
    if old and not any(meta.get("changelog" + s) for s in ("", "_ar", "_fr")):
        for s in ("", "_ar", "_fr"):
            entry.pop("changelog" + s, None)   # لا نُبقي ملاحظات إصدار قديم

    entry.update({
        "versionCode": vc,
        "versionName": vn,
        "size": f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB",
        "apkUrl": DL + f"{tag}/{os.path.basename(asset)}",
    })

    icon = None
    up = glob.glob(f"{INC}/icon.*")
    if up:
        icon = (open(up[0], "rb").read(), up[0].rsplit(".", 1)[-1].lower())
    elif not old or not old.get("icon"):
        icon = pick_icon(apk_path, apk)
    if icon:
        os.makedirs(os.path.join(MAIN_DIR, "store", "icons"), exist_ok=True)
        for f in glob.glob(os.path.join(MAIN_DIR, "store", "icons", pkg + ".*")):
            os.remove(f)
        name = f"{pkg}.{icon[1]}"
        open(os.path.join(MAIN_DIR, "store", "icons", name), "wb").write(icon[0])
        entry["icon"] = f"{RAW}/store/icons/{name}?v={vc}"
    entry.setdefault("icon", "")

    if old:
        apps[apps.index(old)] = entry
    else:
        apps.append(entry)
    with open(store, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # حذف الإصدار القديم لنفس التطبيق (إن كان في هذا المستودع)
    if old and old.get("apkUrl", "").startswith(DL):
        old_tag = old["apkUrl"][len(DL):].split("/")[0]
        if old_tag != tag:
            open("/tmp/old_tag", "w").write(old_tag)
    open("/tmp/summary", "w").write(f"{label} {vn} ({pkg})")


if __name__ == "__main__":
    main()
