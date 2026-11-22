"""استخراج أيقونة التطبيق من ملف APK، بما فيها الأيقونات التكيفية (adaptive icons)."""
import io, logging, math, re, subprocess, tempfile
import xml.etree.ElementTree as ET
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


# ---------- رسم الأيقونات المرسومة كأشكال (VectorDrawable / shape) ----------
A = "{http://schemas.android.com/apk/res/android}"


def _hex(c):
    """#AARRGGBB/#RRGGBB/#ARGB/#RGB -> (rgb, alpha)"""
    c = c.lstrip("#")
    if len(c) in (3, 4):
        c = "".join(ch * 2 for ch in c)
    if len(c) == 6:
        c = "FF" + c
    return "#" + c[2:], int(c[:2], 16) / 255


def _num(v, d=0.0):
    if v is None:
        return d
    m = re.match(r"-?[\d.]+", str(v))
    return float(m.group()) if m else d


class _Ctx:
    def __init__(self, apk, arsc):
        self.apk, self.arsc, self.defs, self.n = apk, arsc, [], 0

    def ref_xml(self, ref):
        m = re.fullmatch(r"@(?:android:)?([0-9A-Fa-f]{8})", ref or "")
        if not m:
            return None
        x = _xml_of(self.apk, self.arsc, int(m.group(1), 16))
        return ET.fromstring(x) if x else None

    def paint(self, val, alpha=1.0):
        """يرجع (قيمة svg, شفافية)"""
        if not val:
            return "none", 0
        if val.startswith("#"):
            rgb, a = _hex(val)
            return rgb, a * alpha
        m = re.fullmatch(r"@(?:android:)?([0-9A-Fa-f]{8})", val)
        if m:
            col = _color(self.apk, self.arsc, int(m.group(1), 16))
            if col:
                rgb, a = _hex(col if len(col) != 9 else "#" + col[7:9] + col[1:7])
                return rgb, a * alpha
            g = self.ref_xml(val)
            if g is not None and g.tag == "gradient":
                return "url(#%s)" % self.gradient(g), alpha
        return "none", 0

    def gradient(self, g, box=None):
        self.n += 1
        gid = "g%d" % self.n
        stops = []
        items = g.findall("item")
        if items:
            for it in items:
                rgb, a = _hex(it.get(A + "color", "#000"))
                stops.append((_num(it.get(A + "offset")), rgb, a))
        else:
            cols = [g.get(A + k) for k in ("startColor", "centerColor", "endColor")]
            cols = [c for c in cols if c]
            for i, c in enumerate(cols):
                rgb, a = _hex(c)
                stops.append((i / max(1, len(cols) - 1), rgb, a))
        st = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%.3f"/>' % s for s in stops)
        typ = str(g.get(A + "type", "0"))
        if box:  # shape gradient على مربع 0..box
            cx, cy = _num(g.get(A + "centerX"), .5) * box, _num(g.get(A + "centerY"), .5) * box
            if typ in ("1", "2", "radial", "sweep"):
                r = _num(g.get(A + "gradientRadius"), box / 2)
                self.defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s">%s</radialGradient>' % (gid, cx, cy, r, st))
            else:
                ang = math.radians(_num(g.get(A + "angle")))
                dx, dy = math.cos(ang) * box / 2, -math.sin(ang) * box / 2
                self.defs.append('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>' % (gid, box/2-dx, box/2-dy, box/2+dx, box/2+dy, st))
        else:    # gradient داخل vector بإحداثيات المسار
            if typ in ("1", "radial"):
                self.defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s">%s</radialGradient>' % (
                    gid, _num(g.get(A + "centerX")), _num(g.get(A + "centerY")), _num(g.get(A + "gradientRadius"), 1), st))
            else:
                self.defs.append('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>' % (
                    gid, _num(g.get(A + "startX")), _num(g.get(A + "startY")), _num(g.get(A + "endX")), _num(g.get(A + "endY")), st))
        return gid


CAP = {"0": "butt", "1": "round", "2": "square"}
JOIN = {"0": "miter", "1": "round", "2": "bevel"}


def _vec_children(ctx, el):
    out = []
    for c in el:
        if c.tag == "group":
            px, py = _num(c.get(A + "pivotX")), _num(c.get(A + "pivotY"))
            t = "translate(%s %s) translate(%s %s) rotate(%s) scale(%s %s) translate(%s %s)" % (
                _num(c.get(A + "translateX")), _num(c.get(A + "translateY")), px, py,
                _num(c.get(A + "rotation")), _num(c.get(A + "scaleX"), 1), _num(c.get(A + "scaleY"), 1), -px, -py)
            out.append('<g transform="%s">%s</g>' % (t, _vec_children(ctx, c)))
        elif c.tag == "clip-path":
            ctx.n += 1
            ctx.defs.append('<clipPath id="c%d"><path d="%s"/></clipPath>' % (ctx.n, c.get(A + "pathData", "")))
            rest = list(el)[list(el).index(c) + 1:]
            holder = ET.Element("g")
            holder.extend(rest)
            out.append('<g clip-path="url(#c%d)">%s</g>' % (ctx.n, _vec_children(ctx, holder)))
            break
        elif c.tag == "path":
            d = c.get(A + "pathData", "")
            fill, fo = ctx.paint(c.get(A + "fillColor"), _num(c.get(A + "fillAlpha"), 1))
            stroke, so = ctx.paint(c.get(A + "strokeColor"), _num(c.get(A + "strokeAlpha"), 1))
            # gradient معرّف داخل aapt:attr
            for aa in c:
                if aa.tag.endswith("attr") and len(aa):
                    gid = ctx.gradient(aa[0])
                    if "fill" in (aa.get("name") or "").lower():
                        fill, fo = "url(#%s)" % gid, 1
                    else:
                        stroke, so = "url(#%s)" % gid, 1
            rule = "evenodd" if str(c.get(A + "fillType")) in ("1", "evenOdd") else "nonzero"
            out.append('<path d="%s" fill="%s" fill-opacity="%.3f" fill-rule="%s" stroke="%s" stroke-opacity="%.3f" stroke-width="%s" stroke-linecap="%s" stroke-linejoin="%s"/>' % (
                d, fill, fo, rule, stroke, so, _num(c.get(A + "strokeWidth")),
                CAP.get(str(c.get(A + "strokeLineCap")), "butt"), JOIN.get(str(c.get(A + "strokeLineJoin")), "miter")))
    return "".join(out)


def _xml_to_svg(ctx, root):
    if root.tag == "vector":
        vw, vh = _num(root.get(A + "viewportWidth"), 24), _num(root.get(A + "viewportHeight"), 24)
        body = _vec_children(ctx, root)
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s"><defs>%s</defs>%s</svg>' % (vw, vh, "".join(ctx.defs), body)
    if root.tag == "shape":
        box = 108
        solid, grad = root.find("solid"), root.find("gradient")
        if grad is not None:
            fill = "url(#%s)" % ctx.gradient(grad, box)
        elif solid is not None:
            fill, _ = ctx.paint(solid.get(A + "color"))
        else:
            return None
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><defs>%s</defs><rect width="108" height="108" fill="%s"/></svg>' % ("".join(ctx.defs), fill)
    return None


def _render_xml(apk, arsc, rid, size):
    x = _xml_of(apk, arsc, rid)
    if not x:
        return None
    try:
        svg = _xml_to_svg(_Ctx(apk, arsc), ET.fromstring(x))
    except Exception as e:
        print("vector render failed:", e)
        return None
    if not svg:
        return None
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w") as f:
        f.write(svg)
        f.flush()
        r = subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), f.name], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGBA")


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
    return _render_xml(apk, arsc, rid, size)


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
    if not xml:
        return None
    if "adaptive-icon" not in xml:                # أيقونة مرسومة بأشكال
        img = _render_xml(apk, arsc, rid, 256)
        return _png(img) if img else None
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
