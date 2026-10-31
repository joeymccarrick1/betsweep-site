#!/usr/bin/env python3
"""injweeks.py - which games were shaped by an injury, so a hobbled starter is not read as "losing his role" and the backup who
filled in is not read as "taking it".

Owner, 2026-10-22: TreVeyon Henderson played Weeks 5-6 on a high-ankle sprain (Questionable / limited in Week 6, 16% and 24% of
snaps vs 46% before). The snap trend called it SNAPS DOWN (bad flag AND the sheet's snap-decline factor cut his projection) and
Corey Kiner's fill-in carries read as Role Up / Hot L3. Both were the injury, not the depth chart: "when players get taken out of the
game and backups get more play time, that doesn't mean a more important player is losing snaps. Need to notice if there was an injury."

Sources (nflverse, downloaded by build_snaps.py into in/): snap_counts_<season>.csv (offense_pct per player-week) and
injuries_<season>.csv (weekly report: report_status, practice_status, primary injury).

A player's game in week w is INJURY-LIMITED when his snap share fell well below his own norm (< 75% of the median of his other
games, and that median is a real role, >= 25%) AND an injury explains it: he was on that week's report (Questionable / Doubtful, or
Limited / DNP in practice with an injury, not rest), or on the next week's report, or he missed the team's next game (left hurt).
A week the player sat out while his team played, with an injury on that week's report, is ABSENT.
For a same-position teammate, a week in which someone in his room was injury-limited or absent is a FILL-IN week - but only matters
when that teammate is back this week (not Out / Doubtful on this week's report): then the fill-in bump is about to disappear.

    W = load(IN, WEEK)
    W.limited(name, team) -> {week: reason}      the player's own injury-limited weeks
    W.fill(name, team, pos) -> {week: teammate}   weeks his volume was inflated by a teammate's injury, teammate back this week
    W.status(name) -> (report_status, practice_status, injury) on this week's report, or None
    W.healthy_now(name) -> True when he is not on this week's report, or practising in full with no game status
"""
import csv, os, re
from statistics import median

def norm(s):
    s = re.sub(r"\.", "", str(s)).strip(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s, flags=re.I); return re.sub(r"\s+", " ", s).lower()

TEAM = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
def _t(x): return TEAM.get(x, x)

class Weeks:
    def __init__(self, IN, WEEK, season=2026):
        self.WEEK = int(WEEK); self.snap = {}; self.team_weeks = {}; self.rep = {}; self.pos = {}; self.disp = {}
        p = os.path.join(IN, f"snap_counts_{season}.csv")
        if os.path.exists(p):
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("game_type") != "REG" or r.get("position") not in ("QB", "RB", "WR", "TE"): continue
                    try: wk = int(r["week"]); pct = float(r["offense_pct"])
                    except Exception: continue
                    if wk >= self.WEEK: continue
                    k = (norm(r["player"]), _t(r["team"])); self.snap.setdefault(k, {})[wk] = pct; self.pos[k] = r["position"]; self.disp[k] = r["player"]
                    self.team_weeks.setdefault(_t(r["team"]), set()).add(wk)
        p = os.path.join(IN, f"injuries_{season}.csv")
        if os.path.exists(p):
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("game_type") not in ("REG", None, ""): continue
                    try: wk = int(r["week"])
                    except Exception: continue
                    inj = (r.get("report_primary_injury") or r.get("practice_primary_injury") or "").strip()
                    prac = (r.get("practice_status") or "").strip(); stat = (r.get("report_status") or "").strip()
                    if inj.lower().startswith("not injury") or (not inj and not stat): continue
                    self.rep[(norm(r["full_name"]), wk)] = (stat, prac, inj, _t(r["team"]))
        # this week's availability tab (OUT / IR / released) - an IR player is not on the weekly injury report, so the report alone
        # cannot say he is back
        self.out_now = set(); self.cleared = set()
        try:
            import json as _j
            av = _j.load(open(os.path.join(IN, "avail.json")))["values"]
            for r in av[1:]:
                if len(r) > 4 and str(r[0]) == str(self.WEEK) and r[4].strip().upper() == "OUT": self.out_now.add(norm(r[1]))
                # owner 10/30 (Pickens: "He wasn't injured. He just lost blocking snaps to Flournoy"): "not injury-limited" in this week's
                # reason column (J) means his low-snap games were NOT the injury - no first-game-back haircut or flag, and teammates did not
                # "fill in" for him. His game status (Questionable etc.) is untouched.
                if len(r) > 9 and str(r[0]) == str(self.WEEK) and re.search(r"not injury[- ]limited", str(r[9]), re.I): self.cleared.add(norm(r[1]))
        except Exception: pass
        self._lim = {}; self._abs = {}
        for k, wk_pct in self.snap.items():
            name, team = k
            if name in self.cleared: continue
            if len(wk_pct) < 3: continue
            lim = {}
            for w, pct in wk_pct.items():
                others = [v for ww, v in wk_pct.items() if ww != w]
                med = median(others) if len(others) >= 2 else None
                if med is None or med < 0.25 or pct >= 0.75 * med: continue
                why = self._why(name, team, w)
                if why: lim[w] = f"{why} - {pct*100:.0f}% of snaps vs {med*100:.0f}% normally"
            if lim: self._lim[k] = lim
            # absent: team played, he did not, and an injury was on that week's report
            ab = {}
            for w in sorted(self.team_weeks.get(team, ())):
                if w in wk_pct or w < min(wk_pct): continue
                r = self.rep.get((name, w))
                if r: ab[w] = f"out ({r[2] or 'injury'})"
            if ab: self._abs[k] = ab

    def _why(self, name, team, w):
        def hurt(r): return r and (r[0] in ("Questionable", "Doubtful", "Out") or r[1].startswith(("Limited", "Did Not")))
        r = self.rep.get((name, w))
        if hurt(r): return f"played hurt ({r[2] or 'injury'}, {r[0] or r[1].replace(' Participation in Practice', '').replace(' In Practice', '')} that week)"
        r2 = self.rep.get((name, w + 1))
        if hurt(r2) or (r2 and r2[2]): return f"hurt in that game ({r2[2] or 'injury'} on the next week's report)"
        tw = self.team_weeks.get(team, set()); nxt = min([x for x in tw if x > w], default=None)
        if nxt is not None and nxt < self.WEEK and nxt not in self.snap.get((name, team), {}): return "left that game and missed the next one"
        return None

    def limited(self, name, team):
        return dict(self._lim.get((norm(name), _t(team or "")), {}))

    def status(self, name):
        return self.rep.get((norm(name), self.WEEK))

    def healthy_now(self, name):
        r = self.status(name)
        return r is None or (r[0] in ("", None) and r[1].startswith("Full"))

    def back_now(self, name, team=None):
        """On the field this week - needs evidence: on this week's report as anything but Out / Doubtful, or (not on the report) he
        played his team's most recent game. Out on the availability tab (IR, released, suspended) is never back."""
        n = norm(name)
        if n in self.out_now: return False
        r = self.status(name)
        if r: return r[0] not in ("Out", "Doubtful")
        team = _t(team or ""); k = (n, team)
        tw = sorted(self.team_weeks.get(team, ()))
        return bool(tw) and tw[-1] in self.snap.get(k, {})

    def fill(self, name, team, pos):
        """Weeks this player's volume rose because a same-position teammate was injury-limited or absent and that teammate is back now."""
        team = _t(team or ""); me = (norm(name), team); cand = {}
        for k, p in self.pos.items():
            if k == me or k[1] != team or p != pos: continue
            if not self.back_now(self.disp.get(k, k[0]), k[1]): continue
            for w, why in list(self._lim.get(k, {}).items()) + list(self._abs.get(k, {}).items()):
                cand.setdefault(w, (self.disp.get(k, k[0].title()), why))
        # only weeks where HIS share actually rose (8+ points over his own share in the other games) - a starter who kept his usual role
        # while a backup was hurt is not "filling in"
        mine = self.snap.get(me, {}); out = {}
        base = [v for w, v in mine.items() if w not in cand]
        ref = median(base) if len(base) >= 2 else None
        for w, x in cand.items():
            if w in mine and ref is not None and mine[w] >= ref + 0.08: out[w] = x
        return out

def load(IN, WEEK, season=2026):
    try: return Weeks(IN, WEEK, season)
    except Exception as e:
        print("note: injury-week detection unavailable:", e); return None
