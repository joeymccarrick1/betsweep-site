"""FanDuel prices typed into the builder -> out/in/fd_quotes.json in the sheet mirror (owner 11/25).

The builder sends a signed-in reader's typed FanDuel price for a same-game slip to the database (fd_quote_add). The weekly fit of
FanDuel's same-game discount (generators: research/sgp_discount.py) reads the sheet mirror, so this step asks the database for the rows
(fd_quotes_dump, which needs the cron secret the grading job already holds as FEED_GRADE_SECRET) and writes them beside the sheet pull.

It can never fail the job and never prints the secret or a row: no secret, no database function yet, or any error = one line and no file.
The database's address and public key are read from this repo's own published index.html (they are on every page).
"""
import json, os, re, sys, urllib.request


def main():
    secret = (os.environ.get("FEED_GRADE_SECRET") or "").strip()
    if not secret:
        print("fd quotes: FEED_GRADE_SECRET is not set in this run - skipped"); return
    try: html = open("index.html", encoding="utf-8").read()
    except Exception: html = ""
    m = re.search(r'url:"(https://[a-z0-9]+\.supabase\.co)",key:"([A-Za-z0-9_.\-]{40,})"', html)
    if not m:
        print("fd quotes: the database address was not found on index.html - skipped"); return
    url, key = m.group(1), m.group(2)
    try:
        req = urllib.request.Request(url + "/rest/v1/rpc/fd_quotes_dump", data=json.dumps({"p_secret": secret}).encode(), method="POST",
                                     headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        rows = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"fd quotes: the database answered {e.code} (function not installed yet, or the secret does not match) - no file written"); return
    except Exception as e:
        print(f"fd quotes: could not be read ({type(e).__name__}) - no file written"); return
    if not isinstance(rows, list):
        print("fd quotes: unexpected answer - no file written"); return
    os.makedirs("out/in", exist_ok=True)
    json.dump({"quotes": rows}, open("out/in/fd_quotes.json", "w"))
    print(f"fd quotes: {len(rows)} row(s) written to in/fd_quotes.json")


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"fd quotes: failed ({type(e).__name__}) - the mirror is unaffected")
    sys.exit(0)
