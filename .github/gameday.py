"""Game-day inactives -> the model sheet, with no Claude session (11/5, owner: "weed out inefficiencies").

The "NFL game-day inactives check" scheduled task read five big tabs through the Sheets connector, ran web searches and wrote
'AUTO - Weekly Availability' + 'AUTO - Game Day Status' three times every Sunday - and on 11/2 it died on a usage limit at 6:38 PM.
Everything it needs is already mirrored: .github/feeds.py writes the official inactive lists ESPN posts ~90 minutes before each
kickoff (branch feeds, inactives.json), and .github/sheets_pull.py mirrors the sheet (branch sheet-mirror). This script joins the two
and writes the same rows the task wrote, by the same rules:
  - CONFIRMED OUT only for a player on ESPN's inactive list for a game inside the feeds window (official, dated today) and known to
    the model (a row in the projection tabs, the leg snapshots or the availability tab). No web searches, no guesses.
  - 'AUTO - Weekly Availability': an existing week-W row gets E = OUT, J, K, L (never downgrades an OUT); a player with no row gets
    one appended (A..M, week as a number). Rows 2-300 only - past 300 it stops and says so.
  - 'AUTO - Game Day Status' (rows from 3): one row per player per run [W, player, team, "CONFIRMED OUT", note, time, source]; a
    player already listed CONFIRMED OUT for this week is not written again.
Needs the service account (secret SHEETS_SA_JSON) shared on the sheet as EDITOR (the mirror only needs Viewer). Until then the
Sheets API answers 403 and this prints the one-line fix and exits 0 - the old scheduled task keeps doing the job.
Runs from .github/workflows/gameday.yml at :08 and :38 during the Sunday windows plus Thursday and Monday nights.
"""
import json, os, re, sys, time, base64, subprocess, urllib.request, urllib.parse, datetime as dt, unicodedata

SHEET = "1Tmt5vp--RhvErt6ZGm6vIje7hcrf-aFXovpRrUjENI8"
REPO = "https://github.com/joeymccarrick1/betsweep-site.git"
NOW = dt.datetime.now(dt.timezone.utc)
CT = dt.timezone(dt.timedelta(hours=-6))   # November: CST

def token(sa, scope):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    now = int(time.time()); b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    hdr = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    clm = b64(json.dumps({"iss": sa["client_email"], "scope": scope, "aud": sa["token_uri"], "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = b64(key.sign(hdr + b"." + clm, padding.PKCS1v15(), hashes.SHA256()))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": (hdr + b"." + clm + b"." + sig).decode()}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(sa["token_uri"], data=body)))["access_token"]

def api(tok, method, path, body=None):
    req = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))

def branch_file(branch, path):
    d = f"/tmp/{branch}"
    if not os.path.isdir(d): subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", branch, REPO, d], check=True)
    with open(os.path.join(d, path)) as f: return json.load(f)

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[.'’]", "", s).lower(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s.strip()); return re.sub(r"\s+", " ", s)
ALIAS = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}
def team(t): t = str(t or "").upper(); return ALIAS.get(t, t)

def main():
    sa_json = os.environ.get("SHEETS_SA_JSON", "").strip()
    if not sa_json: print("SHEETS_SA_JSON secret not set - nothing to do"); return 0
    sa = json.loads(sa_json)
    ina = branch_file("feeds", "inactives.json")
    games = ina.get("games") or {}
    outs = [(g["ko"], g["teams"], o) for g in games.values() for o in g.get("out") or []]
    if not outs: print("no inactives posted for any game in the window (", ina.get("mirrored"), ")"); return 0
    # who the model knows: projection tabs + availability + leg snapshots (name -> team, pos)
    known = {}
    for f, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        try:
            v = branch_file("sheet-mirror", "in/" + f)["values"]; h = {c: i for i, c in enumerate(v[0])}
            for r in v[1:]:
                if r and r[0]: known[norm(r[0])] = {"name": r[0], "team": team(r[1] if len(r) > 1 else ""), "pos": pos}
        except Exception as e: print("mirror read failed", f, e)
    settings = branch_file("sheet-mirror", "in/settings.json")["values"]
    try: W = int(float(settings[1][1]))   # 'AUTO - Settings'!B2 ("Projection Week")
    except Exception: print("could not read the week from the settings mirror"); return 1
    avail = branch_file("sheet-mirror", "in/avail.json")["values"]
    hdr = avail[0]; rows = avail[1:]
    have = {}   # norm name -> (sheet row number, row)
    for i, r in enumerate(rows, start=2):
        if r and str(r[0]).strip() and int(float(r[0])) == W and len(r) > 1: have[norm(r[1])] = (i, r)
    try: gds = branch_file("sheet-mirror", "in/gameday.json")["values"]
    except Exception: gds = []
    already = {norm(r[1]) for r in gds[2:] if len(r) > 3 and str(r[0]).strip() and int(float(r[0])) == W and str(r[3]).strip().upper() == "CONFIRMED OUT"}
    stamp = NOW.astimezone(CT).strftime("%Y-%m-%d %H:%M"); today = NOW.astimezone(CT).strftime("%Y-%m-%d")
    updates, appends, status_rows, skipped = [], [], [], []
    seen = set()
    for ko, teams, o in outs:
        n = norm(o.get("name")); k = known.get(n)
        if not k or n in seen:
            if not k: skipped.append(o.get("name"))
            continue
        seen.add(n)
        tm = team(o.get("team")) or k["team"]
        note = f"Inactive - game-day scratch (ESPN inactives, {stamp} CT)"; src = "ESPN game summary (official inactives)"
        if n in have:
            rown, r = have[n]
            if str(r[4] if len(r) > 4 else "").strip().upper() != "OUT":
                updates.append({"range": f"'AUTO - Weekly Availability'!E{rown}", "values": [["OUT"]]})
                updates.append({"range": f"'AUTO - Weekly Availability'!J{rown}:L{rown}", "values": [[note, src, today]]})
        else:
            appends.append([W, k["name"], tm, k["pos"], "OUT", "", "", "", "", note, src, today, ""])
        if n not in already: status_rows.append([W, k["name"], tm, "CONFIRMED OUT", note, stamp, src])
    print(f"week {W}: {len(outs)} official outs in the window, {len(seen)} model players; updates {len(updates) // 2}, new rows {len(appends)}, status rows {len(status_rows)}; not model players: {len(skipped)}")
    if not (updates or appends or status_rows): return 0
    try: tok = token(sa, "https://www.googleapis.com/auth/spreadsheets")
    except Exception as e: print("token failed:", e); return 1
    try:
        if updates: api(tok, "POST", "values:batchUpdate", {"valueInputOption": "USER_ENTERED", "data": updates})
        if appends:
            first = 2 + len(rows)
            if first + len(appends) - 1 > 300: print(f"STOP: Weekly Availability would pass row 300 (next row {first}); nothing appended"); appends = []
            else:
                rng = urllib.parse.quote("'AUTO - Weekly Availability'!A%d:M%d" % (first, first + len(appends) - 1))
                api(tok, "PUT", "values/" + rng + "?valueInputOption=USER_ENTERED", {"values": appends})
        if status_rows:
            rng = urllib.parse.quote("'AUTO - Game Day Status'!A3:G3")
            api(tok, "POST", "values/" + rng + ":append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS", {"values": status_rows})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code == 403: print(f"FIX: share the sheet with {sa.get('client_email')} as EDITOR (the mirror only has Viewer). Nothing written; the scheduled inactives check still covers this. {body[:120]}"); return 0
        print("Sheets API", e.code, body); return 1
    # read back
    chk = api(tok, "GET", "values/" + urllib.parse.quote("'AUTO - Game Day Status'!A1:G400"))
    n = sum(1 for r in chk.get("values", [])[2:] if len(r) > 3 and str(r[0]).strip() and int(float(r[0])) == W and r[3] == "CONFIRMED OUT")
    print(f"wrote: {len(updates) // 2} availability updates, {len(appends)} new availability rows, {len(status_rows)} status rows; Game Day Status now lists {n} confirmed outs for week {W}")
    for r in status_rows: print("  OUT", r[1], r[2])
    return 0

if __name__ == "__main__": sys.exit(main())
