"""Writes backtests/RESULTS.md and the current grids from the three result files.   python -m sports.report"""
import json, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.join(HERE, "backtests")


def pct(a, b):
    return 100.0 * (1.0 - a / b)


def main():
    nba, epl, cfb = (json.load(open(os.path.join(BT, f + ".json"))) for f in ("nba", "epl", "cfb"))
    L = ["# Walk-forward results", "",
         "Every projection below was made from earlier games only. Weights were chosen on one season and scored on the next, which they never saw.",
         "Lower is better for every error number. Nothing here has been compared with FanDuel's prices yet: no NBA, EPL or college prices are stored.", ""]
    h = nba["seasons"]["2027"]
    L += [f"## NBA (data through {nba['data_through']})", "",
          f"Checked on {h['player_games']:,} player-games of 2026-27 (rotation players), weights chosen on 2025-26.", "",
          "| Stat | Season average | Model | Better by |", "|---|---|---|---|"]
    for s, name in (("pts", "Points"), ("reb", "Rebounds"), ("ast", "Assists"), ("fg3", "Threes"), ("pra", "Pts + reb + ast")):
        L.append(f"| {name} | {h[s]['season_avg']:.2f} | {h[s]['model']:.2f} | {h[s]['gain_vs_season_avg_pct']:.1f}% |")
    L += [f"| Minutes | {h['minutes']['season_avg']:.2f} | {h['minutes']['with_budget']:.2f} | {pct(h['minutes']['with_budget'], h['minutes']['season_avg']):.1f}% |", "",
          "Average miss per player per game. The minutes line uses the players who actually played, so it is the projection once the night's inactives are known.", "",
          "Hit chances for 'X+' lines, 2026-27 (Brier score: 0 is perfect; 'own hit rate' is the 'cleared it in 7 of 10' number on a prop page):", "",
          "| Market | Model | Own hit rate |", "|---|---|---|"]
    for s, name in (("pts", "Points 10+ to 30+"), ("reb", "Rebounds 4+ to 12+"), ("ast", "Assists 2+ to 10+"), ("fg3", "Threes 1+ to 5+")):
        b = nba["hit_chances"][s]["brier_all_lines"]
        L.append(f"| {name} | {b['model']:.4f} | {b['own_hit_rate']:.4f} |")
    L += ["", "What moved the number most on 2025-26 (the tuning log is in nba.json): fitting the active players' minutes to the team's 240 "
          "(minutes miss 4.68 -> 4.37), then the team-total step; the defense-vs-position matchup moved points by about 0.003.", ""]
    t, t0 = epl["team"]["2027"], epl["team"]["2026"]
    e0 = epl["elo_only_benchmark"]["2026"]
    L += [f"## Premier League (data through {epl['data_through']})", "",
          "| | Matches | Model | Last season's rates | Elo only |", "|---|---|---|---|---|",
          f"| Home / draw / away, 2025-26 (weights chosen here) | {t0['matches']} | {t0['h_d_a']['logloss_model']:.4f} | {t0['h_d_a']['logloss_last_season_rates']:.4f} | {e0['logloss']:.4f} |",
          f"| Home / draw / away, 2026-27 (never seen) | {t['matches']} | {t['h_d_a']['logloss_model']:.4f} | {t['h_d_a']['logloss_last_season_rates']:.4f} | not on file |", "",
          "Log loss. The grid is level with an Elo-only model. Over 2.5 goals and both-teams-to-score were no better than last season's flat rate in 2025-26 "
          f"({t0['over_2_5']['brier_model']:.4f} vs {t0['over_2_5']['brier_last_season_rate']:.4f} on over 2.5), so totals are not a strength of this version.", ""]
    p = epl["player"]["2027"]; a = p["anytime_scorer"]
    L += [f"Players, 2026-27: {p['starts']:,} starts by outfield players with 450+ minutes on record.", "",
          "| Market | Legs | Model | Benchmark |", "|---|---|---|---|",
          f"| Anytime goalscorer (Brier) | {a['legs_with_5_games']} | {a['brier_model']:.4f} | {a['brier_own_scoring_rate']:.4f} (own scoring rate) |"]
    for k, name in (("shots", "Shots"), ("sot", "Shots on target")):
        for r in p[k]["lines"][:2]:
            L.append(f"| {name} {r['line']} (Brier) | {r['legs']} | {r['brier_model']:.4f} | {r['brier_own_hit_rate']:.4f} (own hit rate) |")
    L += [f"| Shots per start (average miss) | | {p['shots']['mae_model']:.3f} | {p['shots']['mae_per_appearance_avg']:.3f} (per-game average) |", "",
          "One hundred matches is a small sample; read 2026-27 as a direction.", ""]
    c, c0 = cfb["lines"]["2026"], cfb["lines"]["2025"]
    L += [f"## College football (data through {cfb['data_through']})", "", "Game lines against DraftKings' spread and total (the only prices on file).", "",
          "| | Games | Model | Book |", "|---|---|---|---|",
          f"| Margin, average miss, 2025 (weights chosen here) | {c0['games_with_a_line']} | {c0['margin_mae']['model']:.2f} | {c0['margin_mae']['book']:.2f} |",
          f"| Margin, average miss, 2026 (never seen) | {c['games_with_a_line']} | {c['margin_mae']['model']:.2f} | {c['margin_mae']['book']:.2f} |",
          f"| Total, average miss, 2026 | {c['games_with_a_line']} | {c['total_mae']['model']:.2f} | {c['total_mae']['book']:.2f} |",
          f"| Winner picked, 2026 | {c['games_with_a_line']} | {100 * c['winner_picked']['model']:.1f}% | {100 * c['winner_picked']['book']:.1f}% |", ""]
    a5 = [x for x in c["against_the_spread"] if x["min_gap"] == 5.0][0]; a0 = [x for x in c["against_the_spread"] if x["min_gap"] == 0.0][0]
    b5 = [x for x in c0["against_the_spread"] if x["min_gap"] == 5.0][0]
    L += [f"Against the spread in 2026, taking the model's side every game: {a0['wins']}-{a0['bets'] - a0['wins']} ({100 * a0['win_pct']:.1f}%). "
          f"Only when the model and the book are 5+ points apart: {a5['wins']}-{a5['bets'] - a5['wins']} ({100 * a5['win_pct']:.1f}%); the same rule was "
          f"{b5['wins']}-{b5['bets'] - b5['wins']} ({100 * b5['win_pct']:.1f}%) on 2025, the season the weights were fitted to. 52.4% is break-even at -110.",
          f"Weight the 2026 results put on the model when it disagrees with the book: {c['weight_on_model_vs_book']['margin']:.2f} for margins, "
          f"{c['weight_on_model_vs_book']['total']:.2f} for totals (0 = the book's number already holds everything this grid knows).", "",
          "Player layer, 2026 (not bettable in Tennessee):", "", "| Stat | Player-games | Season average | With matchup | Better by |", "|---|---|---|---|---|"]
    for k, name in (("pass_yds", "Passing yards"), ("rush_yds", "Rushing yards"), ("rec_yds", "Receiving yards"), ("rec", "Receptions")):
        v = cfb["player"]["2026"][k]
        L.append(f"| {name} | {v['player_games']:,} | {v['mae_season_avg']:.2f} | {v['mae_with_matchup']:.2f} | {v['gain_vs_season_avg_pct']:.1f}% |")
    L.append("")
    open(os.path.join(BT, "RESULTS.md"), "w").write("\n".join(L))
    os.makedirs(os.path.join(BT, "grids"), exist_ok=True)
    pd.DataFrame(epl["grid_today"]["clubs"]).to_csv(os.path.join(BT, "grids", "epl_attack_defence.csv"), index=False)
    pd.DataFrame(cfb["grid_today"]["top25"]).to_csv(os.path.join(BT, "grids", "cfb_top25_offense_defense.csv"), index=False)
    try:
        from .nba import data as ND, model as NM
        NM.defense_grid(ND.load([2027])).round(3).to_csv(os.path.join(BT, "grids", "nba_defense_vs_position.csv"), index=False)
    except FileNotFoundError:
        pass
    print("wrote", os.path.join(BT, "RESULTS.md"))


if __name__ == "__main__":
    main()
