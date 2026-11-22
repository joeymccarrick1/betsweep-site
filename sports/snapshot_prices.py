"""DRAFT - not scheduled, not run against the live API from this branch.

Saves FanDuel's prices for a sport's upcoming games so the model's legs can be frozen before they start and graded afterwards -
the NFL build's 'V2 - FanDuel Leg Snapshots' for NBA and EPL. Until prices are being saved, nothing can be graded against the book.

  ODDS_API_KEY=... python -m sports.snapshot_prices nba --hours 14 --out prices/        (add --dry-run to list the games only: free)

Cost: one credit per market that comes back, per game (see core/oddsapi.py). NBA at 10 markets, about 7 games a day, 3 pulls a day is
about 6,300 credits a month; EPL at 6 markets, 10 matches a week, 3 pulls is about 800. The NFL pulls already use about 17,400 of the
20,000 on the current plan, so this needs the 100,000-credit plan before it is switched on.
"""
import argparse, csv, datetime as dt, os, sys
from .core import oddsapi as OA

MAPS = {"nba": OA.NBA, "epl": OA.EPL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sport", choices=sorted(MAPS))
    ap.add_argument("--hours", type=float, default=14.0, help="only games starting within this many hours")
    ap.add_argument("--out", default="prices")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        sys.exit("ODDS_API_KEY is not set")
    now = dt.datetime.now(dt.timezone.utc)
    events = [e for e in OA.fetch_events(a.sport, key)
              if now < dt.datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) < now + dt.timedelta(hours=a.hours)]
    print(f"{len(events)} {a.sport} games start within {a.hours:g} hours; about {len(events) * len(MAPS[a.sport])} credits to price them")
    if a.dry_run or not events:
        return
    rows, left = [], None
    for e in events:
        js, left = OA.fetch_event_odds(a.sport, e["id"], list(MAPS[a.sport]), key)
        rows += OA.parse_event(js, MAPS[a.sport])
    os.makedirs(a.out, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H%MZ")
    f = os.path.join(a.out, f"{a.sport}_{stamp}.csv")
    with open(f, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["frozen_at"] + (list(rows[0]) if rows else []))
        w.writeheader()
        for r in rows:
            w.writerow(dict(r, frozen_at=stamp))
    print(f"wrote {len(rows)} price rows to {f}; credits left: {left}")


if __name__ == "__main__":
    main()
