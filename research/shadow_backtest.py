"""shadow_backtest.py - the paper recipes of shadow_slips.py run on past weeks' pre-kickoff boards (owner 11/10 deep dive).

  python3 research/shadow_backtest.py WEEK=PATH@BUILT_ISO [...]     PATH = the builder data the site published before kickoff
                                                                    (see research/risk_grade.py for where each week's file is)
For every game day still ahead of the build time it builds each recipe's three legs from that board and grades them from
in/gamelog.json. Small samples: a recipe makes one slip per game day, so four weeks are about eight slips each. Read-only.
"""
import datetime, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(HERE); sys.path.insert(0, GP)
import shadow_slips as SH  # noqa: E402

def load_bd(path):
    s = open(path, encoding="utf-8").read(); m = re.search(r"window\.__BS\s*=\s*", s)
    return json.JSONDecoder().raw_decode(s, m.end())[0]

if __name__ == "__main__":
    idx, weeks = SH.gamelog_index(os.path.join(GP, "in")); tot = {}
    for a in sys.argv[1:]:
        wk, rest = a.split("=", 1); path, iso = rest.rsplit("@", 1)
        now_ms = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
        bd = load_bd(path); days = {}
        for g in bd["games"]:
            if g.get("ko") and g["ko"] > now_ms: days.setdefault(SH.day_of(g["ko"]), set()).add(g["gid"])
        for d, gids in sorted(days.items()):
            for name, legs in SH.recipes_for(bd, gids).items():
                if not legs: continue
                rs = [SH.grade_leg({"pl": l["pl"], "m": l["m"], "ln": l["ln"], "week": wk}, idx, weeks) for l in legs]
                live = [(l, r) for l, r in zip(legs, rs) if r in ("HIT", "MISS")]
                if not live or any(r is None for r in rs): continue
                dd = 1.0
                for l, _ in live: dd *= SH.dec(l["o"])
                win = all(r == "HIT" for _, r in live); t = tot.setdefault(name, {"n": 0, "w": 0, "u": 0.0, "legs": 0, "hit": 0})
                t["n"] += 1; t["w"] += win; t["u"] += (dd - 1) if win else -1; t["legs"] += len(live); t["hit"] += sum(1 for _, r in live if r == "HIT")
                print(f"wk {wk} {d} {name:10} {'WON ' if win else 'lost'} {sum(1 for _, r in live if r == 'HIT')}/{len(live)}  +{round((dd - 1) * 100)}  " + " | ".join(f"{l['pl']} {l['m']} {l['ln']:g} ({l['o']}) {r}" for l, r in zip(legs, rs)))
    print()
    for name, t in tot.items():
        print(f"{name:10} slips {t['w']}-{t['n'] - t['w']}  units {t['u']:+.2f}  legs {t['hit']}/{t['legs']} ({t['hit'] / max(1, t['legs']) * 100:.0f}%)")
