"""port.py - the model, column by column, in code (owner 11/10 deep dive: "move the model from the sheet into code before a second sport").

Rule of the port: a column moves here only when parity.py shows the code reproduces the sheet's own value on every row of the
mirror. Until every column of a tab has moved, the sheet stays the model and nothing on the site reads this file.

Ported so far (11/10): the fantasy-points roll-up of each projection tab - the last step of the chain, and the one whose inputs
(the projected stat lines and the scoring settings) are themselves columns of the mirror, so it could be checked end to end.
"""

def _f(x, d=0.0):
    try: return float(str(x).replace(",", "").replace("%", ""))
    except Exception: return d


def scoring(settings_rows):
    s = {str(r[0]).strip(): r[1] for r in settings_rows if len(r) > 1}
    return {"pass_yds_per_pt": _f(s.get("Pass Yds / FP"), 25), "pass_td": _f(s.get("Pass TD FP"), 6), "int": _f(s.get("INT FP"), -2),
            "rush_yds_per_pt": _f(s.get("Rush Yds / FP"), 10), "rush_td": _f(s.get("Rush TD FP"), 6),
            "rec_yds_per_pt": _f(s.get("Rec Yds / FP"), 10), "rec_td": _f(s.get("Rec TD FP"), 6), "rec": _f(s.get("Reception FP"), 1)}


def fp_qb(row, sc):
    """row = dict of the QB tab's columns. 'Proj Fantasy Pts'."""
    return (_f(row.get("Proj Pass Yds")) / sc["pass_yds_per_pt"] + _f(row.get("Proj Pass TD")) * sc["pass_td"] + _f(row.get("Proj INT")) * sc["int"]
            + _f(row.get("Proj Rush Yds")) / sc["rush_yds_per_pt"] + _f(row.get("Proj Rush TD")) * sc["rush_td"])


def _active(row): return str(row.get("Weekly Active", "YES")).strip().upper() == "YES"      # an inactive player projects to zero whatever his averages say


def fp_rb(row, sc):
    if not _active(row): return 0.0
    return (_f(row.get("Proj Rush Yds")) / sc["rush_yds_per_pt"] + _f(row.get("Proj Rush TD")) * sc["rush_td"] + _f(row.get("Proj Rec Yds")) / sc["rec_yds_per_pt"]
            + _f(row.get("Proj Rec TD")) * sc["rec_td"] + _f(row.get("Projected Receptions (Audit)")) * sc["rec"])


def fp_wr(row, sc):
    if not _active(row): return 0.0
    return _f(row.get("Proj Rec Yds")) / sc["rec_yds_per_pt"] + _f(row.get("Proj Rec TD")) * sc["rec_td"] + _f(row.get("Projected Receptions (Audit)")) * sc["rec"]


# tab -> (column, function, claimed).  claimed = parity.py fails the run if it ever stops matching.  Not claimed = work in progress:
# reported, never trusted.  11/10: RB and WR match on all but 9 and 13 active rows, each a few tenths high - a haircut the sheet applies
# to the reception count that the "(Audit)" column does not carry (first games back is the likely one). Find it in the formula before claiming.
PORTED = {"proj_qb.json": ("Proj Fantasy Pts", fp_qb, True), "proj_rb.json": ("Proj Fantasy Pts", fp_rb, False), "proj_wr.json": ("Proj Fantasy Pts", fp_wr, False)}
