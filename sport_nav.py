"""Which sports have a page in this build, and the switch every board page carries.

Owner 11/23 1:10 AM: "We'd have NFL, College Football, NBA and Soccer (with these different leagues)." Each sport's page links to the
others, but only to pages that are going out in the same build: a preview page is not written when its board is missing or stale, and a
link to it would be a dead one. So the question is asked of each builder's own rule (its usable()), on the same feed branch they read.
"""
import html

ORDER = (("nfl", "NFL", "/boards/"), ("cfb", "CFB", "/cfb/"), ("nba", "NBA", "/nba/"), ("epl", "EPL", "/epl/"))
BOARDS = {"nba": ("build_nba", "nba/board.json"), "epl": ("build_epl", "epl/board.json"), "cfb": ("build_cfb", "cfb/board.json")}


def available(clone=None, only=None):
    """{sport: True} for the preview pages this build will draw. only: a list given by hand, for local work and tests."""
    if only is not None:
        return {k: True for k in only if k in BOARDS}
    import build_nba as N
    out = {}
    try:
        if N.usable(N.load(clone=clone))[0]:          # N.load fetches the branch; the two reads below use what it fetched
            out["nba"] = True
    except Exception:
        pass
    for key in ("epl", "cfb"):
        mod, name = BOARDS[key]
        try:
            if __import__(mod).usable(N.feed_file(clone, name))[0]:
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
    """for a page built by hand from a board file: the sports named on the command line, plus any whose page already sits in out/"""
    import os
    have = available(only=named(argv))
    for key in BOARDS:
        if os.path.exists(os.path.join(out_dir, f"{key}-boards.html")):
            have[key] = True
    return have


def switch(cur, have):
    """the row of sport pills: the NFL always, this page's own sport, and every other sport with a page in this build"""
    return ('<div class="nbsw" role="group" aria-label="Sport">'
            + "".join(f'<a href="{href}"' + (' aria-current="page"' if key == cur else "") + f'>{html.escape(label)}</a>' for key, label, href in ORDER if key in ("nfl", cur) or have.get(key))
            + '</div>')
