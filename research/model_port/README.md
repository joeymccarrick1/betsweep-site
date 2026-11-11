# Moving the model from the sheet into code

Owner, 11/10 deep dive: "Move the model from the sheet into code before a second sport."

**Where it stands (11/10):** started, not done. The sheet is still the model; nothing on the site reads this folder.

## Why
The projections live in Google Sheets formulas across about forty tabs. That has worked for one sport, but it means the model
cannot be tested (a formula edit has no check behind it), cannot be re-run on last season (backtests re-implement pieces by hand in
research/), and cannot be copied to another sport without copying the workbook.

## How the port works
1. **Parity first.** `parity.py` recomputes a column from the row's other columns in the mirror (`in/*.json`, refreshed every 30
   minutes) and compares it with the sheet's own cell. A column is "ported" only at 100% of rows; then it is marked claimed in
   `port.py` and the run fails the day the sheet and the code drift apart.
2. **Backwards through the chain.** Each step's inputs must already be mirror columns so it can be checked end to end:
   fantasy points (done for QB) -> projected stat lines from opportunity x efficiency -> opportunity (role weights, vacated targets
   and carries, availability) -> efficiency (catch rate, yards per touch, TD rates with their shrinkage) -> matchup factors ->
   leg probabilities ('V2 - Leg Board') -> game scripts and the four endings.
3. **The formulas are the spec.** The mirror carries values, not formulas. The next step is a formula census: read row 2 of each
   projection tab with the Sheets connector asking for `userEnteredValue` (the formula text), save it under `formulas/`, and port
   column by column from the text instead of guessing from numbers.
4. **Only when a whole tab is at parity** does a generator read the code instead of the mirror - behind a flag, with the sheet's
   value printed next to it for two weeks.

## What is here
- `port.py` - the ported columns. 11/10: fantasy-point roll-ups. QB matches the sheet on 66 of 66 rows (claimed). RB and WR match on
  all inactive rows and all but 9 and 13 active rows, which run 0.05-0.4 points high: the sheet trims the reception count for some
  players in a way the "(Audit)" column does not show. Not claimed until the formula is read.
- `parity.py` - the check, plus a census of the mirrored tabs (rows and columns).

## Order of work from here
1. Formula census for the four projection tabs (one session, connector calls only).
2. Close RB / WR / TE fantasy points; claim them.
3. Projected stat lines (Proj Rec Yds = adjusted opportunity x catch rate x yards per reception, and the like), then the
   opportunity and efficiency columns behind them.
4. 'V2 - Leg Board' model % from the projection and the line - the number every page shows.
5. Team scores and the four endings ('V2 - Game Scripts').
