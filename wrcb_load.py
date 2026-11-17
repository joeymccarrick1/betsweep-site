#!/usr/bin/env python3
"""wrcb_load.py - Mike Clay's weekly WR-CB cheatsheet (the PDF the owner uploads) -> rows for 'AUTO - WR CB Matchups'.

    python3 -I wrcb_load.py <pdf> <week> <first empty row on the tab>      -> out/wrcb_load.json + a printed summary
    python3 -I wrcb_load.py <pdf> <week> --check <in/wrcb.json>            -> compares the parsed rows with that week's rows on the mirror

(-I because the PDF is an upload: nothing next to it may be imported.) Written 11/17 from the Week 10 and Week 11 loads; run on the
Week 10 file it reproduces all 84 rows on the sheet cell for cell.

What it reads
  page 1, one line per receiver:  OFF Receiver Pos Tgt% Ht Wt LWR Slot RWR Rt T/R F/R | matchup T/R F/R | [S] DEF [Z%] Defender Pos Ht Wt
                                  RCB Slot LCB | snap Rt T/R F/R | coverage Rt T/R F/R        ("S" before DEF = projected shadow;
                                  the defense's zone % is printed on one of its three rows)
  page 2, the "Season" rows:      Off Def Season LWR Slot RWR Perimeter Overall FPOE EPA      (rank 1 = the defense that ALLOWS THE MOST,
                                  i.e. the easy matchup - checked 11/17 against the cell colours and against points actually allowed)
What it writes (out/wrcb_load.json): "blocks" = the four value ranges to send with update_values, "formulas" = the array formulas for the
block's first row (update_formulas), all with their A1 ranges. Columns: C-E receiver / team / opponent; H-S role, target share, routes,
alignment, T/R, F/R, primary corner, his team, shadow, exposure; U-AG the corner's alignment and snap / coverage numbers, zone %, the
four defense ranks; AS-AT Clay's matchup deltas. Primary corner = the listed corner on a shadow row, else the defense's corner with the
highest alignment exposure (LWR x RCB + Slot x Slot + RWR x LCB).
After writing: dispatch sheet-mirror.yml, pull the mirror, run the --check form (must print 0 mismatched cells), then rebuild.
The Alignment Def Score is (16.5 - rank) / 15.5: POSITIVE = easier. (The Week 8-10 blocks carried the opposite sign until 11/17.)
"""
import collections, json, os, re, sys

ROW = re.compile(r"^(?P<off>[A-Z]{2,3}) (?P<wr>.+?) (?P<pos>[LSR]) (?P<tgt>\d+%) (?P<ht>\d-\d+) (?P<wt>\d+) (?P<lwr>\d+%) (?P<slot>\d+%) (?P<rwr>\d+%) (?P<rt>\d+) (?P<tr>\d+%) (?P<fr>-?\d\.\d+) (?P<mtr>-?\d+%) (?P<mfr>-?\d\.\d+) "
                 r"(?:(?P<sh>S) )?(?P<def>[A-Z]{2,3}) (?:(?P<z>\d+%) )?(?P<cb>.+?) (?P<cpos>[LSR]) (?P<cht>\d-\d+) (?P<cwt>\d+) (?P<rcb>\d+%) (?P<cslot>\d+%) (?P<lcb>\d+%)(?P<rest>(?: -?[\d.]+%?)*)$")
pct = lambda s: round(int(s.rstrip("%")) / 100, 4)
ALL32 = "ARZ ATL BLT BUF CAR CHI CIN CLV DAL DEN DET GB HST IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split()

def parse(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages); t1 = pdf.pages[0].extract_text() or ""; t2 = pdf.pages[1].extract_text() if pages > 1 else ""
    rows, problems = [], []
    for line in t1.split("\n"):
        line = line.strip()
        if not re.match(r"^[A-Z]{2,3} \S", line) or line.startswith("OFF "): continue
        m = ROW.match(line)
        if not m: problems.append(f"line not read: {line}"); continue
        d = m.groupdict(); num = lambda s: pct(s) if s.endswith("%") else (float(s) if "." in s else int(s))
        rows.append({"off": d["off"], "wr": d["wr"], "pos": d["pos"], "tgt": pct(d["tgt"]), "lwr": pct(d["lwr"]), "slot": pct(d["slot"]), "rwr": pct(d["rwr"]), "rt": int(d["rt"]), "tr": pct(d["tr"]),
                     "fr": float(d["fr"]), "mtr": pct(d["mtr"]), "mfr": float(d["mfr"]), "sh": bool(d["sh"]), "def": d["def"], "z": pct(d["z"]) if d["z"] else None,
                     "cb": {"name": d["cb"], "rcb": pct(d["rcb"]), "slot": pct(d["cslot"]), "lcb": pct(d["lcb"]), "rest": [num(x) for x in d["rest"].split()]}})
    season = {}
    for line in (t2 or "").split("\n"):
        m = re.match(r"^([A-Z]{2,3}) ([A-Z]{2,3}) Season (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$", line.strip())
        if m: season[(m.group(1), m.group(2))] = [int(x) for x in m.groups()[2:6]]
    by = collections.OrderedDict()
    for r in rows: by.setdefault(r["off"], []).append(r)
    out = []
    for off, rs in by.items():
        if len(rs) != 3: problems.append(f"{off}: {len(rs)} receiver rows (expected 3)")
        if len({r["def"] for r in rs}) != 1: problems.append(f"{off}: defenders from more than one team")
        z = next((r["z"] for r in rs if r["z"] is not None), None)
        if z is None: problems.append(f"{off}: no zone %")
        sr = season.get((off, rs[0]["def"]))
        if not sr: problems.append(f"{off}|{rs[0]['def']}: no Season row on page 2")
        cbs = [r["cb"] for r in rs]
        for r in rs:
            ex = lambda c: r["lwr"] * c["rcb"] + r["slot"] * c["slot"] + r["rwr"] * c["lcb"]
            cb = r["cb"] if r["sh"] else max(cbs, key=ex); rest = cb["rest"] + [None] * (6 - len(cb["rest"]))
            if len(cb["rest"]) != 6: problems.append(f"{r['wr']}: corner {cb['name']} has {len(cb['rest'])} of 6 numbers")
            row = [None] * 46
            row[2], row[3], row[4] = r["wr"], off, r["def"]
            row[7:15] = [r["pos"], r["tgt"], r["rt"], r["lwr"], r["slot"], r["rwr"], r["tr"], r["fr"]]
            row[15:19] = [cb["name"], r["def"], ("YES" if r["sh"] else ""), round(ex(cb), 2)]
            row[20:23] = [cb["rcb"], cb["slot"], cb["lcb"]]
            row[23:28] = [rest[0], rest[1], rest[2], rest[4], rest[5]]
            row[28] = z
            if sr: row[29:33] = sr
            row[44], row[45] = r["mtr"], r["mfr"]
            out.append(row)
    return {"pages": pages, "rows": out, "problems": problems, "shadows": sum(1 for r in rows if r["sh"]), "teams": list(by)}

def formulas(a, b, week, name, byes, today):
    R = lambda col: f"{col}{a}:{col}{b}"; C = f'C{a}:C{b}=""'
    return {
        f"A{a}:B{a}": [[f'=ARRAYFORMULA(IF({C},"",2026))', f'=ARRAYFORMULA(IF({C},"",{week}))']],
        f"F{a}:G{a}": [[f'=ARRAYFORMULA(IF({C},"","FULL PDF"))', f'=ARRAYFORMULA(IF({C},"","{name} (owner upload {today}, full slate; {", ".join(byes)} on bye)"))']],
        f"T{a}": [[f'=ARRAYFORMULA(IF({C},"","ALIGNMENT CALC"))']],
        f"AH{a}:AR{a}": [[
            f'=ARRAYFORMULA(IF({C},"","Clay matchup delta: T/R "&TEXT({R("AS")},"+0%;-0%")&", F/R "&TEXT({R("AT")},"+0.00;-0.00")&"."))',
            f'=ARRAYFORMULA(IF({C},"",IF(({R("X")}="")+({R("X")}=0),"NEW STARTER / NO SAMPLE",IF({R("X")}<40,"LIMITED",IF({R("X")}<80,"MODERATE","ESTABLISHED")))))',
            f'=ARRAYFORMULA(IF({C},"",{R("K")}*{R("AD")}+{R("L")}*{R("AE")}+{R("M")}*{R("AF")}))',
            f'=ARRAYFORMULA(IF({R("AJ")}="","",(16.5-{R("AJ")})/15.5))',
            f'=ARRAYFORMULA(IF(({C})+({R("X")}="")+({R("X")}<40)+({R("AA")}=""),"",({R("AA")}-AVERAGE(FILTER({R("AA")},{R("X")}>=40,{R("AA")}<>"")))/STDEV(FILTER({R("AA")},{R("X")}>=40,{R("AA")}<>""))))',
            f'=ARRAYFORMULA(IF(({C})+({R("X")}="")+({R("X")}<40)+({R("AB")}=""),"",({R("AB")}-AVERAGE(FILTER({R("AB")},{R("X")}>=40,{R("AB")}<>"")))/STDEV(FILTER({R("AB")},{R("X")}>=40,{R("AB")}<>""))))',
            f'=ARRAYFORMULA(IF({C},"",IF(({R("X")}="")+({R("X")}=0),0,IF({R("X")}>=100,1,{R("X")}/100))))',
            f'=ARRAYFORMULA(IF({C},"",{R("AK")}+IF({R("AL")}="",0,{R("S")}*{R("AN")}*{R("AL")})))',
            f'=ARRAYFORMULA(IF({C},"",{R("AK")}+IF({R("AM")}="",0,{R("S")}*{R("AN")}*{R("AM")})))',
            f'=ARRAYFORMULA(IF({C},"",IF(NOT(ISNUMBER({R("AK")})),"UNKNOWN",IF({R("AK")}>=0.4,"FAVORABLE",IF({R("AK")}<=-0.4,"DIFFICULT","NEUTRAL")))))',
            f'=ARRAYFORMULA(IF({C},"",IF(({R("X")}="")+({R("X")}<40),"LOW",IF(({R("R")}="YES")*({R("X")}>=100)*({R("S")}>=0.55),"HIGH","MEDIUM"))))']],
    }

DATA_COLS = [2, 3, 4, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 44, 45]
def check(rows, mirror, week):
    v = json.load(open(mirror))["values"]; H = v[0]
    sheet = [r + [""] * (46 - len(r)) for r in v[1:] if len(r) > 1 and str(r[1]).strip() == str(week)]
    def num(x):
        try: return float(str(x).replace("%", "").replace(",", ""))
        except Exception: return None
    bad = []
    for a, b in zip(rows, sheet):
        for c in DATA_COLS:
            x, y = a[c], b[c]
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                yv = num(y)
                if yv is not None and "%" in str(y): yv /= 100
                ok = yv is not None and abs(yv - x) < 0.006
            else: ok = (x or "") == (y or "")
            if not ok: bad.append((a[2], H[c], x, y))
    return len(sheet), bad

if __name__ == "__main__":
    pdf, week = sys.argv[1], int(sys.argv[2]); d = parse(pdf)
    print(f"{d['pages']} pages; {len(d['rows'])} receivers, {len(d['teams'])} offenses, {d['shadows']} shadows; problems: {d['problems'] or 'none'}")
    if "--check" in sys.argv:
        n, bad = check(d["rows"], sys.argv[sys.argv.index("--check") + 1], week)
        print(f"{len(d['rows'])} parsed vs {n} on the tab for Week {week}; mismatched cells: {len(bad)}"); [print("  ", b) for b in bad[:12]]
        sys.exit(1 if bad or n != len(d["rows"]) else 0)
    a = int(sys.argv[3]); b = a + len(d["rows"]) - 1; rows = d["rows"]
    import datetime
    byes = [t for t in ALL32 if t not in d["teams"]]
    out = {"tab": "AUTO - WR CB Matchups", "week": week, "first_row": a, "last_row": b, "byes": byes, "problems": d["problems"],
           "blocks": {f"C{a}:E{b}": [r[2:5] for r in rows], f"H{a}:S{b}": [r[7:19] for r in rows], f"U{a}:AG{b}": [r[20:33] for r in rows], f"AS{a}:AT{b}": [r[44:46] for r in rows]},
           "formulas": formulas(a, b, week, os.path.basename(pdf).split("-", 1)[-1], byes, datetime.date.today().isoformat())}
    here = os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(here, "out"), exist_ok=True)
    json.dump(out, open(os.path.join(here, "out", "wrcb_load.json"), "w"), ensure_ascii=False)
    edge = [r[2] for r in rows if r[44] >= 0.08 and r[45] >= 0.15]; tough = [r[2] for r in rows if r[44] <= -0.08 and r[45] <= -0.15]
    print(f"rows {a}-{b}; byes {', '.join(byes) or 'none'}; coverage edges: {', '.join(edge) or 'none'}; tough coverage: {', '.join(tough) or 'none'}")
    print("wrote out/wrcb_load.json (blocks + first-row formulas). The mirror reads this tab to row 600: widen .github/sheets_pull.py and RUNBOOK call C before a block passes it.")
