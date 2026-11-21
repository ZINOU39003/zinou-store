"""استخراج أيقونة التطبيق من ملف APK، بما فيها الأيقونات التكيفية (adaptive icons)."""
import io, logging, re
logging.disable(logging.CRITICAL)
try:
    from loguru import logger
    logger.remove()
except Exception:
    pass
from androguard.core.apk import APK
from androguard.core.axml import AXMLPrinter
from PIL import Image, ImageDraw

DENS = ["xxxhdpi", "xxhdpi", "xhdpi", "hdpi", "mdpi", "tvdpi", "ldpi", "nodpi", "anydpi"]
ANDROID_COLORS = {0x0106000B: "#FFFFFF", 0x0106000C: "#000000", 0x01060000: "#00000000",
                  0x01060001: "#000000", 0x01060002: "#FFFFFF"}


def _rank(q):
    for i, d in enumerate(DENS):
        if d in (q or ""):
            return i
    return len(DENS)


def _is_img(b):
    return b[:8] == b"\x89PNG\r\n\x1a\n" or b[:4] == b"RIFF" or b[:3] == b"\xff\xd8\xff"


def _configs(apk, arsc, rid):
    try:
        res = arsc.get_resolved_res_configs(rid)
    except Exception:
        return []
    return sorted(res, key=lambda cv: _rank(cv[0].get_qualifier()))


def _best_image(apk, arsc, rid):
    for cfg, val in _configs(apk, arsc, rid):
        if isinstance(val, str) and val.startswith("res/"):
            try:
                b = apk.get_file(val)
            except Exception:
                continue
            if b and _is_img(b):
                return Image.open(io.BytesIO(b)).convert("RGBA")
    return None


def _xml_of(apk, arsc, rid):
    for cfg, val in _configs(apk, arsc, rid):
        if isinstance(val, str) and val.endswith(".xml"):
            try:
                return AXMLPrinter(apk.get_file(val)).get_xml().decode("utf-8", "ignore")
            except Exception:
                pass
    return None


def _color(apk, arsc, rid):
    if rid in ANDROID_COLORS:
        return ANDROID_COLORS[rid]
    for cfg, val in _configs(apk, arsc, rid):
        if isinstance(val, str) and re.fullmatch(r"#[0-9A-Fa-f]{6,8}", val):
            v = val[1:]
            if len(v) == 8:                       # AARRGGBB -> RRGGBBAA
                v = v[2:] + v[:2]
            return "#" + v
    return None


def _layer(apk, arsc, ref, size):
    """يرجع طبقة بحجم size×size أو None"""
    if not ref:
        return None
    rid = int(ref, 16)
    img = _best_image(apk, arsc, rid)
    if img:
        return img.resize((size, size), Image.LANCZOS)
    col = _color(apk, arsc, rid)
    if col:
        return Image.new("RGBA", (size, size), col)
    return None


def _round(img):
    s = img.size[0]
    mask = Image.new("L", (s * 4, s * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s * 4 - 1, s * 4 - 1), radius=int(s * 4 * 0.22), fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask.resize((s, s), Image.LANCZOS))
    return out


def extract_icon(apk_path):
    """يرجع bytes بصيغة PNG أو None"""
    apk = APK(apk_path)
    arsc = apk.get_android_resources()
    icon = apk.get_attribute_value("application", "icon") or ""
    m = re.fullmatch(r"@(?:android:)?([0-9A-Fa-f]{8})", icon)
    if not m or arsc is None:
        return None
    rid = int(m.group(1), 16)

    # 1) أيقونة عادية (صورة)
    img = _best_image(apk, arsc, rid)
    if img:
        return _png(img.resize((256, 256), Image.LANCZOS) if img.size[0] < 256 else img)

    # 2) أيقونة تكيفية: خلفية + واجهة
    xml = _xml_of(apk, arsc, rid)
    if not xml or "adaptive-icon" not in xml:
        return None
    size = 432
    refs = dict(re.findall(r"<(background|foreground)[^>]*drawable=\"@(?:android:)?([0-9A-Fa-f]{8})\"", xml))
    fg = _layer(apk, arsc, refs.get("foreground"), size)
    if fg is None:
        return None
    bg = _layer(apk, arsc, refs.get("background"), size) or Image.new("RGBA", (size, size), "#FFFFFF")
    canvas = Image.alpha_composite(bg, fg)
    c = int(size * 18 / 108)                     # المنطقة الظاهرة 72dp من 108dp
    canvas = canvas.crop((c, c, size - c, size - c))
    return _png(_round(canvas))


def _png(img):
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()


if __name__ == "__main__":
    import sys
    data = extract_icon(sys.argv[1])
    if data:
        open(sys.argv[2], "wb").write(data)
        print("ok", len(data))
    else:
        print("no icon")
