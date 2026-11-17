"""finals.py: what the build hands the Live page about finished games (11/17). No network: a made-up season in a temp folder.
  python3 tests/finals_build.py"""
import csv, os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import finals, subprocess
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
SCOLS = ["player_display_name", "season", "week", "season_type", "team", "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions", "carries", "rushing_yards", "rushing_tds",
         "receptions", "targets", "receiving_yards", "receiving_tds", "def_tds", "special_teams_tds", "fumble_recovery_tds", "fg_made", "pat_made", "rushing_2pt_conversions", "receiving_2pt_conversions", "def_safeties"]
def srow(name, week, team, **kw): return dict({c: 0 for c in SCOLS}, player_display_name=name, season=2026, week=week, season_type="REG", team=team, **kw)
def write(IN, games, stats, snaps):
    with open(os.path.join(IN, "games.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["season", "game_type", "week", "away_team", "away_score", "home_team", "home_score", "gameday", "gametime"]); w.writeheader(); w.writerows(games)
    with open(os.path.join(IN, "stats_player_week_2026.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, SCOLS); w.writeheader(); w.writerows(stats)
    with open(os.path.join(IN, "snap_counts_2026.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["season", "game_type", "week", "player", "team", "offense_snaps", "st_snaps"]); w.writeheader(); w.writerows(snaps)
def game(week, a, sa, h, sh): return {"season": 2026, "game_type": "REG", "week": week, "away_team": a, "away_score": sa, "home_team": h, "home_score": sh, "gameday": "2026-11-15", "gametime": "13:00"}
def snap(week, name, team, n=30): return {"season": 2026, "game_type": "REG", "week": week, "player": name, "team": team, "offense_snaps": n, "st_snaps": 0}
# week 5: AAA 24 at BBB 17 (complete), CCC 20 at DDD 10 (the file's points for CCC are short), EEE 13 at FFF 9 (no stat lines yet), GGG at HHH not played
def season(aaa_snaps=True):
    st = [srow("Quinn Passer", 5, "AAA", completions=20, attempts=30, passing_yards=250, passing_tds=2, passing_interceptions=1, carries=3, rushing_yards=12),
          srow("Rory Runner", 5, "AAA", carries=18, rushing_yards=88, rushing_tds=0, receptions=2, targets=3, receiving_yards=9, special_teams_tds=1),   # his touchdown was a kick return
          srow("Wes Catcher", 5, "AAA", receptions=6, targets=9, receiving_yards=74, receiving_tds=2),
          srow("Kai Kicker", 5, "AAA", fg_made=1, pat_made=3),                                     # 3 TD x 6 + 3 + 3 = 24
          srow("Bo Back", 5, "BBB", carries=15, rushing_yards=61, rushing_tds=2), srow("Ben Boot", 5, "BBB", fg_made=1, pat_made=2),   # 12 + 3 + 2 = 17
          srow("Cy Carrier", 5, "CCC", carries=20, rushing_yards=90, rushing_tds=2), srow("Dee Dasher", 5, "DDD", carries=10, rushing_yards=40, rushing_tds=1), srow("Dan Toe", 5, "DDD", fg_made=1, pat_made=1),
          srow("Sam Scratch", 4, "AAA", receptions=3, targets=4, receiving_yards=31), srow("Otto Bench", 4, "AAA", receptions=1, targets=1, receiving_yards=5)]
    sn = [snap(5, "Quinn Passer", "AAA"), snap(5, "Rory Runner", "AAA"), snap(5, "Wes Catcher", "AAA"), snap(5, "Otto Bench", "AAA", 12), snap(5, "Bo Back", "BBB"), snap(4, "Sam Scratch", "AAA")]
    if not aaa_snaps: sn = [x for x in sn if not (x["week"] == 5 and x["team"] == "AAA")]
    return [game(5, "AAA", 24, "BBB", 17), game(5, "CCC", 20, "DDD", 10), game(5, "EEE", 13, "FFF", 9), game(5, "GGG", "", "HHH", "")], st, sn
GAMES = [{"gid": "AAA-BBB"}, {"gid": "CCC-DDD"}, {"gid": "EEE-FFF"}, {"gid": "GGG-HHH"}]
LEGS = [{"pl": n, "tm": t, "g": g} for n, t, g in (("Quinn Passer", "AAA", "AAA-BBB"), ("Rory Runner", "AAA", "AAA-BBB"), ("Wes Catcher", "AAA", "AAA-BBB"), ("Otto Bench", "AAA", "AAA-BBB"), ("Sam Scratch", "AAA", "AAA-BBB"),
                                                  ("Typo Nmae", "AAA", "AAA-BBB"), ("Bo Back", "BBB", "AAA-BBB"), ("Cy Carrier", "CCC", "CCC-DDD"), ("Eli Early", "EEE", "EEE-FFF"), ("Gus Later", "GGG", "GGG-HHH"))] + [{"pl": "AAA ML", "tm": "AAA", "g": "AAA-BBB", "gl": {"k": "M"}}]
with tempfile.TemporaryDirectory() as IN:
    write(IN, *season()); fb = finals.build(IN, 5, GAMES, LEGS, log=lambda *a: None)
    a = fb.get("AAA-BBB", {})
    check(set(fb) == {"AAA-BBB", "CCC-DDD", "EEE-FFF"}, f"only games with a final score are handed over ({sorted(fb)})")
    check(a.get("sc") == {"AAA": 24, "BBB": 17}, f"the final score is keyed by team ({a.get('sc')})")
    check(a.get("box", {}).get("Quinn Passer") == [250, 2, 1, 12, 0, 0, 0, 0, 20, 30, 3, 0, 0] and a["box"].get("Wes Catcher") == [0, 0, 0, 0, 0, 6, 74, 2, 0, 0, 0, 9, 0], f"a stat line is the thirteen numbers the page reads ({a.get('box', {}).get('Quinn Passer')})")
    check(a["box"].get("Rory Runner") == [0, 0, 0, 88, 0, 2, 9, 0, 0, 0, 18, 3, 1], f"a return touchdown is carried in the last number, so the page can pay an anytime-TD leg on it ({a['box'].get('Rory Runner')})")
    check(a["box"].get("Otto Bench") == [0] * 13, "a man who was on the field with nothing in the box score gets a row of zeros (his overs lose)")
    check(a.get("dnp") == ["Sam Scratch"], f"a man with no stat line and no snaps, known from another week, did not play ({a.get('dnp')})")
    check("Typo Nmae" not in a["box"] and "Typo Nmae" not in a.get("dnp", []), "a name the files have never seen is left out - not voided, not zeroed")
    check("AAA ML" not in a["box"], "game-line legs are not players")
    check("box" not in fb["CCC-DDD"] and fb["CCC-DDD"]["sc"] == {"CCC": 20, "DDD": 10}, "when the file's points do not add up to the final score, the game gets its score only (the page asks ESPN for the box)")
    check("box" not in fb["EEE-FFF"], "a final with no stat lines yet gets its score only")
    write(IN, *season(aaa_snaps=False)); fb = finals.build(IN, 5, GAMES, LEGS, log=lambda *a: None); a = fb["AAA-BBB"]
    check("dnp" not in a and "Sam Scratch" not in a["box"] and "Otto Bench" not in a["box"], "before snap counts are published nobody is called did-not-play or zero: a man with no stat line is left ungraded")

    # ---- refresh(): a newer copy only when a final game is missing from the one on hand ----
    calls = []; real = subprocess.run
    def fake_run(cmd, **kw):
        calls.append(cmd[-1]); out = cmd[cmd.index("-o") + 1]
        if fake_run.mode == "fail": raise subprocess.CalledProcessError(22, cmd)
        if fake_run.mode == "junk": open(out, "w").write("<html>not found</html>\n")
        else:
            g, st, sn = season()
            if "stats_player" in cmd[-1]:
                with open(out, "w", newline="") as f:
                    w = csv.DictWriter(f, SCOLS); w.writeheader(); w.writerows(st + [srow("Eli Early", 5, "EEE", carries=9, rushing_yards=30), srow("Fay Far", 5, "FFF", carries=9, rushing_yards=30)])
            else:
                with open(out, "w", newline="") as f:
                    w = csv.DictWriter(f, ["season", "game_type", "week", "player", "team", "offense_snaps", "st_snaps"]); w.writeheader(); w.writerows(sn + [snap(5, "X", t) for t in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")])
    subprocess.run = fake_run
    try:
        old = time.time() - 7200
        def age():
            for n in ("stats_player_week_2026.csv", "snap_counts_2026.csv"): os.utime(os.path.join(IN, n), (old, old))
        write(IN, *season()); fake_run.mode = "good"; done = finals.refresh(IN, 2026, 5, log=lambda *a: None)
        check(done == [] and not calls, "a copy made a moment ago is not fetched again (nflverse has simply not published the game yet)")
        age(); fake_run.mode = "fail"; done = finals.refresh(IN, 2026, 5, log=lambda *a: None)
        check(done == [] and len(calls) == 2 and "EEE" not in open(os.path.join(IN, "stats_player_week_2026.csv")).read(), "a failed download changes nothing")
        age(); calls.clear(); fake_run.mode = "junk"; done = finals.refresh(IN, 2026, 5, log=lambda *a: None)
        check(done == [] and "Quinn Passer" in open(os.path.join(IN, "stats_player_week_2026.csv")).read(), "a download that is not the file (an error page) is thrown away")
        age(); calls.clear(); fake_run.mode = "good"; done = finals.refresh(IN, 2026, 5, log=lambda *a: None)
        check(sorted(done) == ["snap_counts_2026.csv", "stats_player_week_2026.csv"] and "Eli Early" in open(os.path.join(IN, "stats_player_week_2026.csv")).read(), f"a final game missing from an older copy brings in the newer copy ({done})")
        age(); calls.clear(); done = finals.refresh(IN, 2026, 5, log=lambda *a: None)
        check(done == [] and not calls, "once every final game is in the copy nothing is downloaded")
        done = finals.refresh(IN, 2026, 9, log=lambda *a: None)
        check(done == [] and not calls, "a week with no final game downloads nothing")
    finally: subprocess.run = real
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
