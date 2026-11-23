"""What the sport switch on a board page must be - worked out here from the site's folders alone, not by calling sport_nav.switch.

Owner 11/23 1:10 AM: "We'd have NFL, College Football, NBA and Soccer (with these different leagues)." So: one row of sports - NFL, CFB,
NBA, Soccer - and, on a soccer page, a second row with the leagues. A page links only to pages that are in the same build.

Not a test itself (it is not in tests/prepublish.sh's list): the NBA, college football and soccer page tests import it, so the three
agree on the rule and none of them can pass by asking the code under test what it meant.

    sports(root, cur)    [[label, href, "page" or None], ...]   cur: "nfl", "cfb", "nba", or a league's folder ("epl", "laliga", ...)
    leagues(root, cur)   the same shape for the league row; [] when the page shows no league row (fewer than two leagues in the build)
"""
import os

SPORTS = (("nfl", "NFL", "/boards/"), ("cfb", "CFB", "/cfb/"), ("nba", "NBA", "/nba/"))
LEAGUES = (("epl", "Premier League", "/epl/"), ("bundesliga", "Bundesliga", "/bundesliga/"), ("laliga", "La Liga", "/laliga/"), ("seriea", "Serie A", "/seriea/"), ("mls", "MLS", "/mls/"))
LEAGUE_KEYS = tuple(k for k, _, _ in LEAGUES)


def there(root, have):
    if have is not None:
        return lambda k: bool(have.get(k))
    return lambda k: os.path.exists(os.path.join(root, k, "index.html"))


def sports(root, cur, have=None):
    t = there(root, have)
    out = [[lab, href, "page" if k == cur else None] for k, lab, href in SPORTS if k in ("nfl", cur) or t(k)]
    lg = [k for k in LEAGUE_KEYS if k == cur or t(k)]
    if lg:                                                  # Soccer is one sport: from another sport's page it goes to the first league that has a page
        here = cur in LEAGUE_KEYS
        out.append(["Soccer", dict((k, h) for k, _, h in LEAGUES)[cur if here else lg[0]], "page" if here else None])
    return out


def leagues(root, cur, have=None):
    t = there(root, have)
    lg = [[lab, href, "page" if k == cur else None] for k, lab, href in LEAGUES if k == cur or t(k)]
    return lg if len(lg) > 1 else []
