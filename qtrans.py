"""Questionable translator (owner 11/6). research/q_translator.py (nflverse 2024-25, skill players who normally play 30%+ of snaps):
  Questionable after a FULL final practice: played 80%; LIMITED: 64%; DID NOT PRACTICE: 54%; no practice listed: 57%. Doubtful: 0 of 61.
  When a Questionable player plays: ~89% of his usual snaps on average, and 1 in 4 is held under 75% of usual.
FanDuel voids a player prop when the player does not play, so a prop is priced on the snaps he gets IF he plays (the snap haircut below);
fantasy and the site's chips show the chance he plays. Reads in/injuries_2026.csv (this week's official report, latest practice day).
"""
import csv, os, re
PLAY = {"Full": 0.80, "Limited": 0.64, "DNP": 0.54, "none": 0.57}
SNAP = {"Full": 0.88, "Limited": 0.90, "DNP": 0.90, "none": 0.85}
LOW = {"Full": 0.29, "Limited": 0.24, "DNP": 0.29, "none": 0.35}
WORD = {"Full": "full practice", "Limited": "limited in practice", "DNP": "did not practice", "none": "no practice listed"}
def norm(n): return re.sub(r"[^a-z ]", "", re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(n).strip().lower())).strip()
def prac(s):
    s = str(s or ""); return "DNP" if "Did Not" in s else "Limited" if "Limited" in s else "Full" if "Full" in s else "none"
def info(status, practice):
    st = str(status or "").strip().title()
    if st not in ("Questionable", "Doubtful"): return None
    ps = prac(practice)
    if st == "Doubtful": return {"st": "D", "ps": ps, "play": 0.02, "snap": None, "low": None, "txt": f"Doubtful ({WORD[ps]}): 0 of 61 doubtful starters played in 2024-25"}
    return {"st": "Q", "ps": ps, "play": PLAY[ps], "snap": SNAP[ps], "low": LOW[ps],
            "txt": f"Questionable, {WORD[ps]}: plays ~{PLAY[ps]*100:.0f}% of the time; if he plays, ~{SNAP[ps]*100:.0f}% of his usual snaps (1 in {round(1/LOW[ps])} held under 75%)"}
def load(IN, WEEK):
    """-> {normalized name: info} for this week's Questionable / Doubtful QB / RB / WR / TE on the official report"""
    out = {}; fn = os.path.join(IN, "injuries_2026.csv")
    if not os.path.exists(fn): return out
    rows = [r for r in csv.DictReader(open(fn)) if str(r.get("week")) == str(WEEK) and r.get("position") in ("QB", "RB", "WR", "TE")]
    for r in rows:
        x = info(r.get("report_status"), r.get("practice_status"))
        if x: x.update({"pl": r.get("full_name"), "tm": r.get("team"), "inj": r.get("report_primary_injury") or ""}); out[norm(r.get("full_name"))] = x
    return out
