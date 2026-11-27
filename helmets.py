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
    return f'<i class="hm{(" " + cls) if cls else ""}" data-hm="{html.escape(t)}" role="img" aria-label="{html.escape(t)}"></i>'
# The right-hand helmet of a matchup is mirrored so the two face each other (owner 11/27). A picture with lettering is never mirrored.
NOFLIP = ["LV", "SF"]
# Which pictures are up (owner 11/27): "nfl" = the official team logos he sent (assets/nfl, white backgrounds removed, nothing redrawn),
# "hm" = his own helmet set (assets/hm), kept ready "in case we ever have to change to these". One word switches the whole site.
SET = "nfl"
# width / height of each wordmark file (assets/wm), so a board header can give every mark the same width and let its height follow
# (owner 11/27: "I love how the raiders word mark fits under the logo and LV ... Can every word mark fit like that?")
WM_AR = {'ARI': 5.14, 'ATL': 5.22, 'BAL': 5.07, 'BUF': 3.79, 'CAR': 2.59, 'CHI': 6.92, 'CIN': 5.71, 'CLE': 2.2, 'DAL': 5.71, 'DEN': 5.62, 'DET': 3.71, 'GB': 3.36, 'HOU': 6.43, 'IND': 4.04, 'JAX': 2.92, 'KC': 4.39, 'LA': 3.5, 'LAC': 3.67, 'LV': 5.71, 'MIA': 3.64, 'MIN': 2.31, 'NE': 4.24, 'NO': 4.29, 'NYG': 2.58, 'NYJ': 3.16, 'PHI': 5.9, 'PIT': 3.56, 'SEA': 6.32, 'SF': 5.14, 'TB': 3.6, 'TEN': 4.09, 'WAS': 3.19}
WM_DARK = ["ARI", "ATL", "BAL", "CIN", "DAL", "DEN", "GB", "HOU", "IND", "JAX", "LAC", "LV", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "WAS"]
def wm(t, text):
    """a team's wordmark picture with its name kept as text for screen readers (owner 11/27: "team fonts ... throughout the site")"""
    k = ALIAS.get(t, t)
    return f'<span class="wm" data-wm="{html.escape(k)}">{html.escape(text)}</span>' if k in TEAMS else f"<span>{html.escape(text)}</span>"
def matchup(a, b, at=False):
    """logo + wordmark for two teams side by side (a promo page for a one-game slip); `at` only when a is known to be the visitor"""
    if ALIAS.get(a, a) not in TEAMS or ALIAS.get(b, b) not in TEAMS: return ""
    return f'<div class="wmrow"><span>{hm(a)}{wm(a, a)}</span><i>{"@" if at else "·"}</i><span>{wm(b, b)}{hm(b)}</span></div>'
def css():
    big = ".tm > [data-hm='%s'],.pp header > [data-hm='%s'],.ghd [data-hm='%s'],.tdir [data-hm='%s'],.phm [data-hm='%s']"
    flip = ".tm.b [data-hm],.gteam.r [data-hm],.ghd2 .t.r [data-hm],.phm span i.hm:last-child,.game .gm i.hm:last-of-type"
    out = ["/* team helmets (helmets.py): the owner's pictures with the backdrop cut away */",
           "[data-hm]{background:transparent center/contain no-repeat !important;color:transparent !important;font-size:0 !important;box-shadow:none !important;text-shadow:none !important;width:auto !important;aspect-ratio:5/4;flex:none;padding:0 !important;border-radius:0 !important}",
           (flip + "{transform:scaleX(-1)}") if SET == "hm" else "/* logos are never mirrored, and carry no outline or shadow (owner 11/27: the light outline read as neon) */",
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
           "@media (max-width:560px){ .hd.hmh{padding:10px 14px 8px} .hd.hmh .tm{column-gap:7px} .hd.hmh .tm [data-hm]{height:40px;grid-row:1} .hd.hmh .tm b{font-size:32px;grid-row:1} }"]
    out += ["/* 11/27 sizing pass: bigger logos in the Live header, and small ones beside player names (builder cards, Social legs, Stock Market tiles) */",
            ".lg2 .ghd2 .t [data-hm]{height:40px !important}",
            "@media (max-width:560px){ .lg2 .ghd2 .t [data-hm]{height:36px !important} }",
            ".bqc .t b i.hm,.pcn b i.hm{height:18px;vertical-align:-4px;margin-right:6px}",
            ".post li .lg i.hm,.hcard li i.hm{height:16px;vertical-align:-3px;margin-right:6px}",
            "i.sktb[data-hm]{display:inline-block;height:18px;vertical-align:-4px}"]
    out += ["/* team wordmarks (owner's files, white removed): the name stays in the markup, the picture is drawn over it */",
            ".wm[data-wm]{display:block;font-size:0 !important;color:transparent !important;height:22px;width:118px;max-width:100%;background:left center/contain no-repeat}",
            ".tm.b .wm{background-position:right center;margin-left:auto}",
            ".hd.hmh .tm .wm{margin-top:4px}",
            ".hd.hmh.ah .tm.a span:not(.badge)::after,.hd.hmh.ah .tm.b span:not(.badge)::after{content:none}",
            ".hd.hmh.ah .tm.a b::after{content:'away'} .hd.hmh.ah .tm.b b::before{content:'home'}",
            ".hd.hmh.ah .tm b::after,.hd.hmh.ah .tm b::before{font:600 10px/1 var(--body, system-ui);font-style:normal;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 6px;vertical-align:middle}",
            ".hd.hmh .tm .wm{height:auto;aspect-ratio:var(--war, 5);max-height:42px}",
            "@media (min-width:561px){ .hd.hmh .tm .wm{width:190px;max-height:64px} }",
            "@media (max-width:560px){ .hd.hmh .tm .wm{grid-column:1/-1;grid-row:2;width:118px;margin-top:5px;align-self:start} .hd.hmh.ah .tm b::after,.hd.hmh.ah .tm b::before{font-size:9px;margin:0 4px} }",
            ".pp header h1 .wm{height:44px;width:min(320px,100%)} .tdir header h1 .wm{display:inline}",
            ".wmrow{display:flex;align-items:center;justify-content:center;gap:10px;margin:10px 0 2px} .wmrow span{display:flex;align-items:center;gap:8px;min-width:0} .wmrow i{font-style:normal;color:var(--mute);font-weight:700} .wmrow i.hm{height:34px;margin:0} .wmrow .wm{display:block;height:26px;width:120px} .wmrow span:last-child .wm{background-position:right center}"]
    for t in TEAMS: out.append("[data-wm='%s']{background-image:url(/s/wm/%s.webp)}" % (t, t.lower()))
    for t in TEAMS: out.append("[data-wm='%s']{--war:%s}" % (t, WM_AR.get(t, 5)))
    # owner 11/27 1:08 PM: "I don't think I love the light outline. It like neons too much." No outline on any logo, and none on a
    # wordmark that has colour of its own. The black and navy marks would vanish on the dark theme, so those alone keep one faint
    # hairline there (not a glow), and nothing on the light theme.
    dk = ",".join("[data-wm='%s']" % t for t in WM_DARK)
    out.append(dk + "{filter:drop-shadow(0 0 .5px rgba(255,255,255,.42))}")
    out.append(":root[data-theme='light'] .wm[data-wm]{filter:none} @media (prefers-color-scheme: light){ :root:not([data-theme='dark']) .wm[data-wm]{filter:none} }")
    # the bottom tab bar on its own layer: on an iPhone it came loose from the bottom mid-scroll (owner 1:26 PM, screenshot)
    out.append(".apptabs{transform:translateZ(0);-webkit-transform:translateZ(0)}")
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(f"[data-hm='{k}']" for k in keys) + "{background-image:url(/s/" + SET + "/%s.webp) !important}" % t.lower())
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(big % ((k,) * 5) for k in keys) + "{background-image:url(/s/" + SET + "/%s-l.webp) !important}" % t.lower())
    return "\n".join(out) + "\n"
