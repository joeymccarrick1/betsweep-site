#!/usr/bin/env python3
"""The other soccer leagues' pages - /bundesliga/, /laliga/, /seriea/, /mls/ (previews) - drawn by the Premier League page's own code.

Owner 11/23 1:10 AM: "get to building Bundesliga, La Liga, Serie A, and MLS. We'd have NFL, College Football, NBA and Soccer (with these
different leagues)." Each league's board (sports/soccer/publish.py, in the feeds-sports job) is in the Premier League board's format, so
build_epl.page() draws it: same cards, same player rows, the soccer background. What differs is said on the page: no expected goals
for these leagues (a shot-based stand-in is used), and no injury list yet.

A league's page is written only when its board is in reach, fresh and has a match still to come - the Premier League page's own rule.
Soccer is one sport in the switch at the top; the leagues that have a page in this build make a second row.

    python3 build_soccer.py <clone>                                             (the hourly job: every league)
    python3 build_soccer.py --league laliga --board FILE [--record FILE] [--with nba,epl,cfb]     (local work)
"""
import json
import os
import sys

import build_epl as K
import build_nba as N
import sport_nav

OUT = N.OUT
KEYS = tuple(k for k, _, _, _ in sport_nav.SOCCER if k != "epl")


def outs(key):
    return (os.path.join(OUT, f"{key}-boards.html"), os.path.join(OUT, f"{key}_board.json"), os.path.join(OUT, f"{key}_sig.json"), os.path.join(OUT, f"{key}_record.json"))


def write(key, B, R, have, any_age=False):
    cfg = sport_nav.LEAGUE[key]; fs = outs(key)
    if not isinstance(R, dict) or R.get("sport") != cfg["feed"] or not isinstance(R.get("total"), dict):
        R = None
    K.unique_keys(B)
    ok, why = K.usable(B, any_age=any_age, sport=cfg["feed"])
    if not ok:
        for f in fs:
            if os.path.exists(f): os.remove(f)
        print(f"{key}: no page written - {why}")
        return False
    os.makedirs(OUT, exist_ok=True)
    open(fs[0], "w", encoding="utf-8").write(K.page(B, bool(have.get("nba")), R, have, cfg))
    json.dump(B, open(fs[1], "w"), separators=(",", ":"))
    json.dump({"built": B.get("built"), "sig": K.signature(B, R) + "|nav:" + ",".join(sorted(have))}, open(fs[2], "w"))
    if R: json.dump(R, open(fs[3], "w"), separators=(",", ":"))
    elif os.path.exists(fs[3]): os.remove(fs[3])
    T = (R or {}).get("total") or {}
    print(f"{key} boards: {len(B['matches'])} matches, {len(B['players'])} player rows; board built {N.fmt_ct(B.get('built'))}; "
          + (f"record: {T.get('matches', 0)} matches graded, {R.get('waiting', 0)} waiting; " if R else "no grading record in reach; ") + f"{os.path.getsize(fs[0]) // 1024} KB -> {fs[0]}")
    return True


def main():
    a = sys.argv[1:]
    if "--board" in a:
        key = a[a.index("--league") + 1]
        R = None
        if "--record" in a:
            try: R = json.load(open(a[a.index("--record") + 1], encoding="utf-8"))
            except Exception: R = None
        have = sport_nav.local(a, OUT); have[key] = True
        write(key, N.load(path=a[a.index("--board") + 1]), R, have, any_age=True)
        return
    clone = a[0] if a else None
    have = sport_nav.available(clone)                    # fetches the branch; each page's own rule says whether it will be there to link to
    for key in KEYS:
        feed = sport_nav.LEAGUE[key]["feed"]
        try:
            write(key, N.feed_file(clone, f"{feed}/board.json"), N.feed_file(clone, f"{feed}/record.json"), have)
        except Exception as e:
            for f in outs(key):
                if os.path.exists(f): os.remove(f)
            print(f"{key}: FAILED ({type(e).__name__}: {e}) - no page written")


if __name__ == "__main__":
    main()
