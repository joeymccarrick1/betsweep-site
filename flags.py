"""BetSweep player flags: one engine, used by the matchup boards and the parlay builder.

Every flag is a dict {k: 'good'|'bad'|'watch'|'info', tag: short pill text, txt: one-sentence explanation}.
Only THIS season's game log is used for form, floors and line hit-rates (no prior-season games), and the last three
games are always compared against the season so recency shows up. Nothing here invents data: a flag is only raised
when the input that supports it is present.

Usage:
    import flags
    F = flags.Engine(IN_DIR, WEEK)          # reads in/*.json once
    F.player(name)                          # -> list of flag dicts for that player (cached)
    F.leg(leg_dict)                         # -> player flags + line-specific hit-rate flag (needs player/market/line/team/opp)
    F.leg_hist(leg_dict)                    # -> (cleared, played) this season for that market/line, or None
    flags.warn_text(fl) / flags.good_text(fl)  # '; '-joined bad+watch / good texts for a flag list
"""
import json, os, csv, re

WRCB_TEAM = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "LAR": "LA", "WSH": "WAS", "JAC": "JAX"}   # ESPN/Clay team codes -> the model's
def _nn(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def _num(x):
    try: return float(str(x).replace("%", "").replace(",", ""))
    except Exception: return None

MAIN_STAT = {"QB": ("Pass Yds", "pass yds"), "RB": ("Rush Yds", "rush yds"), "WR": ("Rec Yds", "rec yds"), "TE": ("Rec Yds", "rec yds")}
VOL_STAT = {"QB": ("Pass Att", "attempts"), "RB": ("Rush Att", "carries"), "WR": ("Targets", "targets"), "TE": ("Targets", "targets")}
RANK_COL = {("QB", "Pass Yds"): "QB Pass Yds", ("QB", "Rush Yds"): "QB Rush Yds", ("RB", "Rush Yds"): "RB Rush Yds", ("RB", "Rec Yds"): "RB Rec Yds",
            ("WR", "Rec Yds"): "WR Rec Yds", ("TE", "Rec Yds"): "TE Rec Yds"}
# market -> defense-rank column for the leg-level matchup flag (the player-level flag only covers the position's headline stat)
LEG_RANK_COL = {("QB", "Passing Yards"): "QB Pass Yds", ("QB", "Rushing Yards"): "QB Rush Yds", ("QB", "Anytime TD"): "QB Rush TD",
                ("RB", "Rushing Yards"): "RB Rush Yds", ("RB", "Rush + Rec Yards"): "RB Rush Yds", ("RB", "Receiving Yards"): "RB Rec Yds", ("RB", "Longest Reception"): "RB Rec Yds", ("RB", "Receptions"): "RB Receptions", ("RB", "Anytime TD"): "RB Rush TD",
                ("WR", "Receiving Yards"): "WR Rec Yds", ("WR", "Longest Reception"): "WR Rec Yds", ("WR", "Receptions"): "WR Receptions", ("WR", "Anytime TD"): "WR Rec TD", ("WR", "Rush + Rec Yards"): "WR Rec Yds",
                ("TE", "Receiving Yards"): "TE Rec Yds", ("TE", "Longest Reception"): "TE Rec Yds", ("TE", "Receptions"): "TE Receptions", ("TE", "Anytime TD"): "TE Rec TD"}
LEG_RANK_LABEL = {"QB Pass Yds": "passing yards", "QB Rush Yds": "rushing yards", "QB Rush TD": "rushing TDs", "RB Rush Yds": "rushing yards", "RB Rec Yds": "receiving yards", "RB Receptions": "receptions", "RB Rush TD": "rushing TDs",
                  "WR Rec Yds": "receiving yards", "WR Receptions": "receptions", "WR Rec TD": "receiving TDs", "TE Rec Yds": "receiving yards", "TE Receptions": "receptions", "TE Rec TD": "receiving TDs"}
MARKET_STAT = {"Passing Yards": "Pass Yds", "Rushing Yards": "Rush Yds", "Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Longest Reception": "Longest Rec", "Rush + Rec Yards": "Rush+Rec Yds"}

try:
    from injweeks import norm as INJN, _t as INJT
except Exception:
    INJN = lambda x: x; INJT = lambda x: x

class Engine:
    def __init__(self, IN, WEEK):
        self.IN, self.WEEK = IN, int(WEEK)
        def vals(n):
            p = os.path.join(IN, n)
            if not os.path.exists(p): return []
            d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
        # game log, this season, weeks before the projection week
        gl = vals("gamelog.json"); self.GL = {}
        if gl:
            H = {c: i for i, c in enumerate(gl[0])}; self.GH = H
            for r in gl[1:]:
                if len(r) < 17 or not r[1]: continue
                wk = _num(r[0])
                if wk is None or wk >= self.WEEK: continue
                g = {"w": int(wk), "team": r[H["Team"]], "pos": r[H["Pos"]], "opp": r[H.get("Opponent", 4)]}
                for c in ("Pass Att", "Pass Yds", "Pass TD", "Rush Att", "Rush Yds", "Rush TD", "Targets", "Receptions", "Rec Yds", "Rec TD", "Longest Rec", "Fantasy Pts"):
                    g[c] = _num(r[H[c]]) if c in H and H[c] < len(r) else None
                g["Any TD"] = (g["Rush TD"] or 0) + (g["Rec TD"] or 0)
                g["Rush+Rec Yds"] = (g["Rush Yds"] or 0) + (g["Rec Yds"] or 0) if (g.get("Rush Yds") is not None or g.get("Rec Yds") is not None) else None
                self.GL.setdefault(r[1], []).append(g)
            for k in self.GL: self.GL[k].sort(key=lambda g: g["w"])
        # team -> position -> players with a game log (for vacated-volume math)
        self.BY_TEAM = {}
        for n, gs in self.GL.items():
            g = gs[-1]; self.BY_TEAM.setdefault(g["team"], {}).setdefault(g["pos"], []).append(n)
        # Mike Clay / ESPN WR-CB matchup rows for this week ('AUTO - WR CB Matchups' -> in/wrcb.json): the receiver's primary corner by
        # alignment, that corner's targets and fantasy points allowed per route, the defense's rank by alignment, and Clay's own matchup
        # deltas (T/R, F/R vs the receiver's season rates). Read by leg() for WR receiving legs -> the 'Coverage' flag.
        self.WRCB = {}
        try:
            rows = vals("wrcb.json"); H = {c: i for i, c in enumerate(rows[0])} if rows else {}
            def cell(r, c):
                i = H.get(c); return r[i] if i is not None and i < len(r) else ""
            for r in rows[1:]:
                if _num(cell(r, "Week")) != self.WEEK or not cell(r, "WR"): continue
                self.WRCB[_nn(cell(r, "WR"))] = {"cb": cell(r, "Primary CB"), "exp": _num(cell(r, "Expected Primary CB Exposure %")), "shadow": cell(r, "Projected Shadow"),
                    "cb_tr": _num(cell(r, "CB Coverage T/R")), "cb_fr": _num(cell(r, "CB Coverage F/R")), "cb_rt": _num(cell(r, "CB Routes / Snaps")),
                    "def_rank": _num(cell(r, "Alignment Def Rank")), "flag": cell(r, "CB Matchup Flag"), "conf": cell(r, "Flag Confidence"),
                    "d_tr": (lambda v: v / 100.0 if v is not None and abs(v) > 1 else v)(_num(cell(r, "Clay Matchup T/R delta"))), "d_fr": _num(cell(r, "Clay Matchup F/R delta")), "role": cell(r, "WR Role"), "src": cell(r, "Source Tier"),
                    "name": cell(r, "WR"), "team": WRCB_TEAM.get(cell(r, "WR Team"), cell(r, "WR Team")), "tgt": _num(cell(r, "Proj Target %"))}
        except Exception: self.WRCB = {}
        # snaps
        self.SNAPS = {}
        for r in vals("snaps.json")[1:]:
            if len(r) >= 9 and r[0]: self.SNAPS[r[0]] = {"season": _num(r[4]), "l2": _num(r[5]), "last": _num(r[6]), "signal": r[8]}
        # injury-shaped games (injweeks.py, nflverse snap counts + injury reports cached in in/ by build_snaps.py): a hobbled player's own
        # limited games and a teammate's fill-in games are set aside from form / usage / snap reads (owner 10/22, Henderson / Kiner)
        try:
            import injweeks as _INJ
            self.IW = _INJ.load(IN, self.WEEK)
        except Exception: self.IW = None
        # owner notes (RUNBOOK Step 2a copies the site's data/risk-notes.json here); this week's only
        self.NOTES = {}
        try:
            for r in (json.load(open(os.path.join(IN, "risk_notes.json"))) or []):
                if r.get("player") and r.get("status") and int(r.get("week") or self.WEEK) == self.WEEK: self.NOTES[_nn(r["player"])] = r
        except Exception: pass
        # context desk (11/4, owner: "take news into account"): every in/ctx_*.json is {"week", "players": [{player, team, pos, k, tag, txt, ...}],
        # "games": {"A-B": [{k, tag, txt}]}} written by news_desk.py, depth_check.py, def_inj.py, stakes.py, role_rising.py, consensus.py, refs.py.
        # Player notes become flags in player(); game notes go on the game cards (build_boards ctx_strip). Files for another week are ignored.
        self.CTX, self.CTX_G, self.CTX_CB = {}, {}, {}
        import glob as _glob
        for _f in sorted(_glob.glob(os.path.join(IN, "ctx_*.json"))):
            try:
                _d = json.load(open(_f))
                if int(_d.get("week") or self.WEEK) != self.WEEK: continue
                for _n in _d.get("players") or []:
                    if _n.get("player") and _n.get("txt"): self.CTX.setdefault(_nn(_n["player"]), []).append(dict(_n, src_file=os.path.basename(_f)))
                for _g, _ns in (_d.get("games") or {}).items():
                    self.CTX_G.setdefault(frozenset(_g.split("-")), []).extend(_ns)
                for _cb, _st in (_d.get("cbs") or {}).items(): self.CTX_CB[_nn(_cb)] = _st   # def_inj.py: corner -> {"status", "why", "team"}
            except Exception as _e: print("ctx skipped", _f, _e)
        # availability
        self.OUT, self.QUEST, self.OUT_BY_TEAM = {}, {}, {}
        for r in vals("avail.json")[1:]:
            if len(r) < 5 or str(r[0]) != str(self.WEEK): continue
            r = r + [""] * (13 - len(r))
            if r[4] == "OUT": self.OUT[r[1]] = {"team": r[2], "pos": r[3], "why": r[9]}; self.OUT_BY_TEAM.setdefault(r[2], []).append(r[1])
            elif r[4] == "QUESTIONABLE": self.QUEST[r[1]] = {"team": r[2], "pos": r[3], "why": r[9], "prac": r[12]}
            if r[4] in ("QUESTIONABLE", "CLEARED", "ACTIVE") and re.search(r"returning starter|season debut|first game back|activated|back this week", str(r[9]), re.I):
                self.RETURNERS = getattr(self, "RETURNERS", {}); self.RETURNERS[r[1]] = {"team": r[2], "pos": r[3], "why": r[9], "status": r[4]}
        # weather by team pair
        self.WX = {}
        for r in vals("weather.json")[1:]:
            if len(r) < 4 or str(r[0]) != str(self.WEEK): continue
            r = r + [""] * (16 - len(r))
            _vh = re.search(r"\((\w+) home\)", str(r[4]))
            if _vh and _vh.group(1) not in (r[2], r[3]): continue   # stale row: venue/forecast still last week's (the matchup columns roll before the weather refresh)
            self.WX[frozenset([r[2], r[3]])] = {"roof": r[5], "temp": _num(r[8]), "wind": _num(r[9]), "gust": _num(r[10]), "ptype": r[11], "pch": _num(r[12]), "risk": (r[14] or "").split()[0] if r[14] else ""}
        # defense ranks (season block then last-3 block, split by a repeated header row)
        rk = vals("ranks.json"); self.RANKS, self.RANKS3, self.DCOL = {}, {}, {}
        if rk:
            self.DCOL = {c: i for i, c in enumerate(rk[0][1:])}; cur = self.RANKS
            for r in rk[1:]:
                if not r: continue
                if str(r[0]).startswith("LAST 3"): cur = self.RANKS3; continue
                if r[0] in ("Defense", "") or len(r) < 2 or _num(r[1]) is None: continue
                cur[r[0]] = [int(float(x)) if _num(x) is not None else None for x in r[1:16]]
        # offense ranks (offranks.py, owner 10/29): the player's own team in the same stat, shown in every matchup flag's text. Text only -
        # the flag kinds (good / bad / info) and the rules that set them are unchanged, so no pick, filter or parlay gate moves.
        try:
            import offranks as _ORK
            self._ORK, self.OR = _ORK, _ORK.load(IN, self.WEEK)
        except Exception: self._ORK, self.OR = None, None
        # game scripts: team a -> (a, b, pa, pb, total, pLEAD, pCLOSE, pSHOOT, pTRAIL)
        self.SCRIPTS = {}
        for r in vals("scripts.json")[1:]:
            if len(r) >= 10 and r[0]: self.SCRIPTS[r[0]] = (r[0], r[1], _num(r[2]), _num(r[3]), _num(r[5]), _num(r[6]), _num(r[7]), _num(r[8]), _num(r[9]))   # r[4] is the margin, r[5] the total (fixed 10/23: reading from r[4] shifted every script one column - "Shootout" fired on close, low-scoring games and "Trail script" read the game total as a %)
        # boards tab: projected stat line + role per player
        self.PROJ = {}
        for r in vals("boards.json"):
            if r and len(r) >= 15 and r[2] and r[3] in ("QB", "RB", "WR", "TE") and r[0] and not str(r[0]).startswith("🏈") and "|" not in str(r[0]):
                r = r + [""] * (17 - len(r))
                self.PROJ[r[0]] = {"team": r[2], "pos": r[3], "opp": r[4], "ppr": _num(r[5]), "role": r[7], "Pass Yds": _num(r[8]), "Rush Yds": _num(r[9]), "Rec Yds": _num(r[10]), "Receptions": _num(r[11])}
        # market totals from the nflverse schedule
        self.SPREAD = {}   # owner 11/1: team -> points favored this week (closing-ish line from nflverse schedules)
        # veteran status (blowout rest risk): years in the league / age from the nflverse roster cached in in/
        self.VET = {}
        try:
            import datetime as _d
            with open(os.path.join(IN, "roster_2026.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    yx = _num(r.get("years_exp")); age = None
                    try: age = (_d.date.today() - _d.date.fromisoformat(r["birth_date"][:10])).days / 365.25
                    except Exception: pass
                    if r.get("full_name"): self.VET[_nn(r["full_name"])] = bool((yx is not None and yx >= 8) or (age is not None and age >= 30))
        except Exception: pass
        self.TOTAL = {}; played = {}   # played[week] = set of teams with a game that week (byes = the teams missing)
        p = os.path.join(IN, "games.csv")
        if os.path.exists(p):
            with open(p, newline="") as f:
                for g in csv.DictReader(f):
                    if g["season"] != "2026" or g["game_type"] != "REG": continue
                    try: wk = int(g["week"])
                    except Exception: continue
                    played.setdefault(wk, set()).update([g["away_team"], g["home_team"]])
                    if wk == self.WEEK:
                        self.TOTAL[frozenset([g["away_team"], g["home_team"]])] = _num(g["total_line"])
                        sp = _num(g.get("spread_line"))   # nflverse: home spread, positive = home favored
                        if sp is not None: self.SPREAD[g["home_team"]] = sp; self.SPREAD[g["away_team"]] = -sp
        # FanDuel's spread wins over the nflverse line when the game-lines pull has it (fresher, and it is the book the site prices against)
        try:
            import gamelines as _GLM
            for r in vals("gamelines.json")[1:]:
                if len(r) > 5 and r[3] == "Spread" and _num(r[5]) is not None:
                    ab = _GLM.TEAM_FULL.get(str(r[4]).strip())
                    if ab: self.SPREAD[ab] = -_num(r[5])   # "-6.5" on a team = favored by 6.5
        except Exception: pass
        allteams = set().union(*played.values()) if played else set()
        self.BYE = {wk: allteams - ts for wk, ts in played.items() if len(ts) < len(allteams)}   # {week: {teams on bye}}
        ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
        self.BYE = {wk: {ALIAS.get(t, t) for t in ts} for wk, ts in self.BYE.items()}
        # FanDuel main line per player + market (the rung priced nearest -112)
        self.MAIN = {}
        for r in vals("legboard.json")[1:]:
            if len(r) < 8 or not r[0] or r[1] not in MARKET_STAT: continue
            ln, od = _num(r[2]), _num(r[3])
            if ln is None or od is None: continue
            k = (r[0], r[1]); d = abs(od + 112)
            if k not in self.MAIN or d < self.MAIN[k][1]: self.MAIN[k] = (ln, d)
        self._cache = {}

    # ---------- helpers ----------
    def games(self, name): return self.GL.get(name, [])
    def qb_role(self, name, team):
        """'starter' | 'fill-in' | 'backup' for a team's QB who is OUT this week, judged from the game log - never from the order he
        appears in the availability tab. The reference is who started the team's most recent game (most pass attempts that week):
        starter  - he did, so his absence is a starting-QB change for the receivers;
        fill-in  - he did, but only because the season's main QB (most attempts, not OUT now) missed that game and is back
                   (Mariota starting while Daniels was hurt) - a return to normal, not a change;
        backup   - he did not start the last game (Mariota behind a healthy Daniels; a rookie behind the veteran) - nothing to flag."""
        qbs = [(n, gs) for n, gs in self.GL.items() if gs and gs[-1]["team"] == team and gs[-1]["pos"] == "QB"]
        if not qbs: return "starter"   # no log at all: do not second-guess the tab
        last_w = max(g["w"] for _, gs in qbs for g in gs if g["team"] == team)
        att_last = {n: max([g["Pass Att"] or 0 for g in gs if g["w"] == last_w and g["team"] == team] or [-1]) for n, gs in qbs}
        last = max(att_last, key=att_last.get)
        tot = {n: sum((g["Pass Att"] or 0) for g in gs if g["team"] == team) for n, gs in qbs}
        leader = max(tot, key=lambda n: (tot[n], max(g["w"] for g in self.GL[n])))
        if name != last: return ("still-out", last) if name == leader else "backup"   # season starter missing another game: same stand-in as last week
        if leader != name and leader not in self.OUT and att_last.get(leader, -1) <= 0: return "fill-in"
        return "starter"
    def avg(self, gs, c):
        v = [g[c] for g in gs if g.get(c) is not None]
        return (sum(v) / len(v)) if v else None
    def orank(self, team, col, last3=False):
        return self._ORK.rank(self.OR, team, col, "l3" if last3 else "season") if (self.OR and team and col) else None
    def otail(self, team, col, pos, lab):
        o = self.orank(team, col); o3 = self.orank(team, col, True)
        return f" Offense side: {team} {pos}s rank #{o} of 32 in {lab} produced{f' (last 3 weeks #{o3})' if o3 else ''}." if o else ""
    def drank(self, opp, col, last3=False):
        t = (self.RANKS3 if last3 else self.RANKS).get(opp)
        if not t or col not in self.DCOL or self.DCOL[col] >= len(t): return None
        return t[self.DCOL[col]]
    def leg_hist(self, l):
        """(cleared, played) this season for the leg's market/line. None when the market is not a game-log stat."""
        gs = self.games(l["player"])
        if not gs: return None
        m = l["market"]; ln = l.get("line")
        if m == "Anytime TD": return (sum(1 for g in gs if g["Any TD"] >= 1), len(gs))
        if m == "First TD": return None
        st = MARKET_STAT.get(m)
        if not st or ln is None: return None
        v = [g[st] for g in gs if g.get(st) is not None]
        if not v: return None
        return (sum(1 for x in v if x >= ln), len(v))

    # ---------- player flags ----------
    def player(self, name, team=None, pos=None, opp=None):
        key = (name, team, pos, opp)
        if key in self._cache: return self._cache[key]
        P = self.PROJ.get(name, {})
        team = team or P.get("team"); pos = pos or P.get("pos"); opp = opp or P.get("opp")
        gs = self.games(name); out = []
        if gs and (not pos or not team): pos = pos or gs[-1]["pos"]; team = team or gs[-1]["team"]   # projection tabs may not list him; the game log does
        add = lambda k, tag, txt: out.append({"k": k, "tag": tag, "txt": txt})
        # --- injury-shaped games: his own limited games, and fill-in games while a same-room teammate was hurt (teammate back now) ---
        lim = self.IW.limited(name, team) if (self.IW and team) else {}
        fill = self.IW.fill(name, team, pos) if (self.IW and team and pos) else {}
        recent = {g["w"] for g in gs[-3:]} if gs else set(); gs_all = gs
        lim_recent = {w: x for w, x in lim.items() if w in recent}; fill_recent = {w: x for w, x in fill.items() if w in recent}
        # first games back (owner OK 10/23): an injury-limited game in his last two -> WATCH. nflverse 2019-25 (RB/WR/TE): in the first two games
        # after one, players produced ~6% below their all-games average and ~17% below their healthy-games average vs comparable players
        # (Henderson 10/22: 9 rushing yards). The projection carries the same haircut through the Snap Trends factor (column M, Settings B278).
        last2 = {g["w"] for g in gs[-2:]} if gs else set()
        _ms0 = sorted(v for v in ((self.IW.snap.get((INJN(name), INJT(team))) or {}).values())) if (self.IW and team) else []
        first_back = bool(set(lim) & last2) and pos in ("RB", "WR", "TE") and (not _ms0 or _ms0[len(_ms0) // 2] >= 0.25)
        if lim_recent:
            wks = ", ".join(f"Week {w}: {x}" for w, x in sorted(lim_recent.items()))
            if first_back:
                add("watch", "First game back", f"Coming back from an injury-limited game ({wks}). History (2019-25): in their first two games back, backs and receivers produce about 17% less than their healthy-game average (about 6% under their full-season average) - the model's projection already takes that haircut. Do not stack him across slips.")
            elif self.IW.healthy_now(name):
                add("info", "Healthy again", f"Recent games were shaped by an injury ({wks}). He is off the injury report / practising in full this week, so those games are set aside from his trends: they are not a lost role.")
            else:
                st = self.IW.status(name)
                add("watch", "Playing hurt", f"Recent games were shaped by an injury ({wks}) and he is still on this week's report ({(st[2] or 'injury')}, {st[1] or st[0]}). Those games are set aside from his trends; the risk is the same thing happening again.")
        # owner 11/1: playing through it - not caught by the limited-game read above (no injury-shaped game yet), but his last game's snap
        # share fell hard and he is on this week's report (Saquon, Week 8: hurt the week before, could barely walk, still listed)
        if not lim_recent and pos in ("QB", "RB", "WR", "TE"):
            _sn = self.SNAPS.get(name) or {}; _st = self.IW.status(name) if self.IW else None
            if _st and _st[0] not in ("Out",) and not self.IW.healthy_now(name) and _sn.get("season") and _sn.get("last") is not None and _sn["season"] >= 0.45 and _sn["last"] <= 0.75 * _sn["season"]:
                add("watch", "Playing through it", f"On this week's injury report ({(_st[2] or 'injury')}, {_st[1] or _st[0]}) after his snap share fell to {_sn['last']*100:.0f}% last game ({_sn['season']*100:.0f}% for the season). If he plays, the risk is the same thing happening again.")
        # owner notes from the player-page panel (risk_feed kind=note -> data/risk-notes.json -> in/risk_notes.json, RUNBOOK Step 2a)
        _nt = self.NOTES.get(_nn(name))
        if _nt:
            _d = (" - " + _nt["detail"]) if _nt.get("detail") else ""
            if _nt["status"] == "HURT": add("bad", "Playing hurt (BetSweep)", f"BetSweep note: playing through an injury{_d}. Kept out of listed parlays and quick builds.")
            elif _nt["status"] == "LIMITED": add("bad", "Limited role (BetSweep)", f"BetSweep note: expect a limited role{_d}.")
            elif _nt["status"] == "STARTING": add("good", "Starting (BetSweep)", f"BetSweep note: confirmed starter{_d}.")
            elif _nt["status"] == "ROLE_UP": add("good", "Role up (BetSweep)", f"BetSweep note: bigger role this week{_d}.")
        # context desk notes (news, depth chart, role rising, consensus, trending) - one flag each, in the order the files were read
        for _c in self.CTX.get(_nn(name), []):
            if _c.get("k") in ("good", "bad", "watch", "info"): add(_c["k"], _c.get("tag") or "Context", _c["txt"])
        _ms = (self.SNAPS.get(name) or {}).get("season")
        if fill_recent and (_ms is None or _ms < 0.60):   # rotational players only: a starter's share does not "go back" when a backup returns
            who = sorted({t for t, _ in fill_recent.values()})
            def _st(t):
                r = self.IW.status(t) if self.IW else None
                if t in self.QUEST or (r and r[0] == "Questionable"): return f"{t} may return (Questionable)"
                if r and r[1] and not r[1].startswith("Full"): return f"{t} is practising ({r[1].replace(' Participation in Practice', '').replace(' In Practice', '').lower()})"
                return f"{t} is back"
            wks = ", ".join(f"Week {w} ({t}: {x.split(' - ')[0]})" for w, (t, x) in sorted(fill_recent.items()))
            add("watch", "Fill-in fading", f"His recent bump came while a teammate was hurt - {wks}. {'; '.join(_st(t) for t in who)} this week, so his share is likely to fall back toward his normal role; those games are set aside from his trends.")
        # --- replacement starter with no game log (fillin.py sets Engine.FILLIN = {name: note}) ---
        if name in getattr(self, "FILLIN", {}):
            add("bad", "Fill-in starter", self.FILLIN[name])
        # --- availability ---
        if name in self.QUEST:
            q = self.QUEST[name]; add("watch", "Questionable", f"Questionable: {q['why']}" + (f" (practice: {q['prac']})" if q.get("prac") else ""))
        def games_missed(last_w, tm):   # weeks between his last game and this one that his team actually played (byes don't count)
            return sum(1 for w in range(int(last_w) + 1, self.WEEK) if tm not in self.BYE.get(w, set()))
        if gs and len(gs) >= 1:
            last_w = gs[-1]["w"]; missed = games_missed(last_w, team)
            if missed >= 1 and name not in self.OUT:
                add("watch", "Back from absence", f"Did not play the last {missed} game{'s' if missed > 1 else ''} (last logged Week {last_w}); first game back is often a lighter workload.")
        if gs and len(gs) < 3: add("watch", f"{len(gs)} game sample", f"Only {len(gs)} game{'s' if len(gs) != 1 else ''} logged this season - projections lean on priors and role, not on his own numbers.")
        # --- teammates out / returning (vacated volume explains a projection above season average) ---
        vac = []
        if team and pos:
            same = {"QB": ("QB",), "RB": ("RB",), "WR": ("WR", "TE"), "TE": ("WR", "TE")}[pos]
            for tn, info in self.OUT.items():
                if info["team"] != team or tn == name: continue
                tg = self.games(tn)
                if info["pos"] == "QB" and pos != "QB":
                    role = self.qb_role(tn, team)
                    if role == "starter": add("watch", "QB out", f"Starting-QB change: {tn} is out ({info['why'][:70]}); passing-game projections carry extra uncertainty.")
                    elif role == "fill-in": add("info", "Starter back", f"{tn} (out: {info['why'][:50]}) only started while the regular starter was hurt; the regular starter is back under center, so the passing game is closer to its early-season shape than to the last box score.")
                    elif isinstance(role, tuple): add("info", "QB still out", f"{tn} misses another game; {role[1]} starts again, so the last box score already reflects this passing game.")
                    # a backup QB out: nothing to say about the passing game
                    continue
                if info["pos"] not in same or not tg: continue
                if info["pos"] == "QB" and self.qb_role(tn, team) not in ("starter", "fill-in"): continue   # a backup QB's attempts were never this QB's to inherit (Daniels does not "step into" Mariota's work)
                vc, vlab = VOL_STAT[info["pos"]]
                # reference = the games the two actually shared (same rule as qb_role: the log, not the order in the tab). His volume in those
                # games is what this player can inherit; if he only ever played while THIS player was out he was the stand-in, and his absence
                # hands nothing new over (the returning starter's own role is not 'vacated work').
                my_w = {g["w"] for g in gs} if gs else set()
                shared = [g for g in tg if g["w"] in my_w]
                if len(my_w) >= 2 and not shared: continue
                v = self.avg(shared, vc) if len(shared) >= 2 else self.avg(tg, vc)
                if v and v >= (8 if info["pos"] == "RB" else 5): vac.append((tn, info["pos"], v, vlab))
            if vac:
                vac.sort(key=lambda x: -x[2])
                txt = ", ".join(f"{tn} ({p}, {v:.1f} {lab}/g)" for tn, p, v, lab in vac)
                add("good", "Fill-in volume", f"Steps into vacated work: out this week - {txt}. The model moves that volume to the players left in the room.")
            # --- thinned room: several small absences at his position add up (Josh Cuevas, BAL TE, Week 6: Hibner + Smythe out = 89% of the
            # TE snaps and only 2.5 targets/g between them, so neither tripped the fill-in rule above; FanDuel priced his receptions on
            # a 1.0 target/g history and he caught 4). Uses snap shares, so a body with snaps but no catches still counts. ---
            if pos in ("RB", "WR", "TE"):
                my_s = self.SNAPS.get(name) or {}; my_l2 = my_s.get("l2") if my_s.get("l2") is not None else my_s.get("last")
                outs = []
                for tn, info in self.OUT.items():
                    if info["team"] != team or tn == name or info["pos"] != pos: continue
                    ts = self.SNAPS.get(tn) or {}; share = ts.get("l2") if ts.get("l2") is not None else ts.get("season")
                    if share is None: continue
                    tg = self.games(tn); vc = VOL_STAT[pos][0]
                    outs.append((tn, share, (self.avg(tg[-2:], vc) if tg else 0) or 0))
                vac_share = sum(o[1] for o in outs); vac_vol = sum(o[2] for o in outs)
                already = any(f["tag"] == "Fill-in volume" for f in out)
                if outs and my_l2 is not None and my_l2 <= 0.60 and (vac_share >= 0.35 or (len(outs) >= 2 and vac_share >= 0.25)):
                    # rank among the bodies left in the room (not the established starter): first in line inherits ~60%, second ~30%, rest ~10%
                    def _l2(n):
                        q = self.SNAPS.get(n) or {}; return q.get("l2") if q.get("l2") is not None else (q.get("last") or 0)
                    def _vol(n):   # recent volume first (Kendre Miller 8 carries/g beat CJ Donaldson's higher snap share for Etienne's work), snaps as the tiebreak
                        tg_ = self.games(n); return ((self.avg(tg_[-2:], VOL_STAT[pos][0]) if tg_ else 0) or 0, _l2(n) or 0)
                    left = sorted([n for n in self.BY_TEAM.get(team, {}).get(pos, []) if n not in self.OUT and (_l2(n) or 0) <= 0.60] + ([name] if name not in self.BY_TEAM.get(team, {}).get(pos, []) else []), key=lambda n: (-_vol(n)[0], -_vol(n)[1]))
                    rank = left.index(name) if name in left else 2
                    w = (0.6, 0.3, 0.1)[min(rank, 2)]
                    vlab = VOL_STAT[pos][1]; mine = (self.avg(gs[-2:], VOL_STAT[pos][0]) if gs else 0) or 0
                    est = mine + w * vac_vol
                    import math as _m
                    lam = est * (0.70 if pos != "RB" else 0.75)   # catches (or carries) expected if he inherits ~60% of the vacated work
                    p2 = min(0.90, 1 - _m.exp(-lam) * (1 + lam)); p3 = min(0.85, p2 - _m.exp(-lam) * lam * lam / 2)   # capped: room math, not a model
                    who = ", ".join(f"{tn.split()[-1]}" for tn, _, _ in outs)
                    add("good" if (rank == 0 and my_l2 >= 0.08) else "info", "Room thinned", f"Next man up{'' if rank == 0 else f' (#{rank+1} in line)'}: {who} out = {vac_share*100:.0f}% of the {pos} snaps and {vac_vol:.1f} {vlab}/g vacated. He had {my_l2*100:.0f}% of the snaps and {mine:.1f} {vlab}/g the last two; if he inherits ~{w*100:.0f}% of the vacated work that is ~{est:.1f} {vlab}" + (f" -> 2+ catches ~{p2*100:.0f}%, 3+ ~{p3*100:.0f}%" if pos != "RB" else "") + ". Books price thin-room players on their history" + ("; the model's fill-in rule also moved volume to him." if already else "; the model's fill-in rule did not fire (no single absence was big enough), so his projection is light too."))
            # returning teammate: a same-room player who missed last week but is active now
            for tn in self.BY_TEAM.get(team, {}).get(pos if pos != "TE" else "WR", []) + (self.BY_TEAM.get(team, {}).get("TE", []) if pos in ("WR", "TE") else []):
                if tn == name or tn in self.OUT: continue
                if pos == "QB":
                    # one QB plays: a returning QB only matters when HE is the team's season starter (most pass attempts) coming back
                    # to take the job from this player - a backup returning behind the starter (Caleb Williams) is nothing to flag
                    # "the starter" = whoever opened the season under center for this team (most attempts in the team's first logged game);
                    # it survives a long injury (Mayfield missing Weeks 4-6 is still TB's starter coming back for Jalon Daniels), and a
                    # backup who started while the starter was hurt (Mariota for Jayden Daniels) never qualifies. No week-1 data: season attempts.
                    _qbs = set(self.BY_TEAM.get(team, {}).get("QB", []) + [name, tn])
                    _games = [(g["w"], n, g["Pass Att"] or 0) for n in _qbs for g in (self.games(n) or []) if g["team"] == team]
                    if not _games: continue
                    _w0 = min(w for w, _, _ in _games)
                    _opener = max((x for x in _games if x[0] == _w0), key=lambda x: x[2])[1]
                    if _opener != tn or _opener == name: continue
                    # ...and he is coming back from an injury (on this week's report) or this player's run is short. A Week-1 starter who was
                    # benched (Lock behind Darnold's four straight starts, Wentz behind Kyler Murray) is not "returning" to anything.
                    _starts = {}
                    for w, n, a in _games: _starts.setdefault(w, (n, a)) if _starts.get(w, ("", -1))[1] >= a else _starts.__setitem__(w, (n, a))
                    _run = 0
                    for w in sorted(_starts, reverse=True):
                        if _starts[w][0] != name: break
                        _run += 1
                    if tn not in self.QUEST and _run >= 3: continue
                tg = self.games(tn)
                if tg and games_missed(tg[-1]["w"], team) >= 1 and (self.avg(tg[-3:], VOL_STAT[pos][0]) or 0) >= 4:   # his role going INTO the absence (last 3 logged), not a season average a demoted player can carry
                    if tn in self.QUEST:
                        add("info", f"{tn.split()[-1]} may return", f"Teammate may return: {tn} missed last week and is Questionable ({str(self.QUEST[tn].get('why', ''))[:60]}); if he plays, the targets/carries that flowed to others shrink.")
                    else:
                        add("watch", f"{tn.split()[-1]} returns", f"Teammate returning: {tn} missed last week and is back - the targets/carries that flowed to others ({self.avg(tg[-3:], VOL_STAT[pos][0]):.1f} {VOL_STAT[pos][1]}/g before he went out) shrink.")
        # --- target competition (owner, 10/21: Xavier Hutchinson rode Value/Moonshot builds while his targets slid and Tank Dell was about to return) ---
        # Receivers only. Competition = (a) a same-team WR/TE returning starter with NO 2026 game log (Dell: a year away, so the game-log based
        # 'teammate returning' check above cannot see him) entered on the availability tab as a returning starter / season debut, and
        # (b) a same-team WR/TE traded in within the last two logged weeks who drew 4+ targets in his first game (not a depth player
        # surfacing in the log - that is an injury symptom, not new competition). Either
        # one while this player's own last-3 targets are already below his season rate is a BAD flag (out of parlays); otherwise a watch.
        if pos in ("WR", "TE") and team and len(gs) >= 3:
            comp = []
            for tn, info in getattr(self, "RETURNERS", {}).items():
                if info["team"] == team and info["pos"] in ("WR", "TE") and tn != name and not self.games(tn):
                    comp.append(f"{tn} ({'back this week' if info['status'] != 'QUESTIONABLE' else 'expected back, Questionable'}: {str(info['why'])[:70].rstrip()})")
            wk_last = max(g["w"] for g in gs)
            for tn in self.BY_TEAM.get(team, {}).get("WR", []) + self.BY_TEAM.get(team, {}).get("TE", []):
                if tn == name or tn in self.OUT: continue
                tg = [g for g in self.games(tn) if g["team"] == team]
                if not tg or tg[0]["w"] < wk_last - 1: continue
                prior_elsewhere = any(g["team"] != team and g["w"] < tg[0]["w"] for g in self.games(tn))
                if (tg[0]["Targets"] or 0) >= 4 and prior_elsewhere:   # trades only: a depth receiver surfacing in the log is an injury symptom, not new competition
                    comp.append(f"{tn} (traded in Week {tg[0]['w']}, {tg[0]['Targets']:.0f} targets in his first game)")
            if comp:
                sa = self.avg(gs, "Targets"); l3 = self.avg(gs[-3:], "Targets")
                sliding = sa is not None and l3 is not None and sa > 0 and l3 < sa
                # the room's primary target (most targets/g this season among its WRs, or its TEs) keeps his work when a body returns; everyone below him is the one squeezed
                room = [n for n in self.BY_TEAM.get(team, {}).get(pos, []) if n not in self.OUT and len(self.games(n)) >= 2]
                top = max(room, key=lambda n: self.avg(self.games(n), "Targets") or 0) if room else None
                txt = f"Target competition: {'; '.join(comp)}. His own targets: {l3:.1f}/g over the last 3 vs {sa:.1f} season" + (" - already sliding before the room got more crowded." if sliding else ".") + (" He is the room's primary target, so this is a note, not a knock." if top == name else "")
                add("bad" if (sliding and top != name) else "watch", "Target competition", txt)
        # --- backfield competition (owner, 10/22: MarShawn Lloyd on Top Plays with Josh Jacobs primed to return and Pierre Strong moving ahead
        # of him). RBs only. A same-team RB returning starter with no 2026 game log (entered on the availability tab) takes the lead role back,
        # so every other back's carries shrink - BAD (out of top plays and parlays). Separately, a teammate who out-carried him last game
        # is named in the text so the reader sees the order.
        if pos == "RB" and team and gs:
            ret = [(tn, info) for tn, info in getattr(self, "RETURNERS", {}).items()
                   if info["team"] == team and info["pos"] == "RB" and tn != name and not self.games(tn)]
            if ret:
                wk_last = max(g["w"] for g in gs); mine = next((g for g in gs if g["w"] == wk_last), None)
                ahead = []
                for tn in self.BY_TEAM.get(team, {}).get("RB", []):
                    if tn == name or tn in self.OUT: continue
                    tg = next((g for g in self.games(tn) if g["w"] == wk_last and g["team"] == team), None)
                    if tg and mine and (tg.get("Rush Att") or 0) > (mine.get("Rush Att") or 0): ahead.append(f"{tn} out-carried him last game ({tg.get('Rush Att') or 0:.0f} to {mine.get('Rush Att') or 0:.0f})")
                txt = ("Backfield competition: " + "; ".join(f"{tn} ({'back this week' if info['status'] != 'QUESTIONABLE' else 'expected back, Questionable'}: {str(info['why'])[:70].rstrip()})" for tn, info in ret)
                       + ". A returning lead back takes the carries the rest of the room has been splitting" + ("; " + "; ".join(ahead) if ahead else "") + ".")
                add("bad", "Backfield competition", txt)
        # from here on (form, usage, floor, snaps, next man up, main-line hit rate) read his healthy, normal-role games only
        if (lim or fill) and gs:
            _g = [g for g in gs if g["w"] not in lim and g["w"] not in fill]
            if len(_g) >= 3: gs = _g
        # --- form: last 3 vs season (this season only) ---
        if pos in MAIN_STAT and len(gs) >= 4:
            st, lab = MAIN_STAT[pos]; sa = self.avg(gs, st); l3 = self.avg(gs[-3:], st)
            if sa and l3 is not None and sa >= 15:
                d = (l3 - sa) / sa
                if d >= 0.25: add("good", "Hot L3", f"Trending up: {l3:.0f} {lab}/g over the last 3 vs {sa:.0f} season ({d*100:+.0f}%).")
                elif d <= -0.25: add("bad", "Cold L3", f"Trending down: {l3:.0f} {lab}/g over the last 3 vs {sa:.0f} season ({d*100:+.0f}%).")
            vc, vlab = VOL_STAT[pos]; va = self.avg(gs, vc); v3 = self.avg(gs[-3:], vc)
            if va and v3 is not None and va >= 3:
                d = (v3 - va) / va
                if d >= 0.25: add("good", f"{vlab.title()} up", f"Usage rising: {v3:.1f} {vlab}/g last 3 vs {va:.1f} season.")
                elif d <= -0.25: add("bad", f"{vlab.title()} down", f"Usage falling: {v3:.1f} {vlab}/g last 3 vs {va:.1f} season.")
        # --- floor / volatility ---
        if pos in MAIN_STAT and len(gs) >= 4:
            st, lab = MAIN_STAT[pos]; sa = self.avg(gs, st); v = [g[st] for g in gs if g.get(st) is not None]
            if sa and sa >= 20 and v:
                lows = sum(1 for x in v if x < 0.4 * sa)
                if lows == 0 and min(v) >= 0.6 * sa: add("good", "Steady floor", f"Every game this season at least {min(v):.0f} {lab} (60%+ of his {sa:.0f} average).")
                elif lows >= 2: add("bad", "Boom/bust", f"{lows} of {len(v)} games under 40% of his {sa:.0f} {lab} average - wide range of outcomes.")
        # --- snaps ---
        s = self.SNAPS.get(name)
        if s and s["season"] and s["last"] is not None and not (lim_recent or fill_recent):
            l2 = s["l2"] if s["l2"] is not None else s["last"]
            # a slipping share is a risk, not a note: -10 pts vs season, or a last-two share under 45% for someone who was a 50%+ player
            if s["signal"].startswith("SNAPS DOWN") or (l2 - s["season"] <= -0.10) or (l2 < 0.45 and s["season"] >= 0.50):
                add("bad", "Snaps down", f"Snap share slipping: {s['last']*100:.0f}% last game, {l2*100:.0f}% last two vs {s['season']*100:.0f}% season - the role is shrinking, whatever the season line says.")
            elif s["signal"].startswith("SNAPS UP") or (l2 - s["season"] >= 0.12):
                add("good", "Snaps up", f"Snap share growing: {s['last']*100:.0f}% last game, {l2*100:.0f}% last two vs {s['season']*100:.0f}% season.")
        # --- next man up: a same-room teammate whose snaps are rising past him, or who out-targeted him last game ---
        if team and pos in ("WR", "TE", "RB") and gs:
            room = self.BY_TEAM.get(team, {}).get(pos, [])   # same position only: a WR is passed by a WR, a TE by a TE
            my_s = self.SNAPS.get(name) or {}; my_l2 = my_s.get("l2") if my_s.get("l2") is not None else my_s.get("last")
            last_w = gs[-1]["w"]; my_tg = next((g.get("Targets") if pos != "RB" else (g.get("Rush Att") or 0) + (g.get("Targets") or 0) for g in gs if g["w"] == last_w), None)
            risers = []
            for tn in room:
                if tn == name or tn in self.OUT: continue
                if lim_recent: break   # his own recent games were injury-limited: a teammate "passing" him there is the injury, not the depth chart
                if self.IW and set(self.IW.fill(tn, team, pos)) & {g["w"] for g in gs_all[-3:]}: continue   # the riser's bump is fill-in for a hurt teammate who is back
                ts = self.SNAPS.get(tn) or {}; tl2 = ts.get("l2") if ts.get("l2") is not None else ts.get("last"); tse = ts.get("season")
                tg = self.games(tn); t_last = next((g for g in tg if g["w"] == last_w), None)
                t_tg = (t_last.get("Targets") if pos != "RB" else (t_last.get("Rush Att") or 0) + (t_last.get("Targets") or 0)) if t_last else None
                if tse is not None and tse >= 0.65: continue   # an established starter is not "next man up"
                if tl2 is None or tl2 < 0.30: continue          # a riser has to have a real share already
                snap_rise = tl2 is not None and tse and (tl2 - tse) >= 0.08 and (my_l2 is None or tl2 >= my_l2 - 0.05)
                out_touched = (my_tg is not None and t_tg is not None and t_tg > my_tg and tl2 is not None and tse and (tl2 - tse) >= 0.04
                               and (my_l2 is None or tl2 >= my_l2 - 0.10))
                if snap_rise or out_touched:
                    bits = []
                    if tl2 is not None and tse: bits.append(f"{tl2*100:.0f}% snaps last two ({(tl2-tse)*100:+.0f} vs season)")
                    if t_tg is not None: bits.append(f"{int(t_tg)} {'touches' if pos == 'RB' else 'targets'} last game" + (f" to his {int(my_tg)}" if my_tg is not None else ""))
                    risers.append((tn, ", ".join(bits), (tl2 or 0) - (tse or 0)))
            # owner 10/22: a teammate gaining playing time is not this player losing it (Chism's snaps rose because Doubs and Hollins went on
            # IR; Douglas stayed at 54%). He has to be slipping himself: last-two share 5+ points under his season share.
            my_trend = (my_l2 - my_s["season"]) if (my_l2 is not None and my_s.get("season") is not None) else None
            if my_trend is not None and my_trend > -0.05: risers = []
            if risers and (my_l2 is not None and my_l2 < 0.60):   # only depth roles get passed; a 60%+ player is the room
                risers.sort(key=lambda x: -x[2]); tn, why, _ = risers[0]
                short = next((t for t in reversed(tn.split()) if t.rstrip(".").upper() not in ("JR", "SR", "II", "III", "IV")), tn)
                add("bad", f"Rising: {short}", f"Next man up: {tn} is taking this role - {why}. Depth legs lose to the riser more often than the season line suggests.")
        # --- role from the model ---
        role = P.get("role", "")
        if role and role not in ("STABLE", "MODEL STARTER"):
            k = "good" if "UP" in role else "bad" if ("DOWN" in role or "LIMITED" in role) else "info"
            if k == "bad" and lim_recent:
                add("info", role.title(), f"Model role signal: {role.title()} - but it comes from injury-limited games, not a demotion (see Healthy again / Playing hurt). The projection carries that dip.")
            elif k == "good" and fill_recent:
                add("info", role.title(), f"Model role signal: {role.title()} - built on fill-in games while a teammate was hurt; that teammate is back this week (see Fill-in fading).")
            else:
                add(k, role.title(), f"Model role signal: {role.title()} - the projection already reflects the changed role.")
        # --- matchup ---
        if pos in MAIN_STAT and opp:
            st, lab = MAIN_STAT[pos]; col = RANK_COL.get((pos, st)); r = self.drank(opp, col) if col else None; r3 = self.drank(opp, col, True) if col else None
            if r:
                tail = f" (last 3 weeks #{r3})" if r3 else ""
                if r <= 6 and (r3 is None or r3 <= 12): add("good", "Soft matchup", f"{opp} allows the #{r}-most {lab} to {pos}s this season{tail}." + self.otail(team, col, pos, lab))
                elif r >= 27 and (r3 is None or r3 >= 20): add("bad", "Tough matchup", f"{opp} ranks #{r} of 32 in {lab} allowed to {pos}s (1 = allows most) - a bottom-six matchup{tail}." + self.otail(team, col, pos, lab))
                elif r3 and abs(r3 - r) >= 14: add("info", "Matchup shifting", f"{opp} ranks #{r} vs {pos}s for the season but #{r3} over the last 3 weeks - the defence has changed recently." + self.otail(team, col, pos, lab))
            if pos == "RB":
                r2 = self.drank(opp, "RB Rec Yds");
                if r2 and r2 <= 5: add("good", "Soft vs RB targets", f"{opp} allows the #{r2}-most receiving yards to RBs.")
            if pos == "QB":
                r2 = self.drank(opp, "QB Rush Yds")
                if r2 and r2 <= 5: add("good", "Soft vs QB runs", f"{opp} allows the #{r2}-most rushing yards to QBs.")
        # --- weather ---
        if team and opp:
            w = self.WX.get(frozenset([team, opp]))
            if w and w["roof"] != "dome" and w["temp"] is not None:
                wind, gust, pch, pt, temp = w["wind"] or 0, w["gust"] or 0, w["pch"] or 0, (w["ptype"] or ""), w["temp"]
                if wind >= 15 or gust >= 28:
                    wt = f"wind {wind:.0f} mph" + (f", gusts {gust:.0f}" if gust >= 20 else "")
                    if pos in ("QB", "WR", "TE"): add("bad", "Wind", f"Kickoff-hour forecast {wt}: deep passing and kicking suffer most; expect shorter throws and more runs.")
                    else: add("good", "Wind = run game", f"Kickoff-hour forecast {wt}: teams lean on the run in wind - carries go up.")
                if pt.startswith("snow"): add("bad" if pos != "RB" else "watch", "Snow", f"Snow in the kickoff-hour forecast ({temp:.0f}°F): footing and ball security problems; scoring usually drops.")
                elif (pt.startswith("rain") and pch >= 50) or pch >= 70:
                    # owner 11/1 (ATL-TB, Mayfield passing yards): steady rain at kickoff is a real flag for the passing game, not just a note
                    rt = f"Rain {'likely' if pt.startswith('rain') else f'{pch:.0f}% chance'} at kickoff ({temp:.0f}°F)"
                    if pos in ("QB", "WR", "TE"): add("bad", "Rain", f"{rt}: a wet ball cuts deep passing and catch rates; expect shorter throws and more runs.")
                    else: add("good", "Rain = run game", f"{rt}: teams lean on the run in steady rain - carries go up.")
                elif pt.startswith("rain") or pch >= 50: add("watch", "Rain", f"Rain {'possible' if pt.startswith('rain') else f'{pch:.0f}% chance'} at kickoff ({temp:.0f}°F): wet ball favours the run and short passing; fumbles/drops up.")
                if temp <= 25: add("watch", "Cold", f"{temp:.0f}°F at kickoff: passing efficiency and kicking drop in deep cold.")
        # --- blowout rest risk (owner 11/1 after Diggs, SNF Week 8): nflverse 2019-24, veteran WRs (age 30+ or 8+ years) on 7+ point favorites
        # averaged 13% fewer receiving yards and 15% fewer PPR points than their trailing 4 (n=137); in games actually won by 17+ veterans lost
        # 10 points of snap share and 16% of targets. Too thin to adjust the projection (2025 check n=24) - a WATCH note only.
        if team and pos == "WR" and self.VET.get(_nn(name)) and (self.SPREAD.get(team) or 0) >= 7:
            add("watch", "Blowout rest risk", f"{team} is a {self.SPREAD[team]:g}-point favorite. Since 2019, veteran receivers on 7+ point favorites have averaged about 13% fewer receiving yards than their recent form, and in blowouts they lose snaps to the backups late. Lean unders / lower rungs on his yardage.")
        # --- market total ---
        if team and opp:
            tot = self.TOTAL.get(frozenset([team, opp]))
            if tot and tot >= 50: add("good", f"O/U {tot:g}", f"High market total ({tot:g}): more plays and scoring chances for everyone in the game.")
            elif tot and tot <= 39.5: add("bad", f"O/U {tot:g}", f"Low market total ({tot:g}): fewer plays and scoring chances.")
        # --- game script ---
        if team and (team in self.SCRIPTS or (opp and opp in self.SCRIPTS)):
            s_ = self.SCRIPTS.get(team); flip = False
            if not s_: s_ = self.SCRIPTS.get(opp); flip = True
            if s_ and s_[5] is not None:
                lead, close, shoot, trail = s_[5], s_[6], s_[7], s_[8]
                if flip: lead, trail = trail, lead
                if trail is not None and trail >= 50:
                    if pos in ("QB", "WR", "TE"): add("good", "Trail script", f"Model has {team} trailing by 10+ in {trail:.0f}% of endings: pass volume rises when behind.")
                    else: add("bad", "Trail script", f"Model has {team} trailing by 10+ in {trail:.0f}% of endings: carries dry up when behind (receiving work can rise).")
                if lead is not None and lead >= 50:
                    if pos == "RB": add("good", "Lead script", f"Model has {team} leading by 10+ in {lead:.0f}% of endings: clock-killing carries.")
                    elif pos in ("QB", "WR", "TE"): add("info", "Lead script", f"Model has {team} leading by 10+ in {lead:.0f}% of endings: pass attempts fall late when ahead.")
                if shoot is not None and shoot >= 40: add("good", "Shootout", f"Model gives a 51+ point shootout {shoot:.0f}%: everyone's volume rises.")
        # --- projection vs season average, explained ---
        if pos in MAIN_STAT and gs:
            st, lab = MAIN_STAT[pos]; sa = self.avg(gs, st); pj = P.get(st)
            if sa and pj is not None and sa >= 15:
                d = (pj - sa) / sa
                drivers_up = [f["tag"] for f in out if f["k"] == "good" and f["tag"] not in ("Steady floor",)]
                drivers_dn = [f["tag"] for f in out if f["k"] in ("bad", "watch") and f["tag"] not in ("Boom/bust",)]
                if d >= 0.25:
                    why = ("driven by: " + ", ".join(drivers_up[:3])) if drivers_up else "no single driver - matchup weight, script odds and the FanDuel-informed baseline add up"
                    add("info", f"Proj {d*100:+.0f}% vs avg", f"Projected {pj:.0f} {lab} vs a {sa:.0f} season average ({d*100:+.0f}%); {why}.")
                elif d <= -0.25:
                    why = ("driven by: " + ", ".join(drivers_dn[:3])) if drivers_dn else "no single driver - tougher matchup weight and script odds"
                    add("info", f"Proj {d*100:+.0f}% vs avg", f"Projected {pj:.0f} {lab} vs a {sa:.0f} season average ({d*100:+.0f}%); {why}.")
        # --- FanDuel main line hit-rate this season ---
        if pos in MAIN_STAT and gs:
            st, lab = MAIN_STAT[pos]; mk = {"Pass Yds": "Passing Yards", "Rush Yds": "Rushing Yards", "Rec Yds": "Receiving Yards"}[st]
            m = self.MAIN.get((name, mk))
            if m and len(gs) >= 3:
                ln = m[0]; v = [g[st] for g in gs if g.get(st) is not None]; k = sum(1 for x in v if x >= ln)
                if k / len(v) >= 0.7: add("good", f"FD {lab} {k}/{len(v)}", f"Cleared FanDuel's main {lab} line ({ln:g}) in {k} of {len(v)} games this season.")
                elif k / len(v) <= 0.4: add("bad", f"FD {lab} {k}/{len(v)}", f"Cleared FanDuel's main {lab} line ({ln:g}) in only {k} of {len(v)} games this season.")
        order = {"bad": 0, "watch": 1, "good": 2, "info": 3}
        out.sort(key=lambda f: order[f["k"]])
        self._cache[key] = out
        return out

    # ---------- leg flags ----------
    def leg(self, l):
        """Player flags plus the this-season hit rate for the exact line; the 'Cleared only' flag is what the parlay gate reads."""
        fl = list(self.player(l["player"], l.get("team"), None, l.get("opp")))
        # --- matchup for the market this leg is priced on (not just the position's headline stat) ---
        # Week 6 check (1,382 graded builder legs vs nflverse): legs against a bottom-six defense for THEIR stat hit 6 pts under
        # the model overall, QB rushing -18, receptions -17, passing -14; Daniels 30+ rush vs SF (#31 vs QB rush) was the costly case.
        # A 'bad' flag here keeps the leg out of Top Plays, Floor legs, clean best-parlay builds and promo picks.
        gs = self.games(l["player"]); pos = gs[-1]["pos"] if gs else None; opp = l.get("opp"); m = l["market"]; _tm = l.get("team") or (gs[-1]["team"] if gs else None)
        col = LEG_RANK_COL.get((pos, m)) if pos else None
        if col and opp:
            # the player-level matchup flags describe his headline stat; on a leg they are replaced by the matchup for THIS market
            # (McCaffrey receiving vs WAS is not 'tough' because WAS is #27 vs RB rushing)
            fl = [f for f in fl if f["tag"] not in ("Tough matchup", "Soft matchup", "Soft vs RB targets", "Soft vs QB runs", "Matchup shifting")]
            r = self.drank(opp, col); r3 = self.drank(opp, col, True)
            if r:
                lab = LEG_RANK_LABEL.get(col, col.lower()); tail = f" (last 3 weeks #{r3})" if r3 else ""
                if r >= 27 and (r3 is None or r3 >= 20): fl.insert(0, {"k": "bad", "tag": "Tough matchup", "txt": f"{opp} ranks #{r} of 32 in {lab} allowed to {pos}s (1 = allows most) - a bottom-six matchup for the stat this leg is priced on{tail}." + self.otail(_tm, col, pos, lab)})
                elif r <= 6 and (r3 is None or r3 <= 12): fl.append({"k": "good", "tag": "Soft matchup", "txt": f"{opp} allows the #{r}-most {lab} to {pos}s this season{tail}." + self.otail(_tm, col, pos, lab)})
                elif r3 and abs(r3 - r) >= 14: fl.append({"k": "info", "tag": "Matchup shifting", "txt": f"{opp} ranks #{r} in {lab} allowed to {pos}s for the season but #{r3} over the last 3 weeks." + self.otail(_tm, col, pos, lab)})
        # --- coverage (Mike Clay WR-CB cheatsheet): WR receiving legs only. Clay's matchup deltas are the receiver's season T/R and F/R
        # re-rated against the corners he is projected to see; +-8% targets AND +-0.15 fantasy points per route is a clear call either way.
        # First week in the pipeline (Week 7): a bad coverage read is a WATCH flag (shown everywhere, does not gate parlays) until a graded week
        # says it should; a good read is a 'good' flag.
        c = self.WRCB.get(_nn(l["player"])) if m in ("Receiving Yards", "Receptions", "Longest Reception", "Anytime TD", "Rush + Rec Yards") else None
        if c and c.get("cb"):
            dtr, dfr = c.get("d_tr"), c.get("d_fr")
            if dtr is not None and abs(dtr) > 1: dtr = dtr / 100.0   # sheet may hand back 12 or 0.12 for 12% - and -2 for -2% (10/22: the old `dtr > 1` left negatives as -200%, so a -2% / -0.16 receiver read as Tough coverage)
            parts = [f"Projected to see {c['cb']}" + (f" on about {c['exp']*100 if c['exp'] <= 1 else c['exp']:.0f}% of routes" if c.get('exp') is not None else "")]
            if c.get("cb_tr") is not None and c.get("cb_fr") is not None:
                tr = c["cb_tr"] * 100 if c["cb_tr"] <= 1 else c["cb_tr"]; parts.append(f"that corner allows {tr:.0f}% targets per route and {c['cb_fr']:.2f} fantasy points per route in coverage")
            if dtr is not None and dfr is not None: parts.append(f"Clay's matchup read vs his season rates: targets {dtr*100:+.0f}%, points per route {dfr:+.2f}")
            txt = "; ".join(parts) + "."
            _cbst = self.CTX_CB.get(_nn(c["cb"]))
            if _cbst and _cbst.get("status") in ("Out", "Doubtful", "IR"):
                fl.append({"k": "good", "tag": "Corner out", "txt": f"{c['cb']} is {_cbst['status']} this week ({_cbst.get('why') or 'injury'}), so Clay's read below assumed a corner who will not play; expect the backup / a softer look. " + txt})
            elif _cbst and _cbst.get("status") == "Questionable":
                fl.append({"k": "watch", "tag": "Corner questionable", "txt": f"{c['cb']} is Questionable ({_cbst.get('why') or 'injury'}); if he sits, the coverage read below changes. " + txt})
            elif dtr is not None and dfr is not None and dtr >= 0.08 and dfr >= 0.15: fl.append({"k": "good", "tag": "Coverage edge", "txt": txt})
            elif dtr is not None and dfr is not None and dtr <= -0.08 and dfr <= -0.15: fl.append({"k": "watch", "tag": "Tough coverage", "txt": txt})
            elif c.get("flag") == "DIFFICULT": fl.append({"k": "watch", "tag": "Coverage", "txt": txt + " Defense ranks tough for his alignment."})
            else: fl.append({"k": "info", "tag": "Coverage", "txt": txt})
        h = self.leg_hist(l)
        if h and h[1] >= 3:
            k, n = h; ln = l.get("line"); m = l["market"]
            what = "scored a TD" if m == "Anytime TD" else f"cleared {ln:g}+ {m.lower()}"
            if k / n <= 0.4: fl.insert(0, {"k": "bad", "tag": f"{k}/{n} this season", "txt": f"Has {what} in only {k} of {n} games this season.", "hit": (k, n)})
            elif k / n >= 0.8: fl.append({"k": "good", "tag": f"{k}/{n} this season", "txt": f"Has {what} in {k} of {n} games this season.", "hit": (k, n)})
            else: fl.append({"k": "info", "tag": f"{k}/{n} this season", "txt": f"Has {what} in {k} of {n} games this season.", "hit": (k, n)})
        return fl

def warn_text(fl): return "; ".join(f["txt"] for f in fl if f["k"] == "bad")
def note_text(fl): return "; ".join(f["txt"] for f in fl if f["k"] in ("watch", "info"))
def good_text(fl): return "; ".join(f["txt"] for f in fl if f["k"] == "good")
def is_clean(fl): return not any(f["k"] == "bad" for f in fl)
def hit_of(fl):
    for f in fl:
        if "hit" in f: return f["hit"]
    return None
