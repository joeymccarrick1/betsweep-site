"""The leg board contract. Every sport writes its priced legs in the same columns the NFL sheet's 'V2 - Leg Board' already uses, so the
boards, the Parlay Builder, Live and the promo desk can read a new sport without a new format."""
import re
import unicodedata
from . import odds as O

HEADER = ["Player", "Market", "Alt line (X+)", "FanDuel odds", "Team", "Opp", "Status", "Model proj", "Season avg", "Games",
          "Model hit % (history-adjusted)", "Fair odds", "Book implied %", "Edge", "Verdict", "Warnings", "Game", "Kickoff (CT)"]
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")


def norm_name(name):
    """Same job as normName in FanDuelOdds.gs: one spelling of a player for joining the model to the book."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = _SUFFIX.sub("", s.replace(".", "").replace("'", "").replace("-", " "))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s)).strip()


def leg_key(player, market, line):
    return f"{norm_name(player)}|{market}|{int(line)}"


def row(player, market, line, team, opp, proj, season_avg, games, raw_p, game, kickoff, fd_odds=None, status="ACTIVE", warnings="", w_model=0.5):
    """One board row. Without a FanDuel price the row carries the model's chance and fair odds only; nothing is called value
    until there is a price to compare with (the verdict labels stay the sheet's, applied there)."""
    book = O.implied(fd_odds) if fd_odds not in (None, "") else None
    shown = O.blend(raw_p, book, w_model)
    edge = O.edge(shown, book)
    fair = O.american(shown)
    return [player, market, line, "" if fd_odds in (None, "") else int(fd_odds), team, opp, status, round(float(proj), 2),
            "" if season_avg is None else round(float(season_avg), 2), int(games), round(float(shown), 4), "" if fair is None else (f"+{fair}" if fair > 0 else str(fair)),
            "" if book is None else round(book, 4), "" if edge is None else round(edge, 4), "", warnings, game, kickoff]
