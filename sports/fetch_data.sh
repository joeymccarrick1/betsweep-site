#!/usr/bin/env bash
# Downloads the public history the backtests use into sports/_data (not committed). About 1.1 GB, mostly college play-by-play.
#   bash sports/fetch_data.sh            then:  BS_SPORTS_DATA=sports/_data python -m sports.nba.backtest   (also .epl. and .cfb.)
set -euo pipefail
D="${BS_SPORTS_DATA:-$(dirname "$0")/_data}"; mkdir -p "$D"; cd "$D"
B=https://github.com/sportsdataverse/sportsdataverse-data/releases/download
for y in 2025 2026 2027; do curl -sSLf -o "nba_player_box_$y.csv" "$B/espn_nba_player_boxscores/player_box_$y.csv"; done
curl -sSLf -o nba_schedule_2027.csv "$B/espn_nba_schedules/nba_schedule_2027.csv"
for y in 2022 2023 2024 2025 2026; do curl -sSLf -o "cfb_schedule_$y.csv" "$B/espn_cfb_schedules/cfb_schedule_$y.csv"; done
for y in 2025 2026; do curl -sSLf -o "cfb_pbp_$y.csv" "$B/cfbfastR_cfb_pbp/play_by_play_$y.csv"; for k in lines team_stats player_games; do [ -f "cfb_${k}_$y.csv" ] && rm "cfb_${k}_$y.csv"; done; done
if [ ! -d fplei ]; then git clone -q --depth 1 --filter=blob:none --sparse https://github.com/olbauday/FPL-Elo-Insights fplei; fi
cd fplei && git pull -q --depth 1 2>/dev/null || true
git sparse-checkout set --no-cone '/data/2024-2025/matches/matches.csv' '/data/2024-2025/playermatchstats/' '/data/2024-2025/players/' '/data/2024-2025/teams/' \
  '/data/2025-2026/By Tournament/Premier League/' '/data/2025-2026/players.csv' '/data/2025-2026/teams.csv' \
  '/data/2026-2027/By Tournament/Premier League/' '/data/2026-2027/players.csv' '/data/2026-2027/teams.csv'
git checkout -q
echo "data ready in $D"
