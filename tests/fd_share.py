"""The FanDuel share link on an imported slip (owner 11/25: "Make it so that people can add the fanduel link when they import a slip.
That link we can use directly to fanduel from people's slips on socials. We use how we've currently been building slips using each
legs url as a backup"). Only FanDuel's own share link is accepted and only its code is kept, so a post can never carry a link to
anywhere else. The two small functions are lifted from the generators and run in a bare page; tests/import_batch.py covers the form,
the save and the post.   python3 tests/fd_share.py"""
import asyncio, os, re, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
imp = open(os.path.join(HERE, "slipimport.py"), encoding="utf-8").read(); soc = open(os.path.join(HERE, "social.py"), encoding="utf-8").read()
m1 = re.search(r"  var FDSHARE = .*\n  function fdCode\(v\)\{.*\n", imp); m2 = re.search(r"  function shareUrl\(ls\)\{.*\n.*\n", soc)
check(bool(m1 and m2), "the share-link reader (slipimport.py) and the feed's share link (social.py) are both in the generators")
GOOD = [("https://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu", "awW1ftu"), ("  https://sportsbook.fanduel.com/addToBetslip?shareCode=8EeHUBo  ", "8EeHUBo"),
        ("https://tn.sportsbook.fanduel.com/addToBetslip?shareCode=Ab12Cd34", "Ab12Cd34"), ("https://sportsbook.fanduel.com/addToBetslip?utm_source=share&shareCode=Zz99&x=1", "Zz99")]
BAD = ["", "awW1ftu", "http://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu", "https://sportsbook.fanduel.com.evil.example/addToBetslip?shareCode=awW1ftu",
       "https://evil.example/?u=https://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu", "javascript:alert(1)//sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu",
       "https://sportsbook.fanduel.com/addToBetslip?shareCode=aw\"><script>", "https://sportsbook.fanduel.com/addToBetslip?shareCode=abc", "https://sportsbook.fanduel.com/navigation/nfl?shareCode=awW1ftu",
       "https://sportsbook.fanduel.com/addToBetslip?marketId[0]=42.1&selectionId[0]=5", "https://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu#x", "https://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu extra"]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.evaluate("(src) => { window.T = new Function(src + '; return {fdCode: fdCode, shareUrl: shareUrl, base: FDSHARE};')(); }", (m1.group(0) if m1 else "") + (m2.group(0) if m2 else ""))
        got = await pg.evaluate("(a) => a.map(function(x){ return window.T.fdCode(x); })", [g[0] for g in GOOD])
        check(got == [g[1] for g in GOOD], f"FanDuel's share link gives its code, with spaces, a state address or other parameters around it ({got})")
        bad = await pg.evaluate("(a) => a.map(function(x){ return window.T.fdCode(x); })", BAD)
        check(all(x is None for x in bad), f"anything else is refused: a bare code, http, a look-alike host, a redirect, script, a short code, another FanDuel page ({[BAD[i][:40] for i, x in enumerate(bad) if x is not None]})")
        check(await pg.evaluate("window.T.base") == "https://sportsbook.fanduel.com/addToBetslip?shareCode=", "the saved link is rebuilt on FanDuel's betslip address")
        r = await pg.evaluate("""() => { var f = Date.now() + 36e5, p = Date.now() - 36e5, S = window.T.shareUrl;
          return {ok: S([{sc: 'awW1ftu', ko: f}, {ko: f}]), started: S([{sc: 'awW1ftu', ko: f}, {ko: p}]), none: S([{ko: f}]), bad: S([{sc: 'aw"><b>', ko: f}]), url: S([{sc: 'https://evil.example', ko: f}]), second: S([{ko: f}, {sc: 'awW1ftu', ko: f}]), empty: S([])}; }""")
        check(r["ok"] == "https://sportsbook.fanduel.com/addToBetslip?shareCode=awW1ftu", f"a post with a share code opens that slip on FanDuel ({r['ok']})")
        check(r["started"] is None, "once any leg has kicked off the share link steps aside for the leg-by-leg link")
        check(r["none"] is None and r["bad"] is None and r["url"] is None and r["second"] is None and r["empty"] is None, f"no code, a code with markup in it or a whole address in its place gives no share link ({r})")
        await b.close()
    check("surl = over || old ? null : shareUrl(ls), url = over || old ? null : (surl || fdUrl(ls))" in soc, "the Social card uses the share link first and the leg-by-leg link as the backup")
    check("fd: shareUrl(ls) || fdUrl(ls)" in soc and "if(SRC && SRC.sc && legs.length) legs[0].sc = SRC.sc;" in soc and "sc: whole ? c.s.sc : null" in soc, "a saved slip carries its code to the post only when the whole slip is posted; Save slip on a card keeps the same link")
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
