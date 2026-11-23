"""The NBA's five positions - PG, SG, SF, PF, C - for the pages.

Owner 11/23 7:37 AM: "For nba we can have all 5 standard positions SG, PG, PF, SF, C."

ESPN's box scores and rosters list only G, F or C this season (checked 11/23: 225 guards, 189 forwards, 76 centers, nothing else).
Its depth charts do name the five: for each team, who plays PG, SG, SF, PF and C, first choice first. The feeds-sports job mirrors
them as nba/depth.json = {"mirrored", "teams": {"LAL": {"PG": [athlete ids, first choice first], "SG": [...], ...}}}.

A player is usually listed at more than one position (a wing at SG, SF and PF). He is given the one where he stands highest; a
tie goes to a position that fits ESPN's own G / F / C for him (a forward tied at SG and SF is an SF), then to PG, SG, SF, PF, C in
that order. A player on no chart has no position here, and the page shows ESPN's G, F or C for him rather than a guess.

For the pages alone: what a visitor reads beside a name and whom a player is ranked among. The model's numbers still use the three
groups it was tested on (minutes and who is out lead in the NBA, not the matchup), and the "allowed to guards / forwards / centers"
ranks stay by group.

Plain Python (no pandas): the hourly site build imports the names from here.
"""
SLOTS = ("PG", "SG", "SF", "PF", "C")
NAMES = {"PG": "Point guard", "SG": "Shooting guard", "SF": "Small forward", "PF": "Power forward", "C": "Center"}
PLURAL = {"PG": "point guards", "SG": "shooting guards", "SF": "small forwards", "PF": "power forwards", "C": "centers"}
FITS = {"G": ("PG", "SG"), "F": ("SF", "PF"), "C": ("C",)}


def _best(chart, pid, grp):
    """(depth, slot) for one player in one team's chart, or None"""
    pid = str(pid); found = []
    for k, slot in enumerate(SLOTS):
        ids = [str(x) for x in (chart or {}).get(slot) or []]
        if pid in ids:
            found.append((ids.index(pid), 0 if slot in FITS.get(grp, ()) else 1, k, slot))
    return (min(found)[0], min(found)[3]) if found else None


def slot(depth, team, pid, grp=None):
    """A player's position from the mirrored depth charts: his own team's chart first; if he is not on it (a trade the charts have not
    caught up with), any team's. None when no chart lists him or there are no charts."""
    teams = (depth or {}).get("teams") or {}
    b = _best(teams.get(team), pid, grp)
    if b: return b[1]
    hits = [x for x in (_best(ch, pid, grp) for t, ch in sorted(teams.items()) if t != team) if x]
    return min(hits)[1] if hits else None


def shown(p):
    """the position a page shows for a player row: one of the five when the board has it, else ESPN's G / F / C"""
    return p.get("pos") or p.get("grp")
