"""Where is the model drifting? (owner 11/1: "Can we identify when the model's projections are more likely to be wrong and adjust?")
RUNBOOK Step 5 (Tuesdays, after grading).

  python3 calib_market.py <GRADED WEEK>

Inputs: in/legsnaps.json ('V2 - FanDuel Leg Snapshots', graded), in/closing.json ('V2 - Closing Lines', optional).
For the graded week AND season to date (Latest Snapshot rows, HIT / MISS only) it prints and writes out/calib_market.json + .md:
  - by market: legs, model %, book %, hit %, model log loss vs book log loss, units per 1u leg
  - by model-vs-book gap (-10+, -5..-10, -5..+5, +5..+10, +10+)
  - by sample size (games <= 3 / 4+), by warning yes / no
  - 50/50 model-book blend log loss next to model and book (the candidate fix from 11/1)
  - line movement (when closing prices exist): legs whose FanDuel price moved toward the side we list (implied up 1+ pt after the freeze)
    vs moved away vs flat - hit rate and units. This is the "did the market agree with us" signal.
A segment is called DRIFTING when it has 60+ legs and the book's log loss beats the model's by 0.01+ in BOTH this week and season to date.
Nothing here changes a projection; the drifting list goes in the Tuesday log row and the receipt, and changes need owner approval.
"""
import json, math, os, sys

IN, OUT = "in", "out"
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
def num(x):
    try: return float(str(x).replace(",", "").replace("%", ""))
    except Exception: return None
def ll(p, y): p = min(max(p, 1e-4), 1 - 1e-4); return -(y * math.log(p) + (1 - y) * math.log(1 - p))

def load(W):
    L = vals("legsnaps.json")
    if not L: return []
    H = {c: i for i, c in enumerate(L[0])}; c = lambda r, k: r[H[k]] if H.get(k) is not None and H[k] < len(r) else ""
    close = {}
    C = vals("closing.json")
    if C:
        CH = {k: i for i, k in enumerate(C[0])}
        for r in C[1:]:
            r = r + [""] * (len(C[0]) - len(r)); w = num(r[CH.get("Week", 0)]); ci = num(r[CH["Close implied"]]) if "Close implied" in CH else None
            if w is not None and ci is not None: close[(int(w), str(r[CH["Key"]]).strip().lower())] = ci if ci <= 1 else ci / 100
    out = []
    for r in L[1:]:
        if str(c(r, "Latest Snapshot")).upper() != "TRUE" or c(r, "Result") not in ("HIT", "MISS"): continue
        w = num(c(r, "Week")); p = num(c(r, "Model % (hist-adj)")); b = num(c(r, "Book implied %"))
        if w is None or p is None or b is None or int(w) > W: continue
        if p > 1: p /= 100
        if b > 1: b /= 100
        k = str(c(r, "Key")).strip().lower(); ci = close.get((int(w), k))
        out.append({"w": int(w), "m": c(r, "Market"), "p": p, "b": b, "y": 1 if c(r, "Result") == "HIT" else 0, "u": num(c(r, "Units (1u)")) or 0.0,
                    "n": num(c(r, "Games")) or 0, "warn": bool(str(c(r, "Warnings")).strip()), "mv": None if ci is None else ci - b})
    return out

def stats(xs):
    n = len(xs)
    if not n: return None
    return {"n": n, "model": sum(x["p"] for x in xs) / n, "book": sum(x["b"] for x in xs) / n, "hit": sum(x["y"] for x in xs) / n,
            "ll_model": sum(ll(x["p"], x["y"]) for x in xs) / n, "ll_book": sum(ll(x["b"], x["y"]) for x in xs) / n,
            "ll_blend": sum(ll(0.5 * x["p"] + 0.5 * x["b"], x["y"]) for x in xs) / n, "units": sum(x["u"] for x in xs) / n}

def segments(xs):
    S = {}
    for m in sorted(set(x["m"] for x in xs)): S["market: " + m] = [x for x in xs if x["m"] == m]
    for lab, lo, hi in (("gap -10+", -9, -.10), ("gap -5..-10", -.10, -.05), ("gap -5..+5", -.05, .05), ("gap +5..+10", .05, .10), ("gap +10+", .10, 9)):
        S[lab] = [x for x in xs if lo <= x["p"] - x["b"] < hi]
    S["games <= 3"] = [x for x in xs if x["n"] <= 3]; S["games 4+"] = [x for x in xs if x["n"] > 3]
    S["warning"] = [x for x in xs if x["warn"]]; S["no warning"] = [x for x in xs if not x["warn"]]
    mv = [x for x in xs if x["mv"] is not None]
    if mv:
        S["price moved our way (1+ pt)"] = [x for x in mv if x["mv"] >= 0.01]
        S["price flat"] = [x for x in mv if abs(x["mv"]) < 0.01]
        S["price moved away (1+ pt)"] = [x for x in mv if x["mv"] <= -0.01]
    return S

def main(W):
    W = int(W); allx = load(W)
    if not allx: print("calib: no graded legs"); return
    wk = [x for x in allx if x["w"] == W]
    A, B = segments(wk), segments(allx)
    rows, drift = [], []
    for k in B:
        a, b = stats(A.get(k, [])), stats(B[k])
        rows.append((k, a, b))
        if a and b and a["n"] >= 60 and b["n"] >= 60 and a["ll_book"] < a["ll_model"] - 0.01 and b["ll_book"] < b["ll_model"] - 0.01: drift.append(k)
    f = lambda s: "-" if not s else f'{s["n"]} | {s["model"]*100:.0f}% / {s["book"]*100:.0f}% / {s["hit"]*100:.0f}% | {s["ll_model"]:.3f} / {s["ll_book"]:.3f} / {s["ll_blend"]:.3f} | {s["units"]:+.3f}'
    md = [f"# Model calibration - Week {W} and season to date", "", "Each cell: legs | model / book / hit | log loss model / book / 50-50 blend (lower is better) | units per 1u leg", "",
          f"| Segment | Week {W} | Season |", "|---|---|---|"] + [f"| {k} | {f(a)} | {f(b)} |" for k, a, b in rows]
    md += ["", "DRIFTING (book beat the model this week and season, 60+ legs each): " + (", ".join(drift) if drift else "none")]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "calib_market.md"), "w").write("\n".join(md) + "\n")
    json.dump({"week": W, "rows": [[k, a, b] for k, a, b in rows], "drifting": drift}, open(os.path.join(OUT, "calib_market.json"), "w"))
    s_all = stats(wk) or stats(allx)
    print(f"calib week {W}: {len(wk)} graded legs; model LL {s_all['ll_model']:.3f} vs book {s_all['ll_book']:.3f} vs 50/50 blend {s_all['ll_blend']:.3f}; drifting: {', '.join(drift) if drift else 'none'}")

if __name__ == "__main__":
    main(sys.argv[1])
