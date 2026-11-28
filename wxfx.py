"""Weather across a game header (owner 11/27 8:31 PM: "I also love the idea of weather in the header").

A game whose kickoff forecast is plainly bad gets a faint moving layer behind its header: falling streaks for rain, drifting flakes for
snow, sideways streaks for wind. It is decoration on top of words the page already prints (the board's weather line, the Live header's
weather line), so it follows the same thresholds those words do and never shows where they would not say "likely":

  rain   the last look says rain is falling or moving in, or the chance is 60%+        (the board says "Rain likely" / "Raining ...")
  snow   the forecast types it as snow and the chance is 60%+                            (the board says "Snow likely")
  wind   no rain or snow as above, and wind 15+ mph or gusts 30+                         (the board says "Windy")
  none   a dome, a roof that can close, a dry or merely possible forecast, no forecast

kind() takes the forecast as either page holds it (the boards' dict: roof, pch, ptype, wind, gust, field; the Live page's: roof, pc, pt,
w, gu). tag() is the element a header carries; css() is the one stylesheet block (build_site.py adds it to the shared sheet). Nothing here
is a picture file: each layer is a small inline SVG used as a mask, painted in the page's own ink colour, moved with a transform only.
Readers who ask for reduced motion get the still pattern."""
import urllib.parse


def _n(v):
    try: return float(v)
    except Exception: return 0.0


def kind(w):
    """'r' (rain) / 's' (snow) / 'w' (wind) / '' for one game's forecast"""
    if not w: return ""
    roof = str(w.get("roof") or "").strip().lower()
    if roof in ("dome", "retractable", "closed"): return ""
    pc = _n(w.get("pch") if "pch" in w else w.get("pc")); pt = str((w.get("ptype") if "ptype" in w else w.get("pt")) or "").lower()
    wind = _n(w.get("wind") if "wind" in w else w.get("w")); gust = _n(w.get("gust") if "gust" in w else w.get("gu")); field = str(w.get("field") or "").lower()
    if field in ("rain now", "rain within 2 hours"): return "r"
    if pt.startswith("snow") and pc >= 60: return "s"
    if pc >= 60: return "r"
    if pt.startswith("snow") and pc >= 30: return ""          # "Snow possible": words only
    if pc < 30 and (wind >= 15 or gust >= 30): return "w"
    return ""


WORD = {"r": "rain", "s": "snow", "w": "wind"}


def tag(k):
    """the layer for a header; '' when there is no effect. The header must be positioned and isolated (css() does that for the board, builder and Live headers and for any element with class wxhost)."""
    return f'<i class="wxfx {k}" aria-hidden="true"></i>' if k in WORD else ""


def _svg(w, h, body):
    return "url(\"data:image/svg+xml," + urllib.parse.quote(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{body}</svg>", safe="/:=' ") + "\")"


def _lines(pts, dx, dy, sw):
    return "".join(f"<line x1='{x}' y1='{y}' x2='{x + dx}' y2='{y + dy}' stroke='black' stroke-width='{sw}' stroke-linecap='round'/>" for x, y in pts)


# one tile per layer; every mark sits wholly inside its tile so the pattern repeats without a seam
RAIN_A = _svg(120, 120, _lines([(8, 6), (31, 52), (47, 14), (66, 78), (83, 30), (102, 92), (20, 96), (112, 44)], 0, 15, 1.4))
RAIN_B = _svg(90, 90, _lines([(12, 20), (38, 62), (59, 8), (77, 46)], 0, 10, 1.1))
SNOW_A = _svg(120, 120, "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='black'/>" for x, y, r in [(10, 14, 2.2), (44, 40, 1.6), (78, 12, 2.0), (104, 58, 1.5), (26, 84, 1.8), (62, 100, 2.3), (92, 96, 1.4)]))
SNOW_B = _svg(80, 80, "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='black'/>" for x, y, r in [(8, 30, 1.1), (30, 8, 1.3), (52, 52, 1.0), (70, 22, 1.2), (40, 70, 1.1)]))
WIND_A = _svg(240, 96, _lines([(10, 12), (120, 40), (48, 70), (170, 86)], 46, 0, 1.3))
WIND_B = _svg(180, 72, _lines([(20, 22), (104, 54)], 30, 0, 1.0))


def css():
    return "\n".join([
        "/* weather across a game header (wxfx.py): rain, snow or wind when the kickoff forecast plainly says so */",
        ".hd.wash,.ghd.wash,.ghd2.wash,.wxhost{isolation:isolate}",
        ".ghd.wash,.ghd2.wash{position:relative;overflow:hidden}",
        ".wxfx{position:absolute;inset:0;z-index:-1;overflow:hidden;pointer-events:none;font-size:0}",
        ".wxfx::before,.wxfx::after{content:'';position:absolute;left:-40%;top:-70%;width:180%;height:240%;background:var(--ink);will-change:transform}",
        f".wxfx.r::before{{-webkit-mask:{RAIN_A} 0 0/120px 120px repeat;mask:{RAIN_A} 0 0/120px 120px repeat;opacity:.2;animation:wxr1 .62s linear infinite}}",
        f".wxfx.r::after{{-webkit-mask:{RAIN_B} 0 0/90px 90px repeat;mask:{RAIN_B} 0 0/90px 90px repeat;opacity:.12;animation:wxr2 .9s linear infinite}}",
        f".wxfx.s::before{{-webkit-mask:{SNOW_A} 0 0/120px 120px repeat;mask:{SNOW_A} 0 0/120px 120px repeat;opacity:.3;animation:wxs1 7s linear infinite}}",
        f".wxfx.s::after{{-webkit-mask:{SNOW_B} 0 0/80px 80px repeat;mask:{SNOW_B} 0 0/80px 80px repeat;opacity:.2;animation:wxs2 11s linear infinite}}",
        f".wxfx.w::before{{-webkit-mask:{WIND_A} 0 0/240px 96px repeat;mask:{WIND_A} 0 0/240px 96px repeat;opacity:.17;animation:wxw1 1.5s linear infinite}}",
        f".wxfx.w::after{{-webkit-mask:{WIND_B} 0 0/180px 72px repeat;mask:{WIND_B} 0 0/180px 72px repeat;opacity:.1;animation:wxw2 2.3s linear infinite}}",
        "/* each layer slides exactly one tile along its own (turned) axis, so the loop has no seam */",
        "@keyframes wxr1{from{transform:rotate(14deg) translate3d(0,0,0)}to{transform:rotate(14deg) translate3d(0,120px,0)}} @keyframes wxr2{from{transform:rotate(14deg) translate3d(0,0,0)}to{transform:rotate(14deg) translate3d(0,90px,0)}}",
        "@keyframes wxs1{0%{transform:translate3d(0,0,0)}50%{transform:translate3d(14px,60px,0)}100%{transform:translate3d(0,120px,0)}} @keyframes wxs2{0%{transform:translate3d(0,0,0)}50%{transform:translate3d(-10px,40px,0)}100%{transform:translate3d(0,80px,0)}}",
        "@keyframes wxw1{from{transform:rotate(-4deg) translate3d(0,0,0)}to{transform:rotate(-4deg) translate3d(240px,0,0)}} @keyframes wxw2{from{transform:rotate(-4deg) translate3d(0,0,0)}to{transform:rotate(-4deg) translate3d(180px,0,0)}}",
        ".wxfx.r::before,.wxfx.r::after{transform:rotate(14deg)} .wxfx.w::before,.wxfx.w::after{transform:rotate(-4deg)}",
        "/* a finished game has no weather left to show; the board marks it done, the Live header drops the layer itself */",
        ".card.done .wxfx{display:none}",
        "@media (prefers-reduced-motion: reduce){ .wxfx::before,.wxfx::after{animation:none !important} }",
    ]) + "\n"
