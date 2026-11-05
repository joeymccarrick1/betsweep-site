# Dynasty trade calculator: age curves and rookie-pick values

Built 2026-10-20 from nflverse data. Files in this folder:

- `age_curves.json` — per position (QB/RB/WR/TE): year-over-year PPR ppg multipliers by age, smoothed curve, cumulative curve (peak = 1.0), and attrition/survival by age.
- `rookie_values.json` — per position and draft round (round 1 also by pick bucket): share of draftees who hit a top-12 (QB/TE) / top-24 (RB/WR) ppg season in their first 3 seasons, plus best-ppg distributions.
- `scripts/build.py` — the whole pipeline (`python3 -I scripts/build.py data . <weekly_2025_csv>`); `scripts/tables.py` renders the tables below.
- `data/` — raw downloads.

## 1. Data

| file | use | note |
|---|---|---|
| `stats_player_reg_<season>.csv` 2012–2024 (nflverse `player_stats` release) | per-player REG-season totals: `position`, `games`, `fantasy_points_ppr`, `targets`, `carries`, `player_id` (gsis) | 2025 file does not exist in the release (404) |
| `/home/claude/data/stats_player_week_2025.csv` (already on disk) | 2025 REG weeks 1–18 aggregated per player to the same shape | validated by aggregating the 2024 weekly file the same way: 1,996 common players, 0 point mismatches > 0.5, 5 game-count mismatches of 1 |
| `roster_<season>.csv` 2012–2025 (nflverse `rosters` release) | `birth_date` per `gsis_id` (first non-empty value across seasons) | 2012–2025 roster coverage is near-complete; player-seasons without a birth date dropped: see `meta.missing_birth_date_player_seasons_dropped` (0) |
| `draft_picks.csv` (nflverse `draft_picks` release) | `season`, `round`, `pick`, `gsis_id`, `position` for drafted players | 2012–2022 QB/RB/WR/TE draftees: 2,799 of 2,811 all-position picks have a gsis_id; 12 dropped (3 WR, 2 QB, rest defense/FB/C) |

Scoring is nflverse `fantasy_points_ppr` (full PPR, 4-pt pass TD, -2 INT, 6-pt rush/rec TD, -2 fumbles lost). ppg = `fantasy_points_ppr / games`, where `games` is games with any recorded stat line.

Position is the stats-file `position` in the season concerned. For age-curve pairs the cell is assigned by this-season position (a next-season position change is not required to match). For rookie hits the player must be ranked at his drafted position.

## 2. Age curves — method

- Pairs: every player with **>= 8 REG games in season s and >= 8 in s+1**, s = 2012..2024 (13 transitions, 2024->2025 uses the weekly-derived 2025 file).
- Age = integer age on **Sept 1 of season s+1** (the season being projected). So "age 27 multiplier" is what to multiply a player's age-26-season ppg by to project his age-27 season.
- Ratio = `ppg(s+1) / ppg(s)`.
- **Relevance floor** (primary curve): this-season ppg >= 8.0 QB, 4.0 RB, 4.0 WR, 3.0 TE. Without it the ratio is dominated by backups with 0.5–2 ppg whose ratios are pure noise (a 1 -> 3 ppg move is "3.0x"). Floors are roughly the ppg of the ~QB40 / RB60 / WR80 / TE30, i.e. anyone a dynasty roster would plausibly own. The unfiltered medians are kept in `raw[age].median_all` / `n_all` for comparison.
- Per-cell statistics: median (primary), 10% trimmed mean, and ratio-of-means (sum of next ppg / sum of this ppg, which weights toward the players who actually score).
- Smoothing: `smoothed[age]` = n-weighted mean of the raw medians over ages a-1..a+1. `quadratic[age]` = exp of a weighted least-squares quadratic in age fit to log(median) over cells with n >= 5.
- **`yoy_multiplier[age]` (recommended)** = rolling value shrunk toward the quadratic with weight `smoothed_n / (smoothed_n + 40)`, clipped to [0.55, 1.20], and forced non-increasing past the oldest age with raw n >= 10 (so a quadratic turning back up at age 36+ TE cannot leak in).
- **`cumulative_peak1[age]`** = product of `yoy_multiplier` from age 21 up to `age`, divided by its maximum. It is a relative production profile (peak = 1.0): use it only to compare ages, not to project a specific player (use the yoy multipliers for that).
- **Survival / attrition**: among players with >= 8 games in season s (and, for the `_relevant` variants, above the ppg floor), the share with >= 8 games in s+1 — at any position, no production requirement. `p_play_next_relevant_smoothed` pools counts over ages a-1..a+1 and is the recommended series. Note survival is *not* conditioned on the player producing: a player who plays 8+ games as a backup still "survives"; the ppg drop that comes with that is already inside the yoy multiplier.

### Headline numbers (recommended `yoy_multiplier`, age being projected)

| age -> | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QB | 0.99 | 0.99 | 0.99 | 0.98 | 0.97 | 0.98 | 0.99 | 0.99 | 0.96 | 0.96 | 0.94 | 0.91 |
| RB | 0.96 | 0.93 | 0.89 | 0.87 | 0.86 | 0.84 | 0.81 | 0.79 | 0.75 | 0.77 | 0.76 | 0.76 |
| WR | 1.04 | 1.01 | 0.94 | 0.93 | 0.87 | 0.88 | 0.85 | 0.85 | 0.79 | 0.80 | 0.78 | 0.83 |
| TE | 1.09 | 1.03 | 0.98 | 0.92 | 0.90 | 0.87 | 0.84 | 0.82 | 0.83 | 0.89 | 0.92 | 0.95 |

Cumulative (peak = 1.0) peaks at age 22 QB (essentially flat 22–30, then -4%/yr), 22 RB (0.79 by 25, 0.50 by 28, 0.32 by 30), 24 WR (0.94 at 25, 0.77 at 27, 0.49 at 30), 24 TE (0.82 at 27, 0.49 at 30).

Reading these: the multipliers are *conditional expectations for a fantasy-relevant player who plays both seasons*. They bundle three things — aging, regression to the mean (a player who was above the floor this year was on average a little lucky), and role churn. That is exactly the quantity a projection needs for "what will this guy score next year given what he scored this year", but it is **not** a pure aging curve: even a 25-year-old RB is expected to lose ~11% because top seasons regress. The cumulative curve compounds that regression every year and therefore overstates the fall-off for a player whose talent is known (see caveats).

The full per-age tables with sample sizes follow.

### QB age curve (n pairs with ppg floor: 309; without floor: 315)

| age | n | median ratio | trimmed mean | ratio of means | rolling (n) | quadratic | **yoy_multiplier** | **cumulative_peak1** | survival raw (n) | **survival smoothed (n)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | 0 | - | - | - | 0.986 (7) | 0.991 | **0.990** | **0.999** | - (0) | **0.778** (9) |
| 22 | 7 | 0.986 | 1.279 | 1.167 | 1.011 (33) | 0.992 | **1.001** | **1.000** | 0.778 (9) | **0.805** (41) |
| 23 | 26 | 1.018 | 1.062 | 1.050 | 0.995 (64) | 0.992 | **0.994** | **0.994** | 0.812 (32) | **0.790** (81) |
| 24 | 31 | 0.978 | 1.030 | 1.031 | 0.990 (92) | 0.991 | **0.990** | **0.985** | 0.775 (40) | **0.760** (121) |
| 25 | 35 | 0.980 | 0.976 | 0.969 | 0.986 (92) | 0.989 | **0.987** | **0.971** | 0.714 (49) | **0.719** (128) |
| 26 | 26 | 1.002 | 0.992 | 0.985 | 0.975 (82) | 0.987 | **0.979** | **0.951** | 0.667 (39) | **0.713** (115) |
| 27 | 21 | 0.934 | 0.962 | 0.941 | 0.965 (71) | 0.983 | **0.972** | **0.924** | 0.778 (27) | **0.755** (94) |
| 28 | 24 | 0.952 | 0.976 | 0.972 | 0.976 (65) | 0.979 | **0.977** | **0.903** | 0.857 (28) | **0.765** (85) |
| 29 | 20 | 1.047 | 1.065 | 1.047 | 0.993 (60) | 0.974 | **0.986** | **0.889** | 0.667 (30) | **0.741** (81) |
| 30 | 16 | 0.988 | 0.996 | 0.984 | 1.010 (53) | 0.968 | **0.992** | **0.882** | 0.696 (23) | **0.707** (75) |
| 31 | 17 | 0.987 | 1.093 | 1.068 | 0.951 (51) | 0.962 | **0.956** | **0.844** | 0.773 (22) | **0.739** (69) |
| 32 | 18 | 0.885 | 0.942 | 0.937 | 0.959 (51) | 0.955 | **0.957** | **0.808** | 0.750 (24) | **0.773** (66) |
| 33 | 16 | 1.014 | 1.062 | 1.031 | 0.936 (48) | 0.947 | **0.941** | **0.760** | 0.800 (20) | **0.774** (62) |
| 34 | 14 | 0.912 | 0.902 | 0.891 | 0.953 (41) | 0.938 | **0.946** | **0.718** | 0.778 (18) | **0.732** (56) |
| 35 | 11 | 0.917 | 0.912 | 0.919 | 0.898 (37) | 0.929 | **0.914** | **0.657** | 0.611 (18) | **0.740** (50) |
| 36 | 12 | 0.865 | 0.954 | 0.950 | 0.936 (33) | 0.919 | **0.927** | **0.609** | 0.857 (14) | **0.702** (47) |
| 37 | 10 | 1.043 | 1.049 | 1.063 | 0.917 (27) | 0.908 | **0.912** | **0.555** | 0.667 (15) | **0.730** (37) |
| 38 | 5 | 0.790 | 0.897 | 0.872 | 0.959 (15) | 0.897 | **0.912** | **0.506** | 0.625 (8) | **0.652** (23) |

### RB age curve (n pairs with ppg floor: 671; without floor: 830)

| age | n | median ratio | trimmed mean | ratio of means | rolling (n) | quadratic | **yoy_multiplier** | **cumulative_peak1** | survival raw (n) | **survival smoothed (n)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | 0 | - | - | - | 0.985 (35) | 1.068 | **1.029** | **0.987** | 0.000 (1) | **0.814** (43) |
| 22 | 35 | 0.985 | 1.048 | 1.044 | 1.012 (117) | 1.017 | **1.013** | **1.000** | 0.833 (42) | **0.824** (142) |
| 23 | 82 | 1.023 | 1.048 | 1.056 | 0.958 (232) | 0.972 | **0.960** | **0.960** | 0.828 (99) | **0.844** (275) |
| 24 | 115 | 0.903 | 0.982 | 0.968 | 0.931 (302) | 0.932 | **0.931** | **0.893** | 0.858 (134) | **0.812** (372) |
| 25 | 105 | 0.888 | 0.915 | 0.919 | 0.887 (316) | 0.898 | **0.888** | **0.793** | 0.755 (139) | **0.786** (402) |
| 26 | 96 | 0.866 | 0.906 | 0.913 | 0.874 (274) | 0.868 | **0.873** | **0.693** | 0.744 (129) | **0.747** (367) |
| 27 | 73 | 0.865 | 0.888 | 0.894 | 0.858 (228) | 0.842 | **0.856** | **0.593** | 0.737 (99) | **0.736** (310) |
| 28 | 59 | 0.839 | 0.893 | 0.875 | 0.843 (176) | 0.820 | **0.838** | **0.497** | 0.720 (82) | **0.710** (248) |
| 29 | 44 | 0.811 | 0.850 | 0.836 | 0.808 (124) | 0.802 | **0.806** | **0.401** | 0.657 (67) | **0.653** (190) |
| 30 | 21 | 0.716 | 0.792 | 0.792 | 0.787 (81) | 0.787 | **0.787** | **0.315** | 0.512 (41) | **0.600** (135) |
| 31 | 16 | 0.813 | 0.833 | 0.830 | 0.732 (48) | 0.775 | **0.752** | **0.237** | 0.593 (27) | **0.552** (87) |
| 32 | 11 | 0.646 | 0.677 | 0.693 | 0.781 (34) | 0.766 | **0.773** | **0.183** | 0.579 (19) | **0.607** (56) |
| 33 | 7 | 0.918 | 0.910 | 0.913 | 0.760 (21) | 0.761 | **0.760** | **0.139** | 0.700 (10) | **0.600** (35) |
| 34 | 3 | 0.810 | 0.675 | 0.668 | 0.861 (12) | 0.758 | **0.760** | **0.106** | 0.500 (6) | **0.632** (19) |
| 35 | 2 | 0.735 | 0.735 | 0.732 | 0.794 (6) | 0.758 | **0.760** | **0.081** | 0.667 (3) | **0.545** (11) |
| 36 | 1 | 0.863 | 0.863 | 0.863 | 0.847 (4) | 0.761 | **0.760** | **0.061** | 0.500 (2) | **0.667** (6) |
| 37 | 1 | 1.056 | 1.056 | 1.056 | 0.960 (2) | 0.766 | **0.760** | **0.047** | 1.000 (1) | **0.500** (4) |
| 38 | 0 | - | - | - | 1.056 (1) | 0.775 | **0.760** | **0.035** | 0.000 (1) | **0.500** (2) |

### WR age curve (n pairs with ppg floor: 1107; without floor: 1353)

| age | n | median ratio | trimmed mean | ratio of means | rolling (n) | quadratic | **yoy_multiplier** | **cumulative_peak1** | survival raw (n) | **survival smoothed (n)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | 2 | 1.226 | 1.226 | 1.226 | 1.179 (55) | 1.221 | **1.197** | **0.848** | 1.000 (2) | **0.859** (64) |
| 22 | 53 | 1.177 | 1.212 | 1.144 | 1.117 (189) | 1.138 | **1.121** | **0.951** | 0.855 (62) | **0.879** (215) |
| 23 | 134 | 1.092 | 1.100 | 1.074 | 1.037 (341) | 1.067 | **1.040** | **0.989** | 0.887 (151) | **0.824** (414) |
| 24 | 154 | 0.941 | 0.955 | 0.950 | 1.011 (434) | 1.008 | **1.011** | **1.000** | 0.766 (201) | **0.798** (544) |
| 25 | 146 | 1.010 | 1.008 | 1.007 | 0.940 (442) | 0.958 | **0.942** | **0.942** | 0.760 (192) | **0.770** (574) |
| 26 | 142 | 0.868 | 0.888 | 0.911 | 0.931 (411) | 0.916 | **0.930** | **0.875** | 0.784 (181) | **0.777** (529) |
| 27 | 123 | 0.910 | 0.944 | 0.934 | 0.874 (372) | 0.882 | **0.875** | **0.766** | 0.788 (156) | **0.775** (480) |
| 28 | 107 | 0.841 | 0.859 | 0.879 | 0.887 (312) | 0.855 | **0.883** | **0.676** | 0.748 (143) | **0.772** (404) |
| 29 | 82 | 0.911 | 0.889 | 0.893 | 0.854 (246) | 0.834 | **0.851** | **0.576** | 0.781 (105) | **0.741** (332) |
| 30 | 57 | 0.796 | 0.820 | 0.830 | 0.857 (180) | 0.820 | **0.850** | **0.489** | 0.679 (84) | **0.717** (251) |
| 31 | 41 | 0.831 | 0.882 | 0.903 | 0.782 (130) | 0.810 | **0.789** | **0.386** | 0.661 (62) | **0.692** (188) |
| 32 | 32 | 0.694 | 0.765 | 0.768 | 0.791 (90) | 0.806 | **0.795** | **0.307** | 0.762 (42) | **0.672** (134) |
| 33 | 17 | 0.876 | 0.843 | 0.824 | 0.765 (59) | 0.808 | **0.782** | **0.240** | 0.567 (30) | **0.656** (90) |
| 34 | 10 | 0.802 | 0.778 | 0.803 | 0.856 (32) | 0.815 | **0.833** | **0.200** | 0.556 (18) | **0.533** (60) |
| 35 | 5 | 0.893 | 0.841 | 0.782 | 0.841 (16) | 0.827 | **0.831** | **0.166** | 0.417 (12) | **0.444** (36) |
| 36 | 1 | 0.961 | 0.961 | 0.961 | 0.875 (7) | 0.845 | **0.831** | **0.138** | 0.167 (6) | **0.350** (20) |
| 37 | 1 | 0.696 | 0.696 | 0.696 | 0.829 (2) | 0.869 | **0.831** | **0.115** | 0.500 (2) | **0.200** (10) |
| 38 | 0 | - | - | - | 0.696 (1) | 0.900 | **0.831** | **0.095** | 0.000 (2) | **0.250** (4) |

### TE age curve (n pairs with ppg floor: 567; without floor: 697)

| age | n | median ratio | trimmed mean | ratio of means | rolling (n) | quadratic | **yoy_multiplier** | **cumulative_peak1** | survival raw (n) | **survival smoothed (n)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | 1 | 0.728 | 0.728 | 0.728 | 1.041 (15) | 1.331 | **1.200** | **0.778** | 1.000 (1) | **0.882** (17) |
| 22 | 14 | 1.064 | 1.185 | 1.127 | 1.090 (52) | 1.208 | **1.141** | **0.888** | 0.875 (16) | **0.788** (66) |
| 23 | 37 | 1.110 | 1.191 | 1.183 | 1.083 (120) | 1.109 | **1.089** | **0.967** | 0.755 (49) | **0.828** (145) |
| 24 | 69 | 1.072 | 1.056 | 1.050 | 1.035 (180) | 1.030 | **1.034** | **1.000** | 0.863 (80) | **0.800** (225) |
| 25 | 74 | 0.963 | 0.970 | 0.994 | 0.985 (216) | 0.968 | **0.983** | **0.983** | 0.771 (96) | **0.794** (272) |
| 26 | 73 | 0.926 | 0.925 | 0.920 | 0.921 (210) | 0.920 | **0.921** | **0.905** | 0.760 (96) | **0.772** (272) |
| 27 | 63 | 0.867 | 0.886 | 0.892 | 0.906 (193) | 0.885 | **0.902** | **0.817** | 0.787 (80) | **0.785** (246) |
| 28 | 57 | 0.923 | 0.947 | 0.926 | 0.870 (174) | 0.861 | **0.869** | **0.709** | 0.814 (70) | **0.817** (213) |
| 29 | 54 | 0.818 | 0.853 | 0.860 | 0.842 (157) | 0.848 | **0.843** | **0.598** | 0.857 (63) | **0.840** (187) |
| 30 | 46 | 0.770 | 0.812 | 0.830 | 0.814 (126) | 0.844 | **0.822** | **0.491** | 0.852 (54) | **0.792** (159) |
| 31 | 26 | 0.885 | 0.853 | 0.898 | 0.821 (88) | 0.851 | **0.830** | **0.408** | 0.619 (42) | **0.710** (124) |
| 32 | 16 | 0.860 | 0.883 | 0.893 | 0.901 (53) | 0.868 | **0.887** | **0.362** | 0.571 (28) | **0.609** (87) |
| 33 | 11 | 0.999 | 1.037 | 0.990 | 0.937 (39) | 0.895 | **0.916** | **0.331** | 0.647 (17) | **0.661** (59) |
| 34 | 12 | 0.982 | 1.005 | 1.045 | 0.977 (28) | 0.934 | **0.952** | **0.315** | 0.857 (14) | **0.667** (42) |
| 35 | 5 | 0.917 | 0.725 | 0.731 | 0.966 (19) | 0.987 | **0.952** | **0.300** | 0.455 (11) | **0.655** (29) |
| 36 | 2 | 0.996 | 0.996 | 0.897 | 0.910 (11) | 1.054 | **0.952** | **0.286** | 0.500 (4) | **0.579** (19) |
| 37 | 4 | 0.858 | 0.781 | 0.755 | 0.793 (9) | 1.140 | **0.952** | **0.272** | 1.000 (4) | **0.692** (13) |
| 38 | 3 | 0.570 | 0.627 | 0.574 | 0.734 (7) | 1.247 | **0.952** | **0.259** | 0.600 (5) | **0.778** (9) |



## 3. Rookie pick values — method

- Universe: QB/RB/WR/TE drafted 2012–2022 (`draft_picks.csv`), so every class has three complete seasons (2022 class: 2022–2024).
- Window: draft season, +1, +2.
- **Hit** = at least one season in the window with >= 8 games ranked **top-12 (QB, TE) or top-24 (RB, WR) by PPR ppg among >= 8-game players at that position** (positional rank taken from the season stats file, using the stats-file position, which must match the drafted position).
- `best_ppg` = the player's highest ppg across his >= 8-game seasons in the window; **0 if he never had one**. `mean_best_ppg_all` therefore is the expected "best season ppg" of a pick including busts — the number to price a pick with. `mean_best_ppg_if_qualified` and `_if_hit` describe the conditional upside.
- Round 1 is also split by overall pick 1–10 / 11–20 / 21–32.
- `hit_in_year1_share` = share of all draftees who hit already in their rookie season (how much of a pick's value is immediate).

### Headline rookie table (hit rate / expected best ppg incl. busts)

| | R1 | R1 pk 1–10 | R1 pk 11–20 | R1 pk 21–32 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|---|---|---|---|---|---|---|---|---|---|
| QB (n) | 50% / 16.1 (34) | 64% / 18.0 (22) | 33% / 14.6 (6) | 17% / 10.6 (6) | 22% / 9.0 (9) | 13% / 6.8 (16) | 5% / 1.3 (19) | 0% / 2.7 (10) | 6% / 1.7 (17) | 5% / 1.7 (19) |
| RB (n) | 73% / 16.3 (15) | 83% / 19.8 (6) | 100% / 19.3 (1) | 63% / 13.3 (8) | 62% / 12.6 (29) | 52% / 11.1 (31) | 13% / 6.5 (47) | 21% / 6.4 (33) | 12% / 3.9 (41) | 8% / 2.1 (40) |
| WR (n) | 46% / 12.1 (46) | 57% / 13.7 (14) | 40% / 12.9 (15) | 41% / 10.3 (17) | 25% / 10.1 (56) | 20% / 7.9 (46) | 4% / 4.1 (51) | 7% / 4.9 (45) | 0% / 2.5 (56) | 0% / 1.9 (53) |
| TE (n) | 78% / 11.5 (9) | 67% / 11.2 (3) | 100% / 11.4 (2) | 75% / 11.8 (4) | 39% / 7.5 (18) | 17% / 6.1 (29) | 7% / 5.0 (29) | 4% / 3.3 (24) | 0% / 2.3 (23) | 0% / 0.4 (23) |
| All four (n) | 54% / 14.0 (104) | 64% / 16.5 (45) | 46% / 13.4 (24) | 46% / 11.2 (35) | 37% / 10.2 (112) | 26% / 8.2 (122) | 8% / 4.7 (146) | 10% / 4.8 (112) | 4% / 2.8 (137) | 3% / 1.7 (135) |

Cells with n < 10 (RB round-1 buckets, all TE round-1 buckets, QB picks 11–32) are anecdotes, not estimates; use the pooled round-1 row or the "All four" row for those. The RB top-24 bar is low in absolute terms (roughly 10–11 ppg among >= 8-game RBs), which is why day-2 RBs "hit" >50% of the time; `mean_best_ppg_if_hit` (~16 ppg for RB R1–R3) tells you what a hit actually looks like.

Full tables follow.

### QB rookies (draft classes 2012-2022), n drafted = 124

| group | n | hit rate | hits | any 8-game season | mean best ppg (all) | mean best ppg (if qualified) | mean best ppg (if hit) | median best ppg | hit in draft year |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 34 | 50% | 17 | 91% | 16.1 | 17.7 | 21.4 | 17.4 | 12% |
| R2 | 9 | 22% | 2 | 56% | 9.0 | 16.2 | 21.6 | 11.7 | 0% |
| R3 | 16 | 12% | 2 | 50% | 6.8 | 13.6 | 20.3 | 4.3 | 6% |
| R4 | 19 | 5% | 1 | 11% | 1.3 | 12.4 | 17.9 | 0.0 | 5% |
| R5 | 10 | 0% | 0 | 20% | 2.6 | 13.2 | - | 0.0 | 0% |
| R6 | 17 | 6% | 1 | 12% | 1.7 | 14.2 | 17.9 | 0.0 | 0% |
| R7 | 19 | 5% | 1 | 11% | 1.7 | 16.1 | 18.5 | 0.0 | 0% |
| R1_pick_1-10 | 22 | 64% | 14 | 95% | 18.0 | 18.9 | 21.0 | 18.3 | 18% |
| R1_pick_11-20 | 6 | 33% | 2 | 100% | 14.6 | 14.6 | 20.6 | 13.3 | 0% |
| R1_pick_21-32 | 6 | 17% | 1 | 67% | 10.6 | 15.8 | 27.7 | 10.9 | 0% |
| day2_R2-3 | 25 | 16% | 4 | 52% | 7.6 | 14.6 | 20.9 | 8.6 | 4% |
| day3_R4-7 | 65 | 5% | 3 | 12% | 1.7 | 14.0 | 18.1 | 0.0 | 2% |
| all rounds | 124 | 19% | 24 | 42% | 6.8 | 16.3 | 20.9 | 0.0 | 5% |

### RB rookies (draft classes 2012-2022), n drafted = 236

| group | n | hit rate | hits | any 8-game season | mean best ppg (all) | mean best ppg (if qualified) | mean best ppg (if hit) | median best ppg | hit in draft year |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 15 | 73% | 11 | 93% | 16.3 | 17.5 | 20.1 | 17.7 | 60% |
| R2 | 29 | 62% | 18 | 97% | 12.6 | 13.1 | 16.3 | 13.3 | 38% |
| R3 | 31 | 52% | 16 | 87% | 11.1 | 12.8 | 16.0 | 11.3 | 16% |
| R4 | 47 | 13% | 6 | 79% | 6.5 | 8.3 | 15.3 | 6.2 | 2% |
| R5 | 33 | 21% | 7 | 76% | 6.4 | 8.4 | 15.3 | 5.5 | 9% |
| R6 | 41 | 12% | 5 | 56% | 3.9 | 7.0 | 13.9 | 1.6 | 5% |
| R7 | 40 | 8% | 3 | 35% | 2.1 | 6.1 | 15.7 | 0.0 | 0% |
| R1_pick_1-10 | 6 | 83% | 5 | 83% | 19.8 | 23.8 | 23.8 | 23.0 | 83% |
| R1_pick_11-20 | 1 | 100% | 1 | 100% | 19.3 | 19.3 | 19.3 | 19.3 | 0% |
| R1_pick_21-32 | 8 | 62% | 5 | 100% | 13.3 | 13.3 | 16.6 | 14.5 | 50% |
| day2_R2-3 | 60 | 57% | 34 | 92% | 11.8 | 12.9 | 16.2 | 12.8 | 27% |
| day3_R4-7 | 161 | 13% | 21 | 61% | 4.7 | 7.7 | 15.1 | 2.6 | 4% |
| all rounds | 236 | 28% | 66 | 71% | 7.3 | 10.2 | 16.5 | 6.1 | 13% |

### WR rookies (draft classes 2012-2022), n drafted = 353

| group | n | hit rate | hits | any 8-game season | mean best ppg (all) | mean best ppg (if qualified) | mean best ppg (if hit) | median best ppg | hit in draft year |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 46 | 46% | 21 | 91% | 12.1 | 13.3 | 16.8 | 12.5 | 17% |
| R2 | 56 | 25% | 14 | 93% | 10.1 | 10.8 | 16.9 | 10.3 | 4% |
| R3 | 46 | 20% | 9 | 89% | 7.9 | 8.9 | 17.2 | 6.4 | 2% |
| R4 | 51 | 4% | 2 | 65% | 4.1 | 6.3 | 18.1 | 2.5 | 2% |
| R5 | 45 | 7% | 3 | 69% | 4.9 | 7.2 | 17.0 | 4.1 | 2% |
| R6 | 56 | 0% | 0 | 48% | 2.5 | 5.2 | - | 0.0 | 0% |
| R7 | 53 | 0% | 0 | 40% | 1.9 | 4.8 | - | 0.0 | 0% |
| R1_pick_1-10 | 14 | 57% | 8 | 93% | 13.7 | 14.7 | 16.6 | 14.7 | 21% |
| R1_pick_11-20 | 15 | 40% | 6 | 100% | 12.8 | 12.8 | 16.7 | 12.4 | 13% |
| R1_pick_21-32 | 17 | 41% | 7 | 82% | 10.2 | 12.4 | 17.2 | 8.6 | 18% |
| day2_R2-3 | 102 | 23% | 23 | 91% | 9.1 | 10.0 | 17.0 | 8.5 | 3% |
| day3_R4-7 | 205 | 2% | 5 | 55% | 3.3 | 6.0 | 17.4 | 1.2 | 1% |
| all rounds | 353 | 14% | 49 | 70% | 6.1 | 8.7 | 17.0 | 4.8 | 4% |

### TE rookies (draft classes 2012-2022), n drafted = 155

| group | n | hit rate | hits | any 8-game season | mean best ppg (all) | mean best ppg (if qualified) | mean best ppg (if hit) | median best ppg | hit in draft year |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 9 | 78% | 7 | 100% | 11.5 | 11.5 | 11.9 | 11.1 | 22% |
| R2 | 18 | 39% | 7 | 89% | 7.5 | 8.4 | 11.3 | 7.5 | 0% |
| R3 | 29 | 17% | 5 | 83% | 6.1 | 7.4 | 12.8 | 5.8 | 3% |
| R4 | 29 | 7% | 2 | 93% | 5.0 | 5.4 | 10.2 | 4.8 | 0% |
| R5 | 24 | 4% | 1 | 71% | 3.3 | 4.7 | 16.2 | 2.9 | 0% |
| R6 | 23 | 0% | 0 | 65% | 2.3 | 3.6 | - | 1.9 | 0% |
| R7 | 23 | 0% | 0 | 22% | 0.4 | 2.0 | - | 0.0 | 0% |
| R1_pick_1-10 | 3 | 67% | 2 | 100% | 11.2 | 11.2 | 11.2 | 11.1 | 33% |
| R1_pick_11-20 | 2 | 100% | 2 | 100% | 11.4 | 11.4 | 11.4 | 11.4 | 0% |
| R1_pick_21-32 | 4 | 75% | 3 | 100% | 11.8 | 11.8 | 12.7 | 11.6 | 25% |
| day2_R2-3 | 47 | 26% | 12 | 85% | 6.6 | 7.8 | 12.0 | 6.2 | 2% |
| day3_R4-7 | 99 | 3% | 3 | 65% | 2.9 | 4.5 | 12.2 | 2.4 | 0% |
| all rounds | 155 | 14% | 22 | 73% | 4.5 | 6.2 | 12.0 | 4.0 | 2% |

### ALL_OFFENSE_SKILL rookies (draft classes 2012-2022)

| group | n | hit rate | hits | any 8-game season | mean best ppg (all) | mean best ppg (if qualified) | mean best ppg (if hit) | median best ppg | hit in draft year |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 104 | 54% | 56 | 92% | 14.0 | 15.2 | 18.2 | 14.1 | 22% |
| R2 | 112 | 37% | 41 | 90% | 10.2 | 11.3 | 15.9 | 10.6 | 12% |
| R3 | 122 | 26% | 32 | 82% | 8.2 | 9.9 | 16.1 | 7.8 | 7% |
| R4 | 146 | 8% | 11 | 68% | 4.7 | 6.9 | 15.2 | 4.3 | 2% |
| R5 | 112 | 10% | 11 | 67% | 4.8 | 7.2 | 15.9 | 3.5 | 4% |
| R6 | 137 | 4% | 6 | 49% | 2.8 | 5.7 | 14.6 | 0.0 | 1% |
| R7 | 135 | 3% | 4 | 31% | 1.7 | 5.4 | 16.4 | 0.0 | 0% |
| R1_pick_1-10 | 45 | 64% | 29 | 93% | 16.5 | 17.6 | 19.6 | 17.2 | 29% |
| R1_pick_11-20 | 24 | 46% | 11 | 100% | 13.4 | 13.4 | 16.7 | 12.8 | 8% |
| R1_pick_21-32 | 35 | 46% | 16 | 86% | 11.2 | 13.1 | 16.8 | 11.2 | 23% |

## 4. Caveats (read before wiring these into a calculator)

1. **Survivorship in the ratio.** Each yoy multiplier conditions on the player appearing in >= 8 games both seasons. Players who retire, get cut, or get hurt for most of the next year are *excluded* from the ratio and show up only in the survival series. The calculator must multiply the two: `expected next ppg x P(plays)`; using the multiplier alone overstates old players, using survival alone (with no ppg decline) overstates them even more.
2. **Selection into fantasy relevance / regression to the mean.** The ppg floor keeps the sample meaningful, but anyone above the floor this year was partly lucky, so the multipliers embed regression toward the positional mean. For a stable, established starter the true aging decline is milder than the table (e.g. WR 27 -> 28 true aging is nearer 0.95 than 0.88). Compounding the multipliers over 2–3 years double-counts that regression; the 3-year formula below is therefore conservative for stars and roughly right for the median relevant player. If you want a purer aging signal, compare `ratio_of_means` (production-weighted, less dragged down by fringe players) with `median`.
3. **Sample sizes.** Ages 21–22 and 33+ are thin for RB/WR/TE (n < 20 in most cells), QB has only 300 relevant pairs in total (16–35 per age). The JSON carries `n` for every cell and `smoothed_n` for the rolling window; the shrinkage to the quadratic is what keeps thin cells from producing silly values. Anything past age 32 RB, 34 WR/TE, 36 QB is extrapolated by construction (held flat at the last reliable value).
4. **Positional reclassification.** Position comes from the nflverse stats file; a handful of players flip (FB/RB, WR/TE, WR/RB). Rookie hits require the player to be ranked at the drafted position, so e.g. a drafted WR who became a TE would read as a miss.
5. **Rule / era drift.** 2012–2020 were 16-game seasons, 2021+ are 17; the >= 8 game threshold is unchanged. Passing environment and RB usage changed across the window; a 14-year pooled curve is a compromise between sample size and recency.
6. **Rookie window = 3 seasons, classes 2012–2022.** Players who broke out in year 4+ (e.g. late-blooming WRs) count as misses; that is intentional for a 3-year discounted model but understates the long-run value of day-2 WR/TE picks. The 2022 class is the last one with a complete window; 2023–2025 draftees are not included.
7. **Hit threshold is ppg-based with an 8-game minimum,** so a 9-game hot streak counts. This inflates hit rates relative to a full-season total-points top-24 and is one reason RB day-2 hit rates look high. `median_best_ppg_all` and the p25/p75 fields in the JSON give the distribution.
8. **2025 season comes from the weekly file**, not the official seasonal release; the 2024 cross-check showed it is equivalent, but if nflverse later restates 2025, rerun `build.py`.
9. The draft_picks file lacks a gsis_id for 12 of 2,811 picks (3 WR, 2 QB among them); they are dropped, not counted as misses.

## 5. How to use these in a 3-year discounted value

Inputs for a player: `pos`, `age_now` (age on Sept 1 of the current season), `ppg_ros` (your rest-of-season projection or current ppg), `games_ros` (games remaining this season), and a full-season game count `G` (17).

```
curve = age_curves[pos]
m(a)  = curve["yoy_multiplier"][str(a)]                           # multiplier INTO age a
s(a)  = curve["survival"][str(a)]["p_play_next_relevant_smoothed"]  # P(plays >= 8 games at age a | played at a-1)
d     = 0.8                                                       # per-year discount

year1 = ppg_ros * games_ros

ppg2  = ppg_ros * m(age_now + 1)
surv2 = s(age_now + 1)
year2 = ppg2 * surv2 * G * d

ppg3  = ppg2 * m(age_now + 2)
surv3 = surv2 * s(age_now + 2)
year3 = ppg3 * surv3 * G * d**2

value = year1 + year2 + year3
```

i.e. `value = year1_ROS + sum_{k=2..3} ( ppg_ros x prod_{j=1..k-1} yoy_multiplier[age_now+j] ) x ( prod_{j=1..k-1} p_play_next_relevant_smoothed[age_now+j] ) x G x 0.8^(k-1)`.

Notes:
- Use `yoy_multiplier` and `p_play_next_relevant_smoothed`, not `cumulative_peak1`. The cumulative curve is only for displaying "where is this player on the arc"; `cumulative_peak1[age_now+1] / cumulative_peak1[age_now]` equals `yoy_multiplier[age_now+1]` anyway.
- If a key is missing (age outside 21–38) clamp the age to the nearest available key.
- Survival here means "plays >= 8 games"; a player who plays only 8–10 games still scores less than `G` games' worth. If you want to be stricter, multiply year2/year3 by ~0.9 (the average >= 8-game player plays ~15 of 17 games) or project `games` instead of using `G`.
- Because of caveat 2, consider blending the multiplier toward 1.0 for established stars (e.g. `m' = 0.5*m + 0.5*max(m, pure_aging_guess)`), or simply treat the output as a floor-ish value for elite players.

Rookie picks, same units: for a pick in round r at position p (or unknown position: `ALL_OFFENSE_SKILL`), take `rookie_values[p]["by_round"]["R<r>"]` (or `["round1_by_pick"][bucket]` when n >= 10):

```
rv = rookie_values[pos]["by_round"]["R1"]
# expected best-season ppg of the pick including busts, spread over the 3-year window
# with the same discount; a simple pricing is:
pick_value = rv["mean_best_ppg_all"] * G * (0.35*1 + 0.9*0.8 + 1.0*0.64) * rookie_haircut
```

where the 0.35 / 0.9 / 1.0 weights reflect that only `hit_in_year1_share / hit_rate` of the eventual hits (roughly a third for WR/QB, two thirds for RB) are already producing in year 1, and `rookie_haircut` (~0.6–0.75) converts "best season" into "average season over the window". Alternatively price picks by matching `hit_rate` x `mean_best_ppg_if_hit` against the value of an existing player with that ppg at age 22–23 (which gets the full positive early-career multipliers above). Pick values for a *future* draft should also be discounted a further 0.8 per year until the draft.

Exact JSON field names used above: `age_curves[pos].yoy_multiplier[age]`, `age_curves[pos].survival[age].p_play_next_relevant_smoothed`, `age_curves[pos].cumulative_peak1[age]`, `rookie_values[pos].by_round["R1".."R7"].{n, hit_rate, mean_best_ppg_all, mean_best_ppg_if_hit, hit_in_year1_share}`, `rookie_values[pos].round1_by_pick["R1_pick_1-10"|"R1_pick_11-20"|"R1_pick_21-32"]`, `rookie_values.ALL_OFFENSE_SKILL.by_round`.
