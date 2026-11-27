"""Team helmets (owner 11/26: "Use this all over the site to represent the NFL teams").
The 32 pictures are the owner's own files, cropped to the helmet and resized (assets/hm/<team>.webp 100 px wide, <team>-l.webp 220 px).
Nothing is redrawn. A helmet is a background on an element that carries data-hm="<TEAM>": the old colour badges keep their
markup and their abbreviation (read by screen readers, hidden to the eye), and hm() gives a small stand-alone helmet."""
import html
TEAMS = ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LA","LAC","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]
ALIAS = {"LAR": "LA", "WSH": "WAS"}
def hm(t, cls=""):
    t = ALIAS.get(t, t)
    if t not in TEAMS: return ""
    return f'<i class="hm{(" " + cls) if cls else ""}" data-hm="{html.escape(t)}" role="img" aria-label="{html.escape(t)} helmet"></i>'
def css():
    big = ".tm > [data-hm='%s'],.pp header > [data-hm='%s'],.ghd [data-hm='%s'],.tdir [data-hm='%s'],.phm [data-hm='%s']"
    out = ["/* team helmets (helmets.py) */",
           "[data-hm]{background:#0c0d10 center/cover no-repeat !important;color:transparent !important;font-size:0 !important;box-shadow:none !important;text-shadow:none !important;width:auto !important;aspect-ratio:5/4;overflow:hidden;flex:none;padding:0 !important}",
           "i.hm{display:inline-block;height:20px;border-radius:4px;vertical-align:-5px;margin-right:5px;font-style:normal}",
           ".phm{display:flex;flex-wrap:wrap;gap:6px 12px;margin:8px 16px 0} .phm span{display:inline-flex;gap:3px} .phm i.hm{height:34px;border-radius:6px;margin:0}",
           ".game .gm i.hm{height:22px;vertical-align:-4px}"]
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(f"[data-hm='{k}']" for k in keys) + "{background-image:url(/s/hm/%s.webp) !important}" % t.lower())
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(big % ((k,) * 5) for k in keys) + "{background-image:url(/s/hm/%s-l.webp) !important}" % t.lower())
    return "\n".join(out) + "\n"
