"""runlean.py - pregame "run-lean" read per team (owner 10/26 after DAL-PHI: Dallas ran 38 times with the lead, Javonte Williams 0 catches).
Model runlean_v1.json (scratchpad runlean2/fit.py): team rush rate predicted from this season's player game log (prior weeks only) + the
game's spread and total; walk-forward fit 2019-23, tested 2024-26 (rush-rate R^2 0.10 vs 0.05 for the season-to-date rate). lean = prediction
minus the team's calibrated norm. Flag at lean >= +0.02 (~top 23% of team-games): in the 2024-26 test, flagged teams' RB1 cleared his
carries line 54.9% (all games 48.5%) and his receptions line 35.1% (39.7%) - suggestive (0.7-1.9 SE), so this is display + a pricing hint only."""
import json, os
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "runlean_v1.json")))
C, K = M["league_constants"], M["shrinkage_k"]
def _n(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return 0.0

class RunLean:
    def __init__(self, gamelog_rows, week):
        H = {c: i for i, c in enumerate(gamelog_rows[0])} if gamelog_rows else {}
        self.ok = all(c in H for c in ("Week", "Team", "Pos", "Opponent", "Pass Att", "Pass Yds", "Rush Att", "Rush Yds"))
        T = defaultdict(lambda: defaultdict(float)); A = defaultdict(lambda: defaultdict(float)); wk = defaultdict(set); owk = defaultdict(set)
        if self.ok:
            for r in gamelog_rows[1:]:
                if len(r) <= max(H.values()): r = r + [""] * (max(H.values()) + 1 - len(r))
                w = _n(r[H["Week"]])
                if not w or w >= week: continue
                tm, opp = r[H["Team"]], r[H["Opponent"]]; ra, pa = _n(r[H["Rush Att"]]), _n(r[H["Pass Att"]])
                T[tm]["ra"] += ra; T[tm]["pa"] += pa; T[tm]["ry"] += _n(r[H["Rush Yds"]]); wk[tm].add(w)
                if r[H["Pos"]] == "RB": T[tm]["rbca"] += ra
                A[opp]["ra"] += ra; A[opp]["ry"] += _n(r[H["Rush Yds"]]); A[opp]["py"] += _n(r[H["Pass Yds"]]); owk[opp].add(w)
        self.T, self.A, self.wk, self.owk = T, A, wk, owk

    def feats(self, tm, opp, spread_tm, total):
        t, a = self.T[tm], self.A[opp]; g = len(self.wk[tm]); og = len(self.owk[opp])
        return {"base_rr": (t["ra"] + K["rr"] * C["rr"]) / (t["ra"] + t["pa"] + K["rr"]),
                "base_rb_car": (t["rbca"] + K["rb_car"] * C["rb_car_pg"]) / (g + K["rb_car"]),
                "own_ypc": (t["ry"] + K["ypc"] * C["ypc"]) / (t["ra"] + K["ypc"]),
                "opp_ypc_allowed": (a["ry"] + K["ypc"] * C["ypc"]) / (a["ra"] + K["ypc"]),
                "opp_pass_yds_allowed_pg": (a["py"] + K["pya"] * C["pass_yds_pg"]) / (og + K["pya"]),
                "imp_margin": -spread_tm, "total_line": total}

    def read(self, tm, opp, spread_tm, total):
        """-> {"pred", "norm", "lean", "flag", "rb_car", "rb_car_norm"} or None (no line / no game log)."""
        if not self.ok or spread_tm is None or total is None: return None
        f = self.feats(tm, opp, spread_tm, total); rm, cm = M["rush_rate_model"], M["rb_carries_model"]
        pred = rm["intercept"] + sum(rm[k] * f[k] for k in rm if k != "intercept")
        car = cm["intercept"] + sum(cm[k] * f[k] for k in cm if k != "intercept")
        norm = M["team_norm"]["a"] + M["team_norm"]["b"] * f["base_rr"]; lean = pred - norm
        return {"pred": pred, "norm": norm, "lean": lean, "flag": "RUN" if lean >= M["lean"]["flag_threshold"] else ("PASS" if lean <= -M["lean"]["flag_threshold"] else ""),
                "rb_car": car, "rb_car_norm": f["base_rb_car"]}
