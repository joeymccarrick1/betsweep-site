"""Which sports have a page in this build, and the switch every board page carries.

Owner 11/23 1:10 AM: "We'd have NFL, College Football, NBA and Soccer (with these different leagues)." Each sport's page links to the
others, but only to pages that are going out in the same build: a preview page is not written when its board is missing or stale, and a
link to it would be a dead one. So the question is asked of each builder's own rule (its usable()), on the same feed branch they read.
"""
import html

SOCCER = (("epl", "Premier League", "/epl/", "epl"), ("bundesliga", "Bundesliga", "/bundesliga/", "bun"), ("laliga", "La Liga", "/laliga/", "lal"),
          ("seriea", "Serie A", "/seriea/", "sea"), ("mls", "MLS", "/mls/", "mls"))            # site folder, name, address, folder on the feed branch
LEAGUE = {k: {"key": k, "name": n, "path": h, "feed": f} for k, n, h, f in SOCCER}
ORDER = (("nfl", "NFL", "/boards/"), ("cfb", "CFB", "/cfb/"), ("nba", "NBA", "/nba/"), ("soccer", "Soccer", "/epl/"))
BOARDS = {"nba": ("build_nba", "nba/board.json"), "cfb": ("build_cfb", "cfb/board.json")}
PAGES = ("nba", "cfb") + tuple(k for k, _, _, _ in SOCCER)          # every preview page there can be, by its site folder


def available(clone=None, only=None):
    """{page: True} for the preview pages this build will draw (keys: nba, cfb, and each soccer league's site folder).
    only: a list given by hand, for local work and tests."""
    if only is not None:
        return {k: True for k in only if k in PAGES}
    import build_nba as N
    out = {}
    try:
        if N.usable(N.load(clone=clone))[0]:          # N.load fetches the branch; the reads below use what it fetched
            out["nba"] = True
    except Exception:
        pass
    try:
        if __import__("build_cfb").usable(N.feed_file(clone, "cfb/board.json"))[0]:
            out["cfb"] = True
    except Exception:
        pass
    try:
        K = __import__("build_epl")
        for key, _, _, feed in SOCCER:
            if K.usable(N.feed_file(clone, f"{feed}/board.json"), sport=feed)[0]:
                out[key] = True
    except Exception:
        pass
    return out


def named(argv):
    """--with nba,epl,cfb on a local command line -> the list; the older --nba flag still counts"""
    only = []
    if "--with" in argv:
        only = [x for x in argv[argv.index("--with") + 1].split(",") if x]
    if "--nba" in argv and "nba" not in only:
        only.append("nba")
    return only


def local(argv, out_dir):
    """for a page built by hand from a board file: the pages named on the command line, plus any whose page already sits in out/"""
    import os
    have = available(only=named(argv))
    for key in PAGES:
        if os.path.exists(os.path.join(out_dir, f"{key}-boards.html")):
            have[key] = True
    return have


def switch(cur, have):
    """the row of sport pills - NFL | CFB | NBA | Soccer: the NFL always, this page's own sport, and every other sport with a page in this
    build. Soccer is one sport: its pill goes to the first league that has a page (the Premier League when it is there)."""
    have = dict(have or {})
    if cur in LEAGUE: have[cur] = True
    first = next((LEAGUE[k]["path"] for k, _, _, _ in SOCCER if have.get(k)), None)
    here = "soccer" if cur in LEAGUE else cur
    out = []
    for key, label, href in ORDER:
        if key == "soccer":
            if not first: continue
            href = LEAGUE[cur]["path"] if cur in LEAGUE else first
        elif key not in ("nfl", here) and not have.get(key):
            continue
        out.append(f'<a href="{href}"' + (' aria-current="page"' if key == here else "") + f'>{html.escape(label)}</a>')
    return '<div class="nbsw" role="group" aria-label="Sport">' + "".join(out) + '</div>'


def leagues(cur, have):
    """the row of league pills on a soccer page; nothing when this is the only league with a page"""
    have = dict(have or {}); have[cur] = True
    ks = [k for k, _, _, _ in SOCCER if have.get(k)]
    if len(ks) < 2: return ""
    return ('<div class="nbsw nblg" role="group" aria-label="League">'
            + "".join(f'<a href="{LEAGUE[k]["path"]}"' + (' aria-current="page"' if k == cur else "") + f'>{html.escape(LEAGUE[k]["name"])}</a>' for k in ks) + '</div>')
