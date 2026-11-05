"""posters.py (was social.py until 10/26, when social.py became the Social page) - social posters for promoted bets (4:5 feed post, 1:1, 9:16 story) - called by build_promo.py.

Design-led rather than illustration-led: BetSweep type, team colours, the real FanDuel slip in a phone frame when the owner
has dropped a screenshot in in/promo_slips/<week>-<slot>.(png|jpg) (otherwise a BetSweep-styled slip is drawn), and the
model's numbers as the hook (matchup rank, this-season hit rate, model % and fair odds). No team logos (trademarks), no
stock art.
"""
import os, base64, html, json
E = html.escape

def _b64(path):
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode()

def odds_str(o): return "" if o is None else (f"+{int(o)}" if o > 0 else f"{int(o)}")

def slip_image(IN, pr):
    """(data URI, height/width ratio) of the owner's slip screenshot for this promo, or (None, None)."""
    for ext in ("png", "jpg", "jpeg"):
        p = os.path.join(IN, "promo_slips", f'{pr["week"]}-{pr["slot"]}.{ext}')
        if os.path.exists(p):
            try:
                from PIL import Image; w, h = Image.open(p).size; ratio = h / w
            except Exception: ratio = 1.6
            return f"data:image/{'jpeg' if ext != 'png' else 'png'};base64,{_b64(p)}", ratio
    return None, None

CSS = r"""
*{box-sizing:border-box;margin:0}
body{background:#0f141c;color:#efe9da;font-family:'IBM Plex Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.pst{position:relative;width:1080px;overflow:hidden;background:#0f141c;display:flex;flex-direction:column}
.pst.feed{height:1350px}.pst.square{height:1080px}.pst.story{height:1920px}
.bg{position:absolute;inset:0;background:url(data:image/png;base64,BANNER) center/cover no-repeat;opacity:.55;filter:saturate(.8)}
.bg2{position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,20,28,.2),rgba(15,20,28,.85) 38%,#0f141c 60%)}
.tear{position:absolute;left:-40px;right:-40px;top:TEARpx;height:150px;background:#d7332a;transform:rotate(-3deg);opacity:.95}
.tear::after{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(0,0,0,.08) 0 6px,transparent 6px 14px);mix-blend-mode:multiply}
.plays{position:absolute;inset:0;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='360' height='130' viewBox='0 0 360 130' fill='none' stroke='rgba(239,233,218,0.10)' stroke-width='1.6' stroke-linecap='round'%3E%3Cpath d='M24 18l10 10m0-10l-10 10M62 88l10 10m0-10l-10 10M150 20l10 10m0-10l-10 10M232 96l10 10m0-10l-10 10M306 26l10 10m0-10l-10 10'/%3E%3Ccircle cx='52' cy='48' r='6'/%3E%3Ccircle cx='192' cy='66' r='6'/%3E%3Ccircle cx='280' cy='60' r='6'/%3E%3Cpath d='M52 42C62 22 86 20 108 16' stroke-dasharray='4 4'/%3E%3Cpath d='M192 60C206 44 222 40 238 30'/%3E%3C/svg%3E") center/360px 130px repeat}
.in{position:relative;display:flex;flex-direction:column;height:100%;padding:52px 60px 44px}
.hd{display:flex;align-items:center;justify-content:space-between}
.hd img{height:70px} .hd .bm{display:flex;align-items:flex-start;gap:4px} .hd .tm{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:22px;color:#9aa3b2;line-height:1}
.hd .wk{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:24px;letter-spacing:.22em;text-transform:uppercase;color:#efe9da;border:2px solid #efe9da;padding:8px 16px;border-radius:4px}
.title{margin-top:TITLEpx}
.title .kick{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:26px;letter-spacing:.26em;text-transform:uppercase;color:#efe9da;opacity:.9}
.title h1{font-family:'Barlow',sans-serif;font-style:italic;font-weight:800;font-size:HSIZEpx;line-height:.95;letter-spacing:-.03em;color:#fff;text-shadow:0 6px 0 rgba(0,0,0,.35);white-space:nowrap}
.two{display:grid;grid-template-columns:minmax(0,1fr) PHONEpx;gap:36px;align-items:start;margin-top:26px}
.left{display:flex;flex-direction:column;gap:18px;min-height:0}
.odds{display:flex;align-items:baseline;gap:18px}
.odds b{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:170px;line-height:.85;letter-spacing:-.02em;color:#efe9da}
.odds span{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:26px;letter-spacing:.2em;text-transform:uppercase;color:#1493ff;line-height:1.1}
.model{font-size:24px;color:#9aa3b2;line-height:1.4} .model b{color:#efe9da}
.legs{display:flex;flex-direction:column;gap:10px;min-height:0;overflow:hidden}
.leg{display:grid;grid-template-columns:10px minmax(0,1fr) auto;gap:0 16px;align-items:center;background:rgba(22,29,40,.92);border:1px solid #2b3442;border-radius:12px;padding:12px 18px 12px 0;overflow:hidden}
.leg .bar{align-self:stretch;width:10px;border-radius:12px 0 0 12px}
.leg b{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:36px;letter-spacing:.01em;line-height:1}
.leg small{display:block;font-size:18px;color:#9aa3b2;margin-top:4px;line-height:1.3}
.leg small i{font-style:normal;color:#5fcf93;font-weight:600}
.leg .o{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:36px;font-variant-numeric:tabular-nums;color:#efe9da}
.legs.many .leg{padding:7px 14px 7px 0;border-radius:9px} .legs.many .leg b{font-size:24px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block} .leg b em{display:none} .legs.many .leg b em{display:inline;font-style:normal;font-weight:600;color:#9aa3b2;font-size:19px;margin-left:8px} .legs.many .leg small{display:none} .legs.many .leg .o{font-size:24px} .legs.many{gap:5px}
.legs.few .leg{padding:16px 20px 16px 0} .legs.few .leg b{font-size:42px} .legs.few .leg small{font-size:20px;margin-top:6px} .legs.few .leg .o{font-size:42px} .legs.few{gap:12px}
.odds.long b{font-size:132px}
.legs.mid .leg{padding:9px 16px 9px 0} .legs.mid .leg b{font-size:30px} .legs.mid .leg small{font-size:17px;margin-top:3px} .legs.mid .leg .o{font-size:30px} .legs.mid{gap:7px}
.phone{position:relative;width:PHONEpx;height:PHONEHpx;border-radius:42px;background:#0b0f15;border:6px solid #1d2633;box-shadow:0 30px 60px rgba(0,0,0,.6),0 0 0 2px #0b0f15;overflow:hidden}
.phone .notch{position:absolute;top:12px;left:50%;transform:translateX(-50%);width:120px;height:30px;background:#0b0f15;border-radius:20px;z-index:2}
.phone img{display:block;width:100%;height:auto;margin-top:34px}
.phone .fake{height:100%;background:#15181d;color:#fff;padding:60px 22px 20px;font-family:'IBM Plex Sans',sans-serif}
.phone .fake .t{display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:22px;margin-bottom:14px} .phone .fake .t span{font-size:30px}
.phone .fake .l{padding:12px 0;border-top:1px solid #2a2f36} .phone .fake .l b{display:block;color:#5aa2ff;font-size:22px;font-weight:700} .phone .fake .l small{display:block;color:#9aa3b2;font-size:13px;letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
.phone .fake .l em{float:right;font-style:normal;font-weight:700;font-size:22px}
.ft{margin-top:auto;display:flex;align-items:flex-end;justify-content:space-between;padding-top:22px;gap:20px}
.ft .site{font-family:'Barlow',sans-serif;font-style:italic;font-weight:800;font-size:40px;line-height:1;white-space:nowrap} .ft .site i{font-size:34px} .ft .site i{color:#d7332a;font-style:normal}
.ft .site span{display:block;font-family:'Barlow Condensed',sans-serif;font-style:normal;font-weight:600;font-size:18px;letter-spacing:.14em;text-transform:uppercase;color:#9aa3b2;margin-top:6px}
.ft .disc{font-size:16px;color:#6f7886;text-align:right;line-height:1.35;max-width:520px}
.callouts{display:grid;grid-template-columns:repeat(COLS,1fr);gap:12px;margin-top:20px} .callouts:empty{display:none}
.co{background:rgba(22,29,40,.92);border:1px solid #2b3442;border-radius:12px;padding:14px 16px;border-top:5px solid var(--c)}
.co b{display:block;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:26px;line-height:1.05}
.co span{display:block;font-size:17px;color:#9aa3b2;line-height:1.35;margin-top:6px} .co span i{font-style:normal;color:#efe9da;font-weight:600}
/* story */
.story .two{grid-template-columns:1fr;gap:26px} .story .phone{display:none}
.story .odds b{font-size:210px} .story .title h1{font-size:150px}
.story .leg b{font-size:44px} .story .leg .o{font-size:44px} .story .leg small{font-size:22px}
.story .legs.many .leg b{font-size:34px} .story .legs.many .leg b em{display:none} .story .legs.many .leg .o{font-size:34px} .story .legs.many .leg small{display:block;font-size:19px} .story .legs.many .leg{padding:10px 16px 10px 0}
.square .two{grid-template-columns:minmax(0,1fr) 300px;gap:28px} .square .odds b{font-size:120px} .square .title h1{font-size:84px} .square .callouts{display:none} .square .phone{width:300px;height:480px}
.square .leg b{font-size:28px} .square .leg .o{font-size:28px} .square .leg small{font-size:16px} .square .leg{padding:9px 14px 9px 0}
"""

def leg_row(l, color):
    rk = l.get("rank"); pos = l.get("pos", "")
    who = l["who"]; ml = l["disp"][len(who):].strip(" ·") if l["disp"].startswith(who) else l["disp"]
    mk = f'{l["opp"]} #{rk[0]} vs {"QB rush" if pos == "QB" else pos} TDs' if rk else ""
    hist = l.get("hist", "")
    sub = " · ".join(x for x in [ml, mk] if x)
    extra = f' <i>{E(hist)}</i>' if hist else ""
    return f'<div class="leg"><span class="bar" style="background:{color}"></span><div><b>{E(who)}<em>{E(ml)}</em></b><small>{E(sub)}{extra}</small></div><span class="o">{E(odds_str(l.get("o")))}</span></div>'

def poster_html(pr, kind, BANNER, WORDMARK, slip_src, colors, callouts, slip_ratio=None):
    n = len(pr["legs"]); many = n >= 7
    legs = "".join(leg_row(l, colors.get(l.get("tm", "").split("/")[0], "#d7332a")) for l in pr["legs"])
    if slip_src: phone = f'<div class="phone"><span class="notch"></span><img src="{slip_src}" alt=""></div>'
    else:
        rows = "".join(f'<div class="l"><em>{E(odds_str(l.get("o")))}</em><b>{E(l["who"])}</b><small>{E((l["disp"][len(l["who"]):].strip(" ·")) if l["disp"].startswith(l["who"]) else l["disp"])}</small></div>' for l in pr["legs"])
        phone = f'<div class="phone"><span class="notch"></span><div class="fake"><div class="t">{n} leg parlay <span>{E(odds_str(pr.get("fd")))}</span></div>{rows}</div></div>'
    cos = "".join(f'<div class="co" style="--c:{c}"><b>{E(t)}</b><span>{s}</span></div>' for t, s, c in callouts) if callouts else ""
    model = f'<b>Model {pr["p"]*100:.1f}%</b> to hit · fair {E(pr["fair"])}' if pr.get("p") else ""
    h1 = E(pr["title"])
    kick = pr.get("kick_line", f'Week {pr["week"]}')
    hsize = 118 if len(pr["title"]) <= 12 else (96 if len(pr["title"]) <= 18 else 80)
    tear = {"feed": 230, "square": 190, "story": 330}[kind]; titletop = {"feed": 70, "square": 40, "story": 120}[kind]
    phone_w = 360 if n <= 4 else 320; phone_h = 600 if n <= 4 else 560
    if slip_ratio: phone_h = min(phone_h, int((phone_w - 12) * slip_ratio) + 46)
    css = CSS.replace("BANNER", BANNER).replace("TEAR", str(tear)).replace("TITLE", str(titletop)).replace("HSIZE", str(hsize)).replace("PHONEH", str(phone_h)).replace("PHONE", str(phone_w)).replace("COLS", str(min(4, max(2, len(callouts) or 2))))
    return f'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@1,800&family=Barlow+Condensed:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{css}</style></head><body>
<div class="pst {kind}"><div class="bg"></div><div class="bg2"></div><div class="plays"></div><div class="tear"></div>
<div class="in">
 <div class="hd"><span class="bm"><img src="data:image/png;base64,{WORDMARK}" alt="BetSweep"><span class="tm">™</span></span><span class="wk">Week {pr["week"]} · Promoted</span></div>
 <div class="title"><div class="kick">{E(kick)}</div><h1>{h1}</h1></div>
 <div class="two">
  <div class="left">
   <div class="odds{" long" if len(odds_str(pr.get("fd"))) > 4 else ""}"><b>{E(odds_str(pr.get("fd")))}</b><span>on<br>FanDuel<br>{n} legs</span></div>
   <div class="model">{model}</div>
   <div class="legs{" many" if many else (" few" if n <= 4 else " mid")}">{legs}</div>
  </div>
  {phone}
 </div>
 <div class="callouts">{cos}</div>
 <div class="ft"><div class="site">betsweep<i>.co/b/w{pr["week"]}-{pr["slot"]}</i><span>Picks. Data. Edge. Sweep.</span></div><div class="disc">Model numbers are projections, not guarantees. Prices move. 21+ · 1-800-GAMBLER</div></div>
</div></div></body></html>'''
