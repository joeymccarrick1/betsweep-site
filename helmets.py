"""Team helmets (owner 11/26: "Use this all over the site to represent the NFL teams").
The 32 pictures are the owner's own files, with the dark backdrop cut away (owner 11/27), cropped and resized (assets/hm/<team>.webp 110 px wide,
<team>-l.webp 240 px). Nothing is redrawn. A helmet is a background on an element that carries data-hm="<TEAM>": the old colour badges keep their
markup and their abbreviation (read by screen readers, hidden to the eye), and hm() gives a small stand-alone helmet."""
import html
TEAMS = ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LA","LAC","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]
ALIAS = {"LAR": "LA", "WSH": "WAS"}
def hm(t, cls=""):
    t = ALIAS.get(t, t)
    if t not in TEAMS: return ""
    return f'<i class="hm{(" " + cls) if cls else ""}" data-hm="{html.escape(t)}" role="img" aria-label="{html.escape(t)} helmet"></i>'
# The right-hand helmet of a matchup is mirrored so the two face each other (owner 11/27). A picture with lettering is never mirrored.
NOFLIP = ["LV", "SF"]
# Which pictures are up (owner 11/27): "nfl" = the official team logos he sent (assets/nfl, white backgrounds removed, nothing redrawn),
# "hm" = his own helmet set (assets/hm), kept ready "in case we ever have to change to these". One word switches the whole site.
SET = "nfl"
def css():
    big = ".tm > [data-hm='%s'],.pp header > [data-hm='%s'],.ghd [data-hm='%s'],.tdir [data-hm='%s'],.phm [data-hm='%s']"
    flip = ".tm.b [data-hm],.gteam.r [data-hm],.ghd2 .t.r [data-hm],.phm span i.hm:last-child,.game .gm i.hm:last-of-type"
    out = ["/* team helmets (helmets.py): the owner's pictures with the backdrop cut away */",
           "[data-hm]{background:transparent center/contain no-repeat !important;color:transparent !important;font-size:0 !important;box-shadow:none !important;text-shadow:none !important;width:auto !important;aspect-ratio:5/4;flex:none;padding:0 !important;border-radius:0 !important;filter:drop-shadow(0 2px 2px rgba(0,0,0,.38))}",
           (flip + "{transform:scaleX(-1)}") if SET == "hm" else "/* logos are never mirrored */ [data-hm]{filter:drop-shadow(0 0 1px rgba(255,255,255,.75)) drop-shadow(0 1px 2px rgba(0,0,0,.35))}",
           ",".join(f"[data-hm='{t}']" for t in NOFLIP) + "{transform:none !important}",
           "i.hm{display:inline-block;height:20px;vertical-align:-5px;margin-right:5px;font-style:normal}",
           ".phm{display:flex;flex-wrap:wrap;gap:6px 14px;margin:8px 16px 0} .phm span{display:inline-flex;gap:2px} .phm i.hm{height:36px;margin:0}",
           ".game .gm i.hm{height:22px;vertical-align:-4px}",
           "/* the matchup header on a board: helmets on the outside facing in, away left, home right */",
           "@media (min-width:561px){ .hd.hmh{align-items:end;padding-top:14px} .hd.hmh .tm{display:flex;flex-direction:column;align-items:flex-start;gap:0} .hd.hmh .tm.b{align-items:flex-end;text-align:right}"
           " .hd.hmh .tm [data-hm]{height:66px;margin:0 0 6px} .hd.hmh .tm span:not(.badge){margin-top:5px} .hd.hmh .score{align-self:end;padding-bottom:2px} }",
           ".hd.hmh.ah .tm.a span:not(.badge)::after{content:' \\00b7 away'} .hd.hmh.ah .tm.b span:not(.badge)::after{content:' \\00b7 home'}",
           "body.compact .card:not(.expanded) .hd.hmh .tm [data-hm]{height:50px}",
           ".ghd [data-hm]{height:46px} .dsum [data-hm]{margin-right:4px}",
           "@media (max-width:560px){ .hd.hmh .tm{column-gap:7px} .hd.hmh .tm [data-hm]{height:46px} .hd.hmh .tm b{font-size:36px} .hd.hmh.ah .tm span:not(.badge){letter-spacing:.06em;font-size:10px} }"]
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(f"[data-hm='{k}']" for k in keys) + "{background-image:url(/s/" + SET + "/%s.webp) !important}" % t.lower())
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(big % ((k,) * 5) for k in keys) + "{background-image:url(/s/" + SET + "/%s-l.webp) !important}" % t.lower())
    return "\n".join(out) + "\n"
