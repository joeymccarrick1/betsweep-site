"""Pricing for the new prop markets (owner 11/5): Passing TDs, Interceptions, Completions, Rush Attempts.
Settings from research/newmkt.py (walk-forward 2023-24 fit, 2025-26 test; every market calibrated, TDs / INTs / completions beat the plain
average on Brier): mean = player's average this season shrunk toward the league mean with k = 3 games x opponent factor ^ alpha;
TDs / INTs Poisson, completions / rush attempts normal with sd = c x sqrt(mean). Reads in/stats_player_week_2026.csv (games before WEEK).
"""
import csv, math, os, json
from collections import defaultdict
P = {"Passing TDs": ("passing_tds", "QB", "pois", 0.0, 1.0), "Interceptions": ("passing_interceptions", "QB", "pois", 0.0, 1.0),
     "Completions": ("completions", "QB", "norm", 0.25, 1.4), "Rush Attempts": ("carries", "RB", "norm", 0.5, 1.6)}
K = 3
def _f(x):
    try: return float(x)
    except Exception: return 0.0
class Pricer:
    def __init__(self, IN, WEEK):
        self.W = int(WEEK); self.rows = []
        fn = os.path.join(IN, "stats_player_week_2026.csv")
        if not os.path.exists(fn): return
        for r in csv.DictReader(open(fn)):
            if r.get("season_type") != "REG" or int(_f(r["week"])) >= self.W: continue
            self.rows.append(r)
        self.lg = {}; self.opp = {}; self.pl = defaultdict(list); self.team = {}; self.pos = {}
        for m, (col, pos, dist, a, c) in P.items():
            ys = [ _f(r[col]) for r in self.rows if r["position"] == pos and (pos != "QB" or _f(r["attempts"]) >= 15)]
            if pos == "RB":
                per = defaultdict(list)
                for r in self.rows:
                    if r["position"] == "RB": per[r["player_display_name"]].append(_f(r["carries"]))
                ys = [sum(v) / len(v) for v in per.values() if v and sum(v) / len(v) >= 8]
            self.lg[m] = sum(ys) / len(ys) if ys else None
            tw = defaultdict(float); tn = defaultdict(set)
            for r in self.rows:
                if r["position"] == pos and (pos != "QB" or _f(r["attempts"]) >= 15): tw[r["opponent_team"]] += _f(r[col]); tn[r["opponent_team"]].add(r["week"])
            per_g = {t: tw[t] / len(tn[t]) for t in tw if tn[t]}
            avg = sum(per_g.values()) / len(per_g) if per_g else None
            self.opp[m] = {t: (v / avg if avg else 1.0) for t, v in per_g.items()}
        for r in sorted(self.rows, key=lambda r: int(_f(r["week"]))):
            self.pl[r["player_display_name"]].append(r); self.team[r["player_display_name"]] = r["team"]; self.pos[r["player_display_name"]] = r["position"]
    def mean(self, pl, m, opp):
        col, pos, dist, a, c = P[m]; g = self.pl.get(pl) or []
        if pos == "QB": g = [r for r in g if _f(r["attempts"]) >= 15]
        if len(g) < 2 or self.lg.get(m) is None or self.pos.get(pl) != pos: return None
        ys = [_f(r[col]) for r in g]
        if pos == "RB" and sum(ys) / len(ys) < 8: return None
        shr = (sum(ys) + K * self.lg[m]) / (len(ys) + K)
        return max(0.05, shr * (self.opp[m].get(opp, 1.0) ** a)), len(ys), sum(ys) / len(ys)
    def prob(self, pl, m, ln, opp):
        """P(stat >= ln) for an X+ line; -> (p, mean, games, season avg) or None"""
        mu = self.mean(pl, m, opp)
        if not mu: return None
        mean, n, avg = mu; col, pos, dist, a, c = P[m]
        if dist == "pois": p = 1 - sum(math.exp(-mean) * mean ** i / math.factorial(i) for i in range(int(ln)))
        else: p = 1 - 0.5 * (1 + math.erf(((ln - 0.5) - mean) / (c * math.sqrt(mean)) / math.sqrt(2)))
        return min(0.97, max(0.03, p)), mean, n, avg
