#!/usr/bin/env bash
# Replace the SITE repository's saved history with one snapshot of the site exactly as it stands, after putting the whole old
# history somewhere safe. Owner 11/23: "do what you think is best to get the storage down without affecting the day to day user
# experience" and, on the backup, "Archive ready". Read RUNBOOK.md, "the site repository's size", before running this.
# It changes no file of the live site: the snapshot's tree is the old tip's tree.
#
#   tools/snapshot_site_history.sh MIRROR SITE_URL ARCHIVE_URL          # everything up to the swap, then stops and says what it would push
#   tools/snapshot_site_history.sh MIRROR SITE_URL ARCHIVE_URL --go     # ... and makes the swap
#
#   MIRROR       a bare clone of the site repository that holds main's whole history (git clone --mirror SITE_URL), kept after the run
#   SITE_URL     the site repository
#   ARCHIVE_URL  the PRIVATE repository that keeps the old history (betsweep-site-archive)
#   SNAPSHOT_DAY (environment, optional) the day in the archive branch's name; today (UTC) when not given
#
# The archive's layout matters. The site's main carries its scheduled jobs, and GitHub runs a scheduled job from a repository's DEFAULT
# branch. So the archive's default branch (main) holds a note and nothing else, and the old history goes on archive/<day>/main, where
# no job can start. This script refuses to go on if the archive's default branch is anything else or has a .github folder.
#
# What it guarantees, each checked before the next step:
#   1. the mirror holds main as it is on the site right now, and is sound (fsck);
#   2. the archive holds the very commit about to be replaced - or nothing is replaced;
#   3. the snapshot commit's tree is the old tip's tree, object for object: every file of the site identical;
#   4. the swap goes through only if main is still at the commit read in step 1 (a job that pushed in between makes it stop;
#      run it again). A job caught between its checkout and its push is fine: its "git pull --rebase" lands its commit on the
#      snapshot (rehearsed 11/23 on a local copy).
# It deletes nothing itself: the old history stays in the mirror and in the archive; GitHub drops its own copy later, on its own schedule.
set -euo pipefail
MIRROR=${1:?mirror}; SITE=${2:?site url}; ARCHIVE=${3:?archive url}; GO=${4:-}
DAY=${SNAPSHOT_DAY:-$(date -u +%F)}; AREF=refs/heads/archive/$DAY/main
stop() { echo "STOP: $*"; exit 1; }
cd "$MIRROR"
[ "$(git rev-parse --is-bare-repository)" = "true" ] || stop "$MIRROR is not a bare repository"

echo "1. bringing the mirror up to date and checking it"
git fetch -q "$SITE" '+refs/heads/main:refs/heads/main'
OLD=$(git rev-parse refs/heads/main); TREE=$(git rev-parse "$OLD^{tree}")
[ "$(git ls-remote "$SITE" refs/heads/main | cut -f1)" = "$OLD" ] || stop "main moved while fetching; run again"
git fsck --connectivity-only --no-dangling > /dev/null
echo "   main is $OLD ($(git rev-list --count "$OLD") commits), tree $TREE"

echo "2. the archive ($AREF)"
[ "$(git ls-remote --symref "$ARCHIVE" HEAD | awk '/^ref:/{print $2}')" = "refs/heads/main" ] || stop "the archive's default branch is not main"
git fetch -q "$ARCHIVE" '+refs/heads/main:refs/archive-check/main'
[ "$(git rev-parse refs/archive-check/main)" != "$OLD" ] || stop "the archive's default branch is the site's main: its scheduled jobs would run there"
[ -z "$(git ls-tree -r --name-only refs/archive-check/main | grep '^\.github/' || true)" ] || stop "the archive's default branch has a .github folder: jobs could run there"
have=$(git ls-remote "$ARCHIVE" "$AREF" | cut -f1)
if [ -n "$have" ] && git merge-base --is-ancestor "$have" "$OLD" 2> /dev/null; then range="$OLD ^$have"; else range="$OLD"; fi
# in pieces, oldest first: one push of the whole history is too large for one request
for c in $(git rev-list --first-parent --reverse $range | awk 'NR % 25 == 0') "$OLD"; do
  git push -q "$ARCHIVE" "$c:$AREF"
done
[ "$(git ls-remote "$ARCHIVE" "$AREF" | cut -f1)" = "$OLD" ] || stop "the archive does not hold $OLD"
echo "   the archive holds $OLD on ${AREF#refs/heads/}"

echo "3. the snapshot"
NEW=$(git -c user.name=BetSweep -c user.email=support@betsweep.co commit-tree "$TREE" -m "Site snapshot $DAY: the site exactly as it stood at ${OLD:0:9}

Every file is identical to that commit's. The history before this ($(git rev-list --count "$OLD") commits) is kept, whole, in the private
repository betsweep-site-archive, on the branch ${AREF#refs/heads/}. It was replaced here to bring this repository's size down:
about four fifths of it was old versions of pictures, saved again each time they changed.

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Pqo4PUB5f8JqeHqFrErqwg")
[ "$(git rev-parse "$NEW^{tree}")" = "$TREE" ] || stop "the snapshot's tree is not the old tip's"
[ -z "$(git diff --stat "$OLD" "$NEW")" ] || stop "the snapshot differs from the old tip"
echo "   snapshot $NEW: 1 commit, the same $(git ls-tree -r "$NEW" | wc -l) files"

if [ "$GO" != "--go" ]; then
  echo "4. NOT pushed (no --go). It would replace $OLD with $NEW on main, only if main is still at $OLD."
  exit 0
fi
echo "4. the swap"
git push --force-with-lease="refs/heads/main:$OLD" "$SITE" "$NEW:refs/heads/main"
git update-ref "refs/snapshots/$DAY-old" "$OLD"        # the mirror keeps the old tip by name
now=$(git ls-remote "$SITE" refs/heads/main | cut -f1)
[ "$now" = "$NEW" ] || echo "CHECK: main is at $now, not the snapshot - a job may have pushed on top of it already (that is fine); look at its log"
echo "   done. old tip $OLD is in the archive and in this mirror; main is now $now"
