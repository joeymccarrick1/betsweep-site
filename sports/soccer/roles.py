"""A soccer player's specific position, read from where ESPN draws him in his side's eleven.

Owner 11/23 7:37 AM: "Can we get more specific with positions in nba and soccer? I want forward/striker, Right wing/Right mid,
center mid/center attacking mid, right back, ect."

ESPN names eleven places a side: "G", "CD-L", "LB", "LM", "AM-R", "CF-L", "F" ... The same code means different jobs in different
shapes, so a place is read together with the other ten. Checked 11/23 against the 1,710 elevens of the Bundesliga, La Liga, Serie A and
MLS seasons (18 distinct shapes; the six commonest are 92% of them) and against players whose job is not in doubt:

    4-2-3-1   LM RM = the two holding midfielders (Tchouameni, Kimmich)      AM-L AM-R = the wings (Vinicius, Olise)   AM = the ten
    4-3-3     LM RM = the outer two of a midfield three (Pedri, McTominay)   LF RF = the wings (Yamal, Bouanga)
    3-4-3     LM RM = wing-backs (Dimarco)                                   CF-L CF-R beside a central F = the wings
    3-5-2     LM RM = wing-backs                                             CF-L CF-R with no central F = two strikers (Lautaro)
    4-4-2     LM RM = wide midfielders                                       CF-L CF-R = two strikers
    a back five (three centre-backs plus LB RB): LB RB = wing-backs, LM RM = wide midfielders

So LM / RM are read by how many other central midfielders the side has: none -> the holding pair, one -> a midfield three, two or more ->
out wide (wing-backs when three centre-backs play and nobody is at full-back).

    role(place, eleven)   one starter's role
    usual(roles)          a player's usual role, from his starts oldest first
    GROUP[role]           the four groups the model's priors and the grader use (unchanged by any of this)

The role is for the page: what a visitor reads beside a name, and whom a player is ranked among. No model number depends on it.
"""
import collections
import re
import unicodedata

ROLES = ("GK", "CB", "LB", "RB", "LWB", "RWB", "CDM", "CM", "LM", "RM", "CAM", "LW", "RW", "ST")
NAMES = {"GK": "Goalkeeper", "CB": "Center back", "LB": "Left back", "RB": "Right back", "LWB": "Left wing-back", "RWB": "Right wing-back",
         "CDM": "Defensive midfielder", "CM": "Center midfielder", "LM": "Left midfielder", "RM": "Right midfielder", "CAM": "Attacking midfielder",
         "LW": "Left wing", "RW": "Right wing", "ST": "Striker", "SUB": "Substitute: no start on file this season, so no position to go on"}
GROUP = {"GK": "GK", "CB": "DEF", "LB": "DEF", "RB": "DEF", "LWB": "DEF", "RWB": "DEF", "CDM": "MID", "CM": "MID", "LM": "MID", "RM": "MID", "CAM": "MID",
         "LW": "FWD", "RW": "FWD", "ST": "FWD"}
CENTRAL = ("CM", "CM-L", "CM-R", "DM", "SW", "M")          # ESPN's "SW" is a holding midfielder in the shapes it appears in (Sano, Mandragora, Zielinski)
USUAL_OVER = 10                                            # a player's usual role is read from his last ten starts


def role(place, eleven):
    """ESPN's place for one starter, and the places of his side's whole eleven -> his role, or None when the place is not one this reads"""
    c = str(place or "").upper().strip()
    S = [str(x or "").upper().strip() for x in (eleven or [])]
    three = "CD" in S and ("CD-L" in S or "CD-R" in S)                      # three centre-backs
    if c in ("G", "GK"): return "GK"
    if c in ("CD", "CD-L", "CD-R"): return "CB"
    if c in ("LB", "RB"): return ("LWB" if c == "LB" else "RWB") if three else c
    if c in ("LWB", "RWB"): return c
    if c in ("DM", "SW"): return "CDM"
    if c in ("CM", "CM-L", "CM-R", "M"): return "CM"
    if c == "AM": return "CAM"
    if c in ("AM-L", "AM-R"):                                               # beside a central ten they are the wings; a pair on their own are two tens
        return ("LW" if c == "AM-L" else "RW") if "AM" in S else "CAM"
    if c in ("LF", "LW"): return "LW"
    if c in ("RF", "RW"): return "RW"
    if c in ("F", "CF", "ST", "RCF", "LCF"): return "ST"
    if c in ("CF-L", "CF-R"):
        return ("LW" if c == "CF-L" else "RW") if "F" in S else "ST"
    if c in ("LM", "RM"):
        central = sum(1 for x in S if x in CENTRAL)
        if central == 0: return "CDM"
        if central == 1: return "CM"
        if three and "LB" not in S and "RB" not in S: return "LWB" if c == "LM" else "RWB"
        return c
    return None


def usual(roles):
    """a player's usual role from the roles of his starts, oldest first: the one he has started most in his last ten; a tie goes to the
    one he started in more recently. None when he has no start to go on."""
    r = [x for x in (roles or []) if x][-USUAL_OVER:]
    if not r: return None
    n = collections.Counter(r)
    best = max(n.values())
    for x in reversed(r):
        if n[x] == best: return x


def starts(matches):
    """{player id: [role of each start, oldest first]} from a season file's matches ({id: {"d", "p": [[team, player, name, place, started, ...]]}}),
    and {player id: (name, team id of his latest start)}"""
    out, who = collections.defaultdict(list), {}
    for mid, m in sorted(matches.items(), key=lambda kv: str(kv[1].get("d") or "")):
        by = collections.defaultdict(list)
        for ln in m.get("p") or []:
            if ln[4]: by[str(ln[0])].append(ln)
        for tid, L in by.items():
            eleven = [x[3] for x in L]
            for x in L:
                r = role(x[3], eleven)
                if r: out[str(x[1])].append(r); who[str(x[1])] = (x[2], tid)
    return dict(out), who


# ---- finding the same player under two spellings (the Premier League's numbers come from a data set that names players its own way)
LETTERS = {"ß": "ss", "ø": "o", "đ": "d", "ð": "d", "ł": "l", "ı": "i", "æ": "ae", "œ": "oe", "þ": "th"}      # letters NFKD leaves as they are


def fold(name):
    """a name for matching: lower case, no accents, no punctuation - 'Pascal Groß' and 'Pascal Gross' are one man"""
    x = "".join(LETTERS.get(ch, ch) for ch in str(name or "").lower())
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", x.replace("-", " "))).strip()


def find(names, club):
    """One player among a club's ESPN names ({folded name: anything}); `names` are the spellings on hand, fullest first. In order: the
    same name; the same name with the spaces closed ('Da Silva', 'Dasilva'); every word of one inside the other, when only one man at
    the club fits ('Abdul Fatawu' in 'Abdul Fatawu Issahaku'); the same surname, when only one man at the club has it. Returns the
    club's key or None - a player it cannot place is left without a role rather than given a neighbour's. (Then a one-word name that
    is a word of one man's name only: 'Fatawu' for 'Fatawu Issahaku'.)"""
    mine = [fold(n) for n in names if fold(n)]
    for n in mine:
        if n in club: return n
    tight = {k.replace(" ", ""): k for k in club}
    for n in mine:
        if n.replace(" ", "") in tight: return tight[n.replace(" ", "")]
    for n in mine:
        w = set(n.split())
        c = [k for k in club if w <= set(k.split()) or set(k.split()) <= w]
        if len(w) >= 2 and len(c) == 1: return c[0]
    for n in mine:                                         # the surname of any spelling ('Andrés' for 'Chema Andrés'), when one man has it
        last = n.split(" ")[-1]
        c = [k for k in club if k.split(" ")[-1] == last]
        if len(last) > 3 and len(c) == 1: return c[0]
    for n in mine:                                         # a one-word name ('Fatawu') that is a word of one man's name only
        if " " not in n and len(n) > 3:
            c = [k for k in club if n in k.split(" ")]
            if len(c) == 1: return c[0]
    return None
