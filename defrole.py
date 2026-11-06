"""Defense vs role (owner 11/5): how often each defense let the opposing QB1 / RB1 / WR1 / WR2 / TE1 beat his own average (season, every
game before this week), plus how often he cleared FanDuel's main line (frozen ladders, weeks with snapshots). research/def_role.py is the
study: leave-one-week-out on Weeks 6-8 main lines, adding the defense's shrunk over-rate to the model's own % helped Weeks 6-7 and hurt
Week 8 (best weight 0.25-0.75 logit per unit of rate gap); against FanDuel's price it added ~nothing. So the weight is SMALL (B = 0.25,
shrinkage K = 4 games toward the league rate) - it nudges a leg 0-2 pts and is shown to the user as context, not a driver.
Usage: import defrole; D = defrole.load(IN, WEEK); p2, note, info = D.adjust(player, team, opp, market, p, under=False)
"""
import csv, json, math, os
from collections import defaultdict
B, K = 0.25, 4
MK = {"WR1": ("Receiving Yards", "Receptions"), "WR2": ("Receiving Yards", "Receptions"), "TE1": ("Receiving Yards", "Receptions"), "RB1": ("Rushing Yards",), "QB1": ("Passing Yards",)}
COL = {"Receiving Yards": "receiving_yards", "Receptions": "receptions", "Rushing Yards": "rushing_yards", "Passing Yards": "passing_yards"}
ROLE_TXT = {"WR1": "WR1s", "WR2": "WR2s", "TE1": "TE1s", "RB1": "RB1s", "QB1": "QBs"}
def _f(x):
    try: return float(x)
    except Exception: return 0.0
class _D:
    def __init__(self, IN, WEEK):
        self.WEEK = int(WEEK); rows = []
        fn = os.path.join(IN, "stats_player_week_2026.csv")
        if os.path.exists(fn):
            for r in csv.DictReader(open(fn)):
                if r.get("season_type") != "REG": continue
                w = int(_f(r["week"]))
                if w >= self.WEEK: continue
                rows.append({"pl": r["player_display_name"], "pos": r["position"], "tm": r["team"], "opp": r["opponent_team"], "w": w,
                             "att": _f(r["attempts"]), "car": _f(r["carries"]), "tg": _f(r["targets"]), **{c: _f(r[c]) for c in COL.values()}})
        self.by_tw = defaultdict(list); self.by_pl = defaultdict(list)
        for r in rows: self.by_tw[(r["tm"], r["w"])].append(r); self.by_pl[r["pl"]].append(r)
        self.ev = defaultdict(list)   # (def, role, market) -> [(week, player, actual, avg, over)]
        for (tm, w), g in self.by_tw.items():
            rl = self.roles(tm, w)
            if not rl: continue
            opp = g[0]["opp"]
            for role, pl in rl.items():
                me = [x for x in g if x["pl"] == pl]
                hist = [x for x in self.by_pl[pl] if x["w"] < w]
                if not me or len(hist) < 2: continue
                for m in MK[role]:
                    c = COL[m]; avg = sum(x[c] for x in hist) / len(hist); act = me[0][c]
                    if act != avg: self.ev[(opp, role, m)].append((w, pl, act, round(avg, 1), int(act > avg)))
        self.lg = {}
        for role, ms in MK.items():
            for m in ms:
                xs = [e[4] for (d, r_, m_), es in self.ev.items() if r_ == role and m_ == m for e in es]
                if xs: self.lg[(role, m)] = sum(xs) / len(xs)
        self.cur = {}   # player -> (team, role) for THIS week (games before it)
        for tm in {t for (t, w) in self.by_tw}:
            for role, pl in self.roles(tm, self.WEEK).items(): self.cur[pl] = (tm, role)
        # FanDuel main-line record (frozen ladders) per (def, role, market)
        self.fd = defaultdict(lambda: [0, 0])
        try:
            v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}; best = {}
            imp = lambda o: 100 / (o + 100) if o > 0 else -o / (-o + 100)
            for r in v[1:]:
                r = r + [""] * (len(v[0]) - len(r))
                if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
                o = _f(r[H["FanDuel odds"]]); w = int(_f(r[0]))
                if not (-170 <= o <= 150) or (0 <= o < 100) or w >= self.WEEK: continue
                k = (w, r[H["Player"]], r[H["Market"]]); d = abs(imp(o) - 0.5238)
                if k not in best or d < best[k][0]: best[k] = (d, r[H["Opp"]], r[H["Result"]] == "HIT", r[H["Team"]])
            for (w, pl, m), (d, opp, hit, tm) in best.items():
                role = {v_: k_ for k_, v_ in self.roles(tm, w).items()}.get(pl)
                if role and m in MK[role]: self.fd[(opp, role, m)][0] += int(hit); self.fd[(opp, role, m)][1] += 1
        except Exception: pass
    def roles(self, tm, w):
        tot = defaultdict(lambda: defaultdict(float)); pos = {}; wks = set()
        for (t, ww), g in self.by_tw.items():
            if t != tm or ww >= w: continue
            wks.add(ww)
            for x in g:
                pos[x["pl"]] = x["pos"]; tot[x["pl"]]["gp"] += 1
                for k in ("att", "car", "tg"): tot[x["pl"]][k] += x[k]
        if len(wks) < 2: return {}
        out = {}
        # per game played (a star who missed games keeps his role); 2+ games, or every game if the team has fewer
        mg = min(2, len(wks))
        top = lambda p_, k: sorted([pl for pl in tot if pos[pl] == p_ and tot[pl][k] > 0 and tot[pl]["gp"] >= mg], key=lambda pl: -tot[pl][k] / tot[pl]["gp"])
        q = top("QB", "att"); r = top("RB", "car"); wr = top("WR", "tg"); te = top("TE", "tg")
        if q: out["QB1"] = q[0]
        if r: out["RB1"] = r[0]
        if wr: out["WR1"] = wr[0]
        if len(wr) > 1: out["WR2"] = wr[1]
        if te: out["TE1"] = te[0]
        return out
    def rate(self, opp, role, m):
        es = self.ev.get((opp, role, m), []); lg = self.lg.get((role, m))
        if lg is None: return None
        n = len(es); o = sum(e[4] for e in es)
        return {"n": n, "over": o, "lg": lg, "shr": (o + K * lg) / (n + K), "fd": list(self.fd.get((opp, role, m), [0, 0]))}
    def adjust(self, pl, tm, opp, m, p, under=False):
        """-> (adjusted p, short note or '', info dict or None). Only the role player of his team this week, only the role's markets."""
        cr = self.cur.get(pl)
        if not cr or cr[0] != tm or p is None: return p, "", None
        role = cr[1]
        if m not in MK[role]: return p, "", None
        r = self.rate(opp, role, m)
        if not r or r["n"] < 2: return p, "", None
        gap = (r["shr"] - r["lg"]) * (-1 if under else 1)
        q = min(0.999, max(0.001, p)); z = math.log(q / (1 - q)) + B * gap; p2 = 1 / (1 + math.exp(-z))
        fdt = f"; vs FanDuel line {r['fd'][0]}/{r['fd'][1]}" if r["fd"][1] else ""
        note = f"{opp} vs {ROLE_TXT[role]} ({m.lower()}): {r['over']}/{r['n']} beat their average ({r['over']/r['n']*100:.0f}%, league {r['lg']*100:.0f}%){fdt}"
        return p2, note, {"role": role, **r}
def load(IN, WEEK): return _D(IN, WEEK)
