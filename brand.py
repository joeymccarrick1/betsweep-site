# brand.py - shared BetSweep page pieces (exec'd by build_boards.py and build_results.py)
import os as _os
_H = HERE
LOGO = open(_os.path.join(_H, "logo_b64.txt")).read().strip(); LOGO_S = open(_os.path.join(_H, "logo_small_b64.txt")).read().strip()
BANNER = open(_os.path.join(_H, "banner_b64.txt")).read().strip()
WORDMARK = open(_os.path.join(_H, "wordmark_b64.txt")).read().strip()      # cream wordmark + red swoosh, transparent (dark backgrounds)
WORDMARK_INK = open(_os.path.join(_H, "wordmark_ink_b64.txt")).read().strip()  # ink wordmark for light backgrounds
NAMES = {"ARI":"Cardinals","LA":"Rams","ATL":"Falcons","CHI":"Bears","BAL":"Ravens","CLE":"Browns","BUF":"Bills","LV":"Raiders","CAR":"Panthers","PHI":"Eagles",
"DAL":"Cowboys","GB":"Packers","DEN":"Broncos","SEA":"Seahawks","HOU":"Texans","JAX":"Jaguars","IND":"Colts","TEN":"Titans","KC":"Chiefs","LAC":"Chargers","NE":"Patriots",
"NYJ":"Jets","NO":"Saints","NYG":"Giants","PIT":"Steelers","TB":"Buccaneers","SF":"49ers","WAS":"Commanders","CIN":"Bengals","DET":"Lions","MIA":"Dolphins","MIN":"Vikings"}
TEAMCOL = {"ARI":("#97233F","#000000"),"ATL":("#A71930","#000000"),"BAL":("#241773","#9E7C0C"),"BUF":("#00338D","#C60C30"),"CAR":("#0085CA","#101820"),"CHI":("#0B162A","#C83803"),
"CIN":("#FB4F14","#000000"),"CLE":("#311D00","#FF3C00"),"DAL":("#003594","#869397"),"DEN":("#FB4F14","#002244"),"DET":("#0076B6","#B0B7BC"),"GB":("#203731","#FFB612"),
"HOU":("#03202F","#A71930"),"IND":("#002C5F","#A2AAAD"),"JAX":("#006778","#D7A22A"),"KC":("#E31837","#FFB81C"),"LV":("#000000","#A5ACAF"),"LAC":("#0080C6","#FFC20E"),
"LA":("#003594","#FFA300"),"MIA":("#008E97","#FC4C02"),"MIN":("#4F2683","#FFC62F"),"NE":("#002244","#C60C30"),"NO":("#D3BC8D","#101820"),"NYG":("#0B2265","#A71930"),
"NYJ":("#125740","#000000"),"PHI":("#004C54","#A5ACAF"),"PIT":("#FFB612","#101820"),"SF":("#AA0000","#B3995D"),"SEA":("#002244","#69BE28"),"TB":("#D50A0A","#34302B"),
"TEN":("#0C2340","#4B92DB"),"WAS":("#5A1414","#FFB612")}
PLAYS = ''   # chalk play diagram is now a repeating CSS tile on .hd (template --plays)
SWOOSH = '''<svg class="swoosh" viewBox="0 0 220 22" aria-hidden="true"><circle cx="9" cy="14" r="5.5" fill="none" stroke="#d7332a" stroke-width="3"/><path d="M15 14.5 C 60 19, 120 19, 170 13 C 185 11, 196 8, 206 5" fill="none" stroke="#d7332a" stroke-width="3.4" stroke-linecap="round"/><path d="M194 2.5 L 209 4.2 L 199 14" fill="none" stroke="#d7332a" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'''
def lum(h):
    h = h.lstrip("#"); r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]; return 0.2126 * r + 0.7152 * g + 0.0722 * b
def badge(t):
    p, s = TEAMCOL.get(t, ("#444", "#999")); ink = "#101820" if lum(p) > 0.45 else "#ffffff"
    return f'<span class="badge" style="--p:{p};--s:{s};--ink:{ink}">{E(t)}</span>'
