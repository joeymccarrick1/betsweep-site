"""Sheet mirror for the BetSweep rebuild (owner 11/3: "the rebuild is expensive for what changes").

Every Claude rebuild re-read ~40 ranges of the model sheet through the Sheets connector (three calls, tens of thousands of rows) before
building anything. This workflow does that read on GitHub's runner with a service account and pushes the same in/*.json files the
runbook's prep.py would write - plus the nflverse schedule - to the orphan branch `sheet-mirror`. The runbook's Step 2 then clones that
branch and skips the connector reads when the mirror is fresh (stamp under 25 minutes old).

Setup (owner, once): Google Cloud console -> create a service account (any project) -> keys -> JSON; share the sheet
"Fantasy Projection Model 2026" with the service account's email as Viewer; add the JSON as the repository secret SHEETS_SA_JSON.
Until the secret exists the workflow exits quietly and the runbook keeps reading through the connector.

Files written (same names and shapes as gen/prep.py): in/<name>.json = {"values": [[...], ...]} per range (formatted values),
in/games.csv, and in/MIRROR.json = {"pulled": ISO UTC, "ranges": N, "rows": {name: rows}}.
"""
import json, os, sys, time, base64, subprocess, urllib.request, urllib.parse

SHEET = "1Tmt5vp--RhvErt6ZGm6vIje7hcrf-aFXovpRrUjENI8"
RANGES = [("AUTO - QB Projections", "A1:AS300"), ("AUTO - RB Projections", "A1:BD300"), ("AUTO - WR Projections", "A1:AV300"), ("AUTO - TE Projections", "A1:AR250"),
          ("V2 - Leg Board", "A4:R1604"), ("AUTO - First TD Odds", "A1:L1200"), ("AUTO - FanDuel Links", "A1:J6000"), ("AUTO - FanDuel Game Lines", "A1:K8000"),
          ("2026 Matchup Boards", "A1:Q560"), ("AUTO - Defensive Stat Matchup Ranks", "A1:P68"), ("AUTO - Game Weather", "A3:P40"), ("AUTO - Weekly Availability", "A1:M300"),
          ("V2 - Game Scripts", "A4:K20"), ("V2 - Best Legs", "A6:K60"), ("AUTO - Script Multipliers", "A1:H23"), ("AUTO - Boards Archive", "A1:F60"),
          ("V2 - Boards Results Feed", "A1:AG1200"), ("V2 - Boards Results Feed", "AJ1:BK3000"), ("V2 - Weekly Scorecard", "A1:K200"), ("V2 - FanDuel Leg Snapshots", "A1:AB20000"),
          ("AUTO - SGP Correlations", "A1:C80"), ("AUTO - Game Day Status", "A1:F200"), ("AUTO - Player Game Log", "A1:X6000"), ("AUTO - Kicker Projections", "A1:P100"),
          ("AUTO - DST Projections", "A1:M50"), ("V1 - Eligible Fantasy Projections", "A1:I650"), ("AUTO - Snap Trends", "A1:J700"), ("V2 - First TD Board", "A3:P700"),
          ("AUTO - Settings", "A1:B300"), ("AUTO - Model Calls Archive", "A1:AQ2000"), ("PROMO - Promoted Bets", "A1:N100"), ("AUTO - Book Odds", "A1:L15000"),
          ("AUTO - Market Values", "A1:J1000"), ("AUTO - WR CB Matchups", "A1:AT600"), ("AUTO - FanDuel Unders", "A1:L1500"), ("V2 - Model Best Picks", "A1:O20000"),
          ("V2 - Closing Lines", "A1:J20000"), ("AUTO - Market Team Points", "A1:Z33"), ("AUTO - Confidence Archive", "A1:R3000"), ("AUTO - DK Salaries", "A1:L1500")]
BY_TITLE = {"2026 Matchup Boards": "boards.json", "AUTO - Defensive Stat Matchup Ranks": "ranks.json", "AUTO - Game Weather": "weather.json",
            "AUTO - Weekly Availability": "avail.json", "V2 - Game Scripts": "scripts.json", "V2 - Leg Board": "legboard.json", "V2 - Best Legs": "bestlegs.json", "AUTO - Script Multipliers": "mult.json", "AUTO - Boards Archive": "archive.json", "V2 - Boards Results Feed": "results.json", "V2 - Weekly Scorecard": "scorecard.json", "V2 - FanDuel Leg Snapshots": "legsnaps.json", "AUTO - SGP Correlations": "corr.json", "AUTO - Game Day Status": "gameday.json", "AUTO - FanDuel Links": "links.json", "AUTO - FanDuel Game Lines": "gamelines.json", "AUTO - Model Calls Archive": "calls.json", "AUTO - Player Game Log": "gamelog.json", "AUTO - QB Projections": "proj_qb.json", "AUTO - RB Projections": "proj_rb.json", "AUTO - WR Projections": "proj_wr.json", "AUTO - TE Projections": "proj_te.json", "AUTO - Kicker Projections": "proj_k.json", "AUTO - DST Projections": "proj_dst.json", "V1 - Eligible Fantasy Projections": "eligible.json", "AUTO - Snap Trends": "snaps.json", "V2 - First TD Board": "firsttd.json", "AUTO - First TD Odds": "ftdodds.json", "AUTO - Settings": "settings.json", "PROMO - Promoted Bets": "promos.json", "AUTO - Market Values": "market.json", "AUTO - Book Odds": "bookodds.json", "AUTO - WR CB Matchups": "wrcb.json", "AUTO - DK Salaries": "dksal.json", "AUTO - Confidence Archive": "confarc.json", "AUTO - Market Team Points": "teammkt.json", "V2 - Closing Lines": "closing.json", "AUTO - FanDuel Unders": "unders.json", "V2 - Model Best Picks": "bestpicks.json"}

def token(sa):
    """OAuth2 access token for the service account (RS256 JWT, no client library needed)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    now = int(time.time())
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    hdr = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()); clm = b64(json.dumps({"iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/spreadsheets.readonly", "aud": sa["token_uri"], "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = b64(key.sign(hdr + b"." + clm, padding.PKCS1v15(), hashes.SHA256()))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": (hdr + b"." + clm + b"." + sig).decode()}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(sa["token_uri"], data=body)))["access_token"]

def main():
    sa_json = os.environ.get("SHEETS_SA_JSON", "").strip()
    if not sa_json: print("SHEETS_SA_JSON secret not set - nothing to mirror"); return 0
    sa = json.loads(sa_json); tok = token(sa); os.makedirs("out/in", exist_ok=True)
    rows = {}
    for i in range(0, len(RANGES), 8):   # batchGet, 8 ranges a call
        chunk = RANGES[i:i + 8]
        q = "&".join("ranges=" + urllib.parse.quote(f"'{t}'!{r}", safe="") for t, r in chunk) + "&valueRenderOption=FORMATTED_VALUE&majorDimension=ROWS"
        req = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values:batchGet?{q}", headers={"Authorization": f"Bearer {tok}"})
        res = None
        for attempt in range(4):   # Google answers 5xx / hangs now and then (11/4: one 503 after 18 minutes): short timeout, retry, never fail the branch
            try: res = json.load(urllib.request.urlopen(req, timeout=60)); break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:600]
                print(f"Sheets API HTTP {e.code} on ranges {[t for t, _ in chunk]} (attempt {attempt + 1}): {body[:200]}")
                if e.code == 403 and ("SERVICE_DISABLED" in body or "has not been used in project" in body): print("FIX: enable the Google Sheets API for the service account's project (console.cloud.google.com -> APIs & Services -> Enable APIs -> Google Sheets API)."); return 1
                if e.code == 403: print(f"FIX: share the sheet with the service account email ({sa.get('client_email')}) as Viewer."); return 1
                if e.code < 500 and e.code != 429: return 1
            except Exception as e: print(f"Sheets API error on ranges {[t for t, _ in chunk]} (attempt {attempt + 1}): {e}")
            time.sleep(15 * (attempt + 1))
        if res is None: print("WARN: a chunk never answered - keeping the previous mirror (no MIRROR.json written, nothing pushed)"); return 0
        for (t, r), vr in zip(chunk, res.get("valueRanges", [])):
            name = BY_TITLE[t]
            if t == "V2 - Boards Results Feed" and r.startswith("AJ"): name = "results_legs.json"
            vals = vr.get("values", [])
            json.dump({"values": vals}, open(f"out/in/{name}", "w")); rows[name] = len(vals)
    subprocess.run(["curl", "-sSLf", "-o", "out/in/games.csv", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"], check=True)
    json.dump({"pulled": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ranges": len(RANGES), "rows": rows}, open("out/in/MIRROR.json", "w"), indent=1)
    print("mirrored", len(rows), "ranges:", {k: v for k, v in rows.items()})
    return 0

if __name__ == "__main__": sys.exit(main())
