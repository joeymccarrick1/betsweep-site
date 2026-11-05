"""confidence.py - how much to trust each game's projection, and what the market thinks will happen (owner 10/26).

Owner, after Week 7 (SF @ ATL, CIN @ BAL, TB @ CAR, KC @ SEA...): "say here's the stats / projections BUT there's a lot of flags on so
and so game, so look at this other game script." What the Week 6-7 audit found (27 games): the game projections are frozen team-level
season averages (0.65 x points per game + 0.35 x opponent points allowed, no home field, no injuries / QB changes); the closing line
beat them (margin MAE 9.1 vs 8.2, the model's side of the spread right 9 of 27); and the five games whose line moved 1+ point after
the model froze were the worst misses (19 pts on average). So each game card gets:

  * a confidence grade (HIGH / MEDIUM / LOW) from flags that say "the market knows something the model does not":
      market gap        model margin 3+ pts off FanDuel's spread (2 pts; 5+ = 3 pts), or total 4+ off (1 pt)
      line moved        FanDuel's spread moved 1+ pt since the first model call this week (2 pts) - news since our number
      QB situation      last game's starter is not the expected starter, the expected starter has <= 2 starts, or a QB on the
                        team is QUESTIONABLE this week (2 pts)
      newly out         players out this week who played in the team's last two games and carried 20%+ of its targets or 25%+
                        of its carries this season (1 pt; 2 pts at 35% / 40%)
      boom/bust QB      the QB's passing yards per game vs tough pass defenses (bottom 10) are < 75% of his vs soft ones (top 10),
                        and this week's opponent is a tough one (1 pt)
    grade: 0-1 HIGH, 2-3 MEDIUM, 4+ LOW. Context (short week, off a bye, division game) is shown but scores 0 - none of it beat the
    closing line in the 2022-26 backtest.
  * since 10/27 the game scripts themselves use FanDuel's spread + total when posted (sheet tab 'AUTO - Market Team Points';
    backtest gbt/results.md: market endings beat the formula out of sample). The card also shows our formula's read for comparison.
Display only: nothing here changes a projection. The flags are graded weekly (season page) before they are trusted.
"""
import json, os, csv, math, re
from collections import defaultdict

def _num(x):
    try: return float(str(x).replace(",", "").replace("%", ""))
    except Exception: return None
def _phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
SD, BLOW, SHOOT = 13.5, 9.5, 50.5

def endings(margin_a, total):
    """[A by 10+, close-low, shootout, B by 10+] in percent - same formula as 'V2 - Game Scripts'."""
    pa = 1 - _phi((BLOW - margin_a) / SD); pb = _phi((-BLOW - margin_a) / SD)
    ps = (1 - pa - pb) * (1 - _phi((SHOOT - total) / SD)); pc = 1 - pa - pb - ps
    return [round(x * 100, 1) for x in (pa, pc, ps, pb)]

class Conf:
    def __init__(self, IN, WEEK, fdgl=None, sched=None, ranks=None):
        self.IN, self.WEEK = IN, int(WEEK); self.fdgl = fdgl or {}; self.sched = sched or {}
        def vals(n):
            try: return json.load(open(os.path.join(IN, n)))["values"]
            except Exception: return []
        # our own team-score formula (0.65 x pts/game + 0.35 x opp allowed) - since 10/27 the game scripts use FanDuel's line when one is
        # posted ('AUTO - Market Team Points'), so the "market sees it differently" flag compares the line to OUR formula, not to the script
        self.formula = {}; self.src = {}
        for r in vals("teammkt.json")[1:]:
            if len(r) >= 10 and r[0] and _num(r[7]) is not None: self.formula[r[0]] = _num(r[7]); self.src[r[0]] = r[9]
        # first model call this week per game (calls archive) -> the spread when our number was set
        self.open_spread = {}
        cal = vals("calls.json")
        if cal:
            H = {c: i for i, c in enumerate(cal[0])}
            for r in cal[1:]:
                if len(r) <= H.get("FD spread (A)", 99) or str(r[0]).strip() != str(self.WEEK): continue
                k = frozenset([r[H["A"]], r[H["B"]]]); sp = _num(r[H["FD spread (A)"]])
                if k not in self.open_spread and sp is not None: self.open_spread[k] = (r[H["A"]], sp, str(r[H["Frozen at (CT)"]])[:16])
        # game log: QB starts, last-game starter, team target / carry shares, who played the last two games
        gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])} if gl else {}
        g = lambda r, c: _num(r[GH[c]]) if c in GH and GH[c] < len(r) else 0.0
        self.qb_games = defaultdict(list)       # qb -> [(week, opp, pass yds)]
        self.starts = defaultdict(int); team_wk_qb = {}
        tgt = defaultdict(float); car = defaultdict(float); ptgt = defaultdict(float); pcar = defaultdict(float); played = defaultdict(set); team_wks = defaultdict(set)
        for r in gl[1:]:
            w = _num(r[0]) if r else None
            if w is None or w >= self.WEEK or len(r) < 12: continue
            w = int(w); pl, tm, pos = r[1], r[2], r[3]
            team_wks[tm].add(w); played[(pl, tm)].add(w)
            pa = g(r, "Pass Att")
            if pos == "QB" and pa >= 10:
                self.qb_games[pl].append((w, r[4], g(r, "Pass Yds")))
                if (tm, w) not in team_wk_qb or pa > team_wk_qb[(tm, w)][1]: team_wk_qb[(tm, w)] = (pl, pa)
            tgt[tm] += g(r, "Targets"); car[tm] += g(r, "Rush Att") if pos != "QB" else 0
            ptgt[(pl, tm)] += g(r, "Targets"); pcar[(pl, tm)] += g(r, "Rush Att") if pos != "QB" else 0
        for (tm, w), (pl, _) in team_wk_qb.items(): self.starts[pl] += 1
        self.last_qb = {}
        for tm, wks in team_wks.items():
            lw = max(wks); x = team_wk_qb.get((tm, lw)); self.last_qb[tm] = x[0] if x else None
        self.last2 = {tm: sorted(wks)[-2:] for tm, wks in team_wks.items()}
        self.share = {k: (ptgt[k] / tgt[k[1]] if tgt[k[1]] else 0, pcar[k] / car[k[1]] if car[k[1]] else 0) for k in ptgt}
        self.played = played
        # expected starter: the sheet's QB role column (CURRENT STARTER), else the last game's starter
        self.exp_qb = {}
        pq = vals("proj_qb.json")
        if pq:
            QH = {c: i for i, c in enumerate(pq[0])}
            for r in pq[1:]:
                if not r or len(r) <= QH.get("QB Role", 99): continue
                if "CURRENT STARTER" in str(r[QH["QB Role"]]).upper() and r[1] not in self.exp_qb: self.exp_qb[r[1]] = r[0]
        # availability this week
        self.out = defaultdict(list); self.qb_q = defaultdict(list)
        for r in vals("avail.json")[1:]:
            if len(r) < 5 or str(r[0]).strip() != str(self.WEEK): continue
            if r[4] == "OUT": self.out[r[2]].append((r[1], r[3]))
            if r[4] == "QUESTIONABLE" and r[3] == "QB": self.qb_q[r[2]].append(r[1])
        # pass-defense ranks (1 = allows the most) for the boom/bust QB split
        self.prank = {}
        rk = [x for x in vals("ranks.json") if x]
        if rk:
            RH = {c: i for i, c in enumerate(rk[0])}
            for x in rk[1:33]:
                if "QB Pass Yds" in RH and len(x) > RH["QB Pass Yds"]: self.prank[x[0]] = _num(x[RH["QB Pass Yds"]])

    def market(self, a, b):
        """(FanDuel main spread for A, main total) - the lines priced closest to even; schedule closing line as fallback."""
        gk = frozenset([a, b]); sp = None; tot = None; best_s = best_t = 9e9
        for (side, mk, pt, g), (o, *_rest) in self.fdgl.items():
            if g != gk: continue
            if mk == "Spread" and side == a and abs(abs(o) - 110) < best_s: best_s = abs(abs(o) - 110); sp = pt
            if mk == "Total" and side == "OVER" and abs(abs(o) - 110) < best_t: best_t = abs(abs(o) - 110); tot = pt
        gi = self.sched.get(gk)
        if (sp is None or tot is None) and gi:
            sl = _num(gi.get("spread_line")); tl = _num(gi.get("total_line"))
            if sp is None and sl is not None: sp = -sl if gi["home_team"] == a else sl
            if tot is None: tot = tl
        return sp, tot

    def assess(self, a, b, pa, pb):
        """-> {"grade", "score", "flags": [(pts, kind, text)], "context": [text], "mkt": {...} or None}"""
        flags, ctx = [], []
        sp, tot = self.market(a, b); mkt = None
        fa, fb = self.formula.get(a, pa), self.formula.get(b, pb); mm = fa - fb; mt = fa + fb
        form = {"pa": fa, "pb": fb, "probs": endings(mm, mt), "used": self.src.get(a) == "FanDuel"}
        if sp is not None:
            m_mkt = -sp
            gap = abs(mm - m_mkt)
            if gap >= 3:
                fav_m = a if mm > 0 else b; fav_k = a if m_mkt > 0 else b
                say_m = f"{fav_m} by {abs(mm):.1f}" if abs(mm) >= 0.5 else "a pick'em"; say_k = f"{fav_k} by {abs(m_mkt):g}" if abs(m_mkt) >= 0.5 else "a pick'em"
                flags.append((3 if gap >= 5 else 2, "Our formula disagrees with the line", f"Our season-average formula has {say_m}; FanDuel has {say_k} ({gap:.1f}-pt gap) - something about this game is not in the averages (injuries, QB, form). When we have been 3+ points off the line (2019-26, 1,593 games), the line was closer: 9.7-pt average miss vs our 10.9."))
            if tot is not None and abs(mt - tot) >= 4:
                flags.append((1, "Total gap", f"Our formula's total {mt:.1f} vs FanDuel {tot:g}."))
            if tot is not None:
                ia = (tot + m_mkt) / 2; ib = tot - ia
                mkt = {"pa": ia, "pb": ib, "spread_a": sp, "total": tot, "probs": endings(m_mkt, tot)}
            op = self.open_spread.get(frozenset([a, b]))
            if op:
                o_a = op[1] if op[0] == a else -op[1]; mv = sp - o_a   # spread for A: negative = A favoured; mv < 0 = moved toward A
                if abs(mv) >= 1:
                    tow = a if mv < 0 else b
                    flags.append((2, "News since our number", f"FanDuel's line moved {abs(mv):g} pts toward {tow} since our projection was set ({op[2]}). Our game numbers do not react to injury news yet - the market does."))
        for t in (a, b):
            exp = self.exp_qb.get(t); last = self.last_qb.get(t)
            if exp and last and exp != last:
                flags.append((2, f"{t} QB change", f"{exp} expected to start; {last} started their last game."))
            elif exp and self.starts.get(exp, 0) <= 2:
                flags.append((2, f"{t} QB inexperience", f"{exp} has {self.starts.get(exp, 0)} start{'s' if self.starts.get(exp, 0) != 1 else ''} this season - small sample."))
            if self.qb_q.get(t): flags.append((2, f"{t} QB questionable", ", ".join(self.qb_q[t]) + " is questionable."))
            # newly out: played in either of the team's last two games
            l2 = set(self.last2.get(t, [])); ts = cs = 0.0; names = []
            for pl, pos in self.out.get(t, []):
                if pos == "QB" or not (self.played.get((pl, t), set()) & l2): continue
                s_t, s_c = self.share.get((pl, t), (0, 0))
                if s_t >= 0.05 or s_c >= 0.10: names.append(f"{pl} ({s_t*100:.0f}% of targets" + (f", {s_c*100:.0f}% of carries" if s_c >= 0.10 else "") + ")")
                ts += s_t; cs += s_c
            if ts >= 0.20 or cs >= 0.25:
                flags.append((2 if (ts >= 0.35 or cs >= 0.40) else 1, f"{t} missing pieces", "Newly out: " + "; ".join(names) + ". Our team score is built from season averages that include them."))
            # boom/bust QB vs tough pass defenses
            q = exp or last; opp = b if t == a else a; orank = self.prank.get(opp)
            if q and orank and orank >= 23:
                soft = [y for w, o, y in self.qb_games.get(q, []) if (self.prank.get(o) or 99) <= 10]
                hard = [y for w, o, y in self.qb_games.get(q, []) if (self.prank.get(o) or 0) >= 23]
                if len(soft) >= 2 and len(hard) >= 2:
                    s_avg, h_avg = sum(soft) / len(soft), sum(hard) / len(hard)
                    if h_avg < 0.75 * s_avg:
                        flags.append((1, f"{q} vs good defenses", f"{h_avg:.0f} pass yds/g vs tough pass defenses, {s_avg:.0f} vs soft ones - {opp} is #{orank:.0f} of 32 (tough)."))
        gi = self.sched.get(frozenset([a, b]))
        if gi:
            for side in ("away", "home"):
                rest = _num(gi.get(f"{side}_rest")); tm = gi[f"{side}_team"]
                if rest is not None and rest <= 5: ctx.append(f"{tm} on a short week ({rest:.0f} days)")
                if rest is not None and rest >= 13: ctx.append(f"{tm} off a bye")
            if str(gi.get("div_game")) == "1": ctx.append("division game")
            ctx.append(f"{gi['away_team']} on the road")
        score = sum(f[0] for f in flags)
        grade = "LOW" if score >= 4 else ("MEDIUM" if score >= 2 else "HIGH")
        return {"grade": grade, "score": score, "flags": flags, "context": ctx, "mkt": mkt, "form": form}
