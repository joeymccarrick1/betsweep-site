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
WM_AR = {'ARI': 10.59, 'ATL': 11.25, 'BAL': 7.06, 'BUF': 3.79, 'CAR': 4.86, 'CHI': 6.92, 'CIN': 10.91, 'CLE': 4.09, 'DAL': 5.71, 'DEN': 8.57, 'DET': 3.71, 'GB': 3.36, 'HOU': 10.0, 'IND': 4.04, 'JAX': 4.44, 'KC': 4.39, 'LA': 4.56, 'LAC': 5.22, 'LV': 5.71, 'MIA': 5.07, 'MIN': 3.1, 'NE': 4.24, 'NO': 4.29, 'NYG': 3.19, 'NYJ': 3.16, 'PHI': 5.9, 'PIT': 3.56, 'SEA': 9.23, 'SF': 5.14, 'TB': 4.29, 'TEN': 6.32, 'WAS': 6.67}
# owner 11/27 4:52 PM: "when in dark mode can you change the color? ... instead of Denver's dark blue can it be their orange". On the dark
# theme a one-colour dark wordmark is painted in the team's bright colour: the file is used as a mask (its shape, untouched) and the
# colour is laid through it. The light theme shows the file as it is. The Ravens mark has its own gold outline and is left alone.
WM_DARK = {"ARI": "#F4EFE3", "ATL": "#E0313E", "CIN": "#FB4F14", "DAL": "#B0B7BC", "DEN": "#FB4F14", "GB": "#FFB612", "HOU": "#E0313E", "IND": "#F4EFE3", "JAX": "#D7A22A",
           "LAC": "#FFC20E", "LV": "#A5ACAF", "NE": "#E0313E", "NO": "#D3BC8D", "NYG": "#F4EFE3", "NYJ": "#F4EFE3", "PHI": "#A5ACAF", "PIT": "#FFB612", "SEA": "#69BE28", "WAS": "#FFB612"}
def wm(t, text, dark=False):
    """a team's wordmark picture with its name kept as text for screen readers (owner 11/27: "team fonts ... throughout the site")"""
    k = ALIAS.get(t, t)
    return f'<span class="wm{" dk" if dark else ""}" data-wm="{html.escape(k)}">{html.escape(text)}</span>' if k in TEAMS else f"<span>{html.escape(text)}</span>"
def matchup(a, b, at=False):
    """logo + wordmark for two teams side by side (a promo page for a one-game slip); `at` only when a is known to be the visitor"""
    if ALIAS.get(a, a) not in TEAMS or ALIAS.get(b, b) not in TEAMS: return ""
    return f'<div class="wmrow"><span>{hm(a)}{wm(a, a)}</span><i>{"@" if at else "·"}</i><span>{wm(b, b)}{hm(b)}</span></div>'
# ---- jersey numbers (owner 11/27: "Jersey-number badges ... as a stand-in until headshots") ----------------------------------------
# A plain shirt shape in the team's two colours with the player's number on it. No team's uniform is drawn: the shape is the same for
# all 32, only the two colours change. COL holds the same two colours per team that brand.py paints the old badges with
# (tests/helmets.py keeps the two lists equal). Numbers come from the season roster the build already reads (in/roster_2026.csv,
# nflverse: full_name, team, jersey_number) - a public roster fact, nothing scraped.
COL = {"ARI": ("#97233F", "#000000"), "ATL": ("#A71930", "#000000"), "BAL": ("#241773", "#9E7C0C"), "BUF": ("#00338D", "#C60C30"), "CAR": ("#0085CA", "#101820"), "CHI": ("#0B162A", "#C83803"),
       "CIN": ("#FB4F14", "#000000"), "CLE": ("#311D00", "#FF3C00"), "DAL": ("#003594", "#869397"), "DEN": ("#FB4F14", "#002244"), "DET": ("#0076B6", "#B0B7BC"), "GB": ("#203731", "#FFB612"),
       "HOU": ("#03202F", "#A71930"), "IND": ("#002C5F", "#A2AAAD"), "JAX": ("#006778", "#D7A22A"), "KC": ("#E31837", "#FFB81C"), "LV": ("#000000", "#A5ACAF"), "LAC": ("#0080C6", "#FFC20E"),
       "LA": ("#003594", "#FFA300"), "MIA": ("#008E97", "#FC4C02"), "MIN": ("#4F2683", "#FFC62F"), "NE": ("#002244", "#C60C30"), "NO": ("#D3BC8D", "#101820"), "NYG": ("#0B2265", "#A71930"),
       "NYJ": ("#125740", "#000000"), "PHI": ("#004C54", "#A5ACAF"), "PIT": ("#FFB612", "#101820"), "SF": ("#AA0000", "#B3995D"), "SEA": ("#002244", "#69BE28"), "TB": ("#D50A0A", "#34302B"),
       "TEN": ("#0C2340", "#4B92DB"), "WAS": ("#5A1414", "#FFB612")}
def lum(h):
    h = str(h).lstrip("#"); r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; return 0.2126 * r + 0.7152 * g + 0.0722 * b
_RTEAM = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
def _pkey(n):
    import re
    n = re.sub(r"\.", "", str(n or "")).strip(); n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n, flags=re.I); return re.sub(r"\s+", " ", n).lower()
_NUMS = {}
def numbers(IN):
    """{(player key, team): number} and {player key: {numbers}} from in/roster_2026.csv; read once per folder, empty when the file is not there"""
    if IN not in _NUMS:
        import csv, os
        by, names = {}, {}
        try:
            with open(os.path.join(IN, "roster_2026.csv"), newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    n = str(r.get("jersey_number") or "").strip().split(".")[0]
                    if not n.isdigit() or not r.get("full_name"): continue
                    t = str(r.get("team") or "").strip(); t = _RTEAM.get(t, t); k = _pkey(r["full_name"])
                    by[(k, t)] = n; names.setdefault(k, set()).add(n)
        except Exception: by, names = {}, {}
        _NUMS[IN] = (by, names)
    return _NUMS[IN]
def num(IN, name, tm=""):
    """a player's jersey number as text, or "" - by name and team; by name alone only when every player of that name wears the same number"""
    by, names = numbers(IN); k = _pkey(name); t = ALIAS.get(tm, tm)
    if (k, t) in by: return by[(k, t)]
    ns = names.get(k) or set()
    return next(iter(ns)) if len(ns) == 1 and not t else ""
def jersey(t, n, cls=""):
    """the number tile; "" when the team or the number is not known"""
    t = ALIAS.get(t, t); n = str(n if n is not None else "").strip()
    if t not in COL or not n: return ""
    p, s = COL[t]; ink = "#101820" if lum(p) > 0.45 else "#ffffff"
    if lum(p) < 0.1 and lum(s) < 0.1: s = "#8a96a3"   # dark trim on a dark shirt would vanish
    return f'<i class="jn{(" " + cls) if cls else ""}" style="--j1:{p};--j2:{s};--jk:{ink}" role="img" aria-label="number {html.escape(n)}"><span>{html.escape(n)}</span></i>'
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
            "i.sktb[data-hm]{display:inline-block;height:18px;vertical-align:-4px}",
            ".sl .legs .ln i.hm{height:16px;vertical-align:-3px;margin-right:6px}",
            "/* 11/27 3:15 PM: board header is logo + abbreviation only, so it is shorter; wordmarks moved to section headings */",
            ".hd.hmh{padding-top:10px;padding-bottom:6px} .hd.hmh .score .pt{line-height:1}",
            "@media (max-width:560px){ .hd.hmh{padding:8px 14px 4px;row-gap:2px} .hd.hmh .tm [data-hm]{height:44px} .hd.hmh .tm{align-items:center} }",
            "@media (min-width:561px){ .hd.hmh .tm{flex-direction:row;align-items:center;gap:10px} .hd.hmh .tm.b{flex-direction:row-reverse} .hd.hmh .tm [data-hm]{height:56px;margin:0} }",
            ".gteamlist h3 .wm[data-wm]{display:inline-block;height:26px;width:124px;vertical-align:middle;margin-left:4px}",
            "h2.wmh .wm[data-wm]{display:inline-block;height:20px;width:84px;vertical-align:middle} h2.wmh{display:flex;align-items:center;gap:5px;flex-wrap:nowrap}",
            "a.wma .wm[data-wm]{display:inline-block;height:18px;width:96px;vertical-align:middle}",
            ".wmrow.l{justify-content:flex-start;margin:8px 16px 0}",
            "/* 11/27 4:30 PM: team colour wash behind a game header (boards, builder, Live) */",
            ".hd.wash{background:linear-gradient(90deg,color-mix(in srgb,var(--wa,transparent) 34%,transparent),transparent 44%,transparent 56%,color-mix(in srgb,var(--wb,transparent) 34%,transparent)),var(--plays) center/360px 130px repeat,var(--chalk)}",
            ".ghd.wash,.ghd2.wash{background-image:linear-gradient(90deg,color-mix(in srgb,var(--wa,transparent) 30%,transparent),transparent 42%,transparent 58%,color-mix(in srgb,var(--wb,transparent) 30%,transparent))}",
            "/* Today: weather picture on a slate row, and the live scoreboard strip */",
            ".game .gk i.wxi{font-style:normal;font-size:13px}",
            "#lstrip{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 10px;margin:0 0 4px;scrollbar-width:none} #lstrip::-webkit-scrollbar{display:none}",
            "#lstrip .lsc{flex:none;display:flex;align-items:center;gap:6px;padding:7px 10px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:800;font-size:17px}",
            "#lstrip .lsc i.hm{height:22px;margin:0;vertical-align:0} #lstrip .lsc span{color:var(--mute)} #lstrip .lsc small{font-family:var(--body);font-weight:600;font-size:11px;color:var(--mute);margin-left:4px;display:inline-flex;align-items:center;gap:5px}",
            "#lstrip .lsc.in{border-color:var(--red)} #lstrip .lsc.in small{color:var(--ink)} #lstrip .lsc.in em{width:7px;height:7px;border-radius:50%;background:var(--red);animation:lsp 1.4s ease-in-out infinite}",
            "@keyframes lsp{0%,100%{opacity:1}50%{opacity:.25}} @media (prefers-reduced-motion: reduce){ #lstrip .lsc.in em{animation:none} }"]
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
    for t in TEAMS: out.append(".wm[data-wm='%s']{background-image:url(/s/wm/%s.webp)}" % (t, t.lower()))   # must outrank .wm[data-wm], whose background shorthand clears the picture (1:35-2:05 PM 11/27: no wordmarks)
    for t in TEAMS: out.append("[data-wm='%s']{--war:%s}" % (t, WM_AR.get(t, 5)))
    # owner 11/27 1:08 PM: "I don't think I love the light outline. It like neons too much." No outline on any logo, and none on a
    # wordmark that has colour of its own. The black and navy marks would vanish on the dark theme, so those alone keep one faint
    # hairline there (not a glow), and nothing on the light theme.
    lt = []
    for t, c in WM_DARK.items():
        u = "/s/wm/%s.webp" % t.lower()
        out.append(".wm[data-wm='%s']{background-image:none;background-color:%s;-webkit-mask:url(%s) left center/contain no-repeat;mask:url(%s) left center/contain no-repeat}" % (t, c, u, u))
        lt.append("SEL .wm:not(.dk)[data-wm='%s']{background-image:url(%s);background-color:transparent;-webkit-mask:none;mask:none}" % (t, u))
    out.append(".wmrow span:last-child .wm[data-wm]{-webkit-mask-position:right center;mask-position:right center}")
    out.append(" ".join(x.replace("SEL", ":root[data-theme='light']") for x in lt))
    out.append("@media (prefers-color-scheme: light){ " + " ".join(x.replace("SEL", ":root:not([data-theme='dark'])") for x in lt) + " }")
    # owner 11/27 5:44 PM, on a promo card: "Can you stretch or shrink the team watermarks so that they match in size?" Where two
    # wordmarks sit side by side (a promo's matchup row, a First TD heading) each fills the same box exactly, so the pair matches.
    # A long thin mark gets taller and a short tall one gets wider; a lone wordmark elsewhere keeps its own shape.
    # owner 6:18 PM: "the broncos word mark stretch doesn't look right. Meet it in the middle somewhere." Same width for the pair, and each
    # mark's height sits halfway (geometric mean) between its own shape and the shared box, so no mark is pulled more than about 1.6x.
    out.append(".wmrow .wm[data-wm],h2.wmh .wm[data-wm]{background-size:100% 100%;-webkit-mask-size:100% 100%;mask-size:100% 100%;height:auto;aspect-ratio:var(--wmid, 4.2)}")
    out.append(".wmrow .wm[data-wm]{width:118px}")
    # owner 6:39 PM: "Can the wordmarks just be centered? So the center of the broncos B and the Steelers S are equal."
    out.append(".wmrow,.wmrow > span,h2.wmh{align-items:center} .wmrow .wm[data-wm],h2.wmh .wm[data-wm]{align-self:center;margin-top:0;margin-bottom:0;background-position:center;-webkit-mask-position:center;mask-position:center}")
    for t in TEAMS: out.append("[data-wm='%s']{--wmid:%.2f}" % (t, (WM_AR.get(t, 4.2) * 4.2) ** 0.5))
    # owner 11/27 5:47 PM, on a team page: "Maybe the logo and the watermark on the same line?" The logo sits beside the wordmark on
    # one row, at the same height; the record line and the buttons run full width under them.
    out.append(".pp header:has(h1 .wm[data-wm]){row-gap:8px} .pp header:has(h1 .wm[data-wm]) > [data-hm]{grid-row:1;grid-column:1;height:46px !important;align-self:center} .pp header:has(h1 .wm[data-wm]) > h1{grid-row:1;grid-column:2;margin:0;align-self:center} .pp header:has(h1 .wm[data-wm]) > .sub,.pp header:has(h1 .wm[data-wm]) > .acts{grid-column:1/-1}")
    out.append(".pp header h1 .wm[data-wm]{height:42px;width:min(230px,100%)}")
    # the bottom tab bar on its own layer: on an iPhone it came loose from the bottom mid-scroll (owner 1:26 PM, screenshot)
    out.append(".apptabs{transform:translateZ(0);-webkit-transform:translateZ(0)}")
    out += ["/* 11/27 night: jersey number - one plain shirt shape for all 32 teams, painted in the team's two colours */",
            ".jn{flex:none;position:relative;display:inline-block;width:38px;height:40px;font-style:normal;font-family:var(--display,'Barlow Condensed',sans-serif);font-weight:700;font-size:18px;line-height:1;color:var(--jk,#fff);font-variant-numeric:tabular-nums}",
            ".jn::before,.jn::after{content:'';position:absolute;inset:0;background:var(--j2);clip-path:polygon(29% 0,40% 0,50% 12%,60% 0,71% 0,100% 19%,91% 39%,80% 32%,80% 100%,20% 100%,20% 32%,9% 39%,0 19%)}",
            ".jn::after{inset:1.5px;background:var(--j1)}",
            ".jn span{position:absolute;left:20%;right:20%;top:36%;bottom:4%;z-index:1;display:grid;place-items:center;letter-spacing:-.02em}"]
    out += ["/* 11/27 night: a leg's last five games as five bars against its line (leg cards on Today and Model's Best, the builder's best-legs strip) */",
            '.h5{display:flex;align-items:center;gap:10px;min-width:0}',
            '.h5 .plot{--bh:30px;flex:none;position:relative;height:calc(var(--bh) + 13px)}',
            # 11/28 (owner's iPhone, 1:19 AM: the caption sat on top of the last two bars): the bars were flex items sized by flex-basis alone, and
            # Safari sizes a shrink-to-fit box from its flex items' CONTENT (the little numbers), not their flex-basis - so the plot came out
            # three bars wide with five bars in it. The row is a grid of fixed columns now (--bw, default 18px), which every engine adds up
            # the same way, and each bar carries the width itself as well.
            '.h5 ol{list-style:none;margin:0;padding:0;height:100%;display:grid;grid-auto-flow:column;grid-auto-columns:var(--bw,18px);justify-content:start;gap:5px}',
            '.h5 li{width:var(--bw,18px);min-width:0;display:grid;grid-template-rows:13px var(--bh);justify-items:stretch;text-align:center}',
            '.h5 li .v{font-size:10px;font-weight:600;line-height:13px;color:var(--mute);font-variant-numeric:tabular-nums;margin:0 -3px;white-space:nowrap}',
            '.h5 li .b{align-self:end;border-radius:3px 3px 0 0;background:color-mix(in srgb,var(--mute) 50%,transparent)}',
            '.h5 li.ov .b{background:var(--good)} .h5 li.ov .v{color:var(--ink)}',
            '.h5 .ln{position:absolute;left:-3px;right:-3px;border-top:1.5px dashed var(--ink);opacity:.85;pointer-events:none}',
            "/* 11/27 late: the opponent's logo under each bar; a game against this week's opponent is ringed */",
            '.h5.op{--lg:17px} .h5.op .plot{height:calc(var(--bh) + 13px + var(--lg))} .h5.op li{grid-template-rows:13px var(--bh) var(--lg)}',
            '.h5 li i.hm{height:12px;margin:4px 0 0;vertical-align:0;justify-self:center;align-self:start}',
            '.h5 li.same i.hm{outline:1.5px solid var(--ink);outline-offset:2px;border-radius:2px}',
            '.h5 p small.vs{color:var(--ink);font-weight:600}',
            '.h5 p{margin:0;font-size:12px;line-height:1.3;color:var(--mute);min-width:0} .h5 p b{display:block;font-family:var(--display);font-weight:700;font-size:16px;letter-spacing:.01em;color:var(--ink)}',
            '.h5 p small{display:block;font-size:11.5px} .h5 p small.good{color:var(--good)} .h5 p small.bad{color:var(--bad,#e07070)}']
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(f"[data-hm='{k}']" for k in keys) + "{background-image:url(/s/" + SET + "/%s.webp) !important}" % t.lower())
    for t in TEAMS:
        keys = [t] + [a for a, v in ALIAS.items() if v == t]
        out.append(",".join(big % ((k,) * 5) for k in keys) + "{background-image:url(/s/" + SET + "/%s-l.webp) !important}" % t.lower())
    return "\n".join(out) + "\n"
