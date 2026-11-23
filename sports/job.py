"""Everything the feeds-sports job builds, one sport after another: `python3 -m sports.job --feeds ../out --out ../out`.

The job on main calls this one module, so a new sport is added here (in the generators, where it is tested) and not in the job's file.
Each sport's step is on its own: one failing is printed and does not stop the next.

  nba   sports.nba.publish   the board, the nightly grading, the Stock Market's numbers
  epl   sports.epl.publish   the Premier League board (when that module exists)

Exit code: 1 only when the NBA board itself could not be written - the job's file then keeps the last board. Any other sport that
fails keeps its own last file here (copied from prev/, the branch as the last run left it).
"""
import importlib
import os
import shutil
import sys
import traceback

STEPS = (("nba", "sports.nba.publish", ()), ("epl", "sports.epl.publish", ("epl/board.json",)))


def arg(name, default=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def main():
    out = arg("--out"); prev = arg("--prev") or (os.path.join(os.path.dirname(os.path.abspath(out)), "prev") if out else None)
    rc = 0
    for name, mod, keep in STEPS:
        try:
            m = importlib.import_module(mod)
        except ModuleNotFoundError as e:
            if e.name == mod:                      # that sport is not built yet: nothing to run, nothing to report
                continue
            print(f"{name}: FAILED to load ({e})"); traceback.print_exc(); rc = rc or (1 if name == "nba" else 0); continue
        try:
            m.main()
        except SystemExit as e:
            if e.code not in (0, None):
                print(f"{name}: stopped with exit code {e.code}"); rc = rc or (1 if name == "nba" else 0)
        except Exception as e:
            print(f"{name}: FAILED ({type(e).__name__}: {e})"); traceback.print_exc()
            if name == "nba":
                rc = 1
            for f in keep:                         # keep that sport's last file rather than lose it from the branch
                src, dst = os.path.join(prev or "", f), os.path.join(out or "", f)
                if prev and out and os.path.exists(src) and not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst); print(f"{name}: kept the last run's {f}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
