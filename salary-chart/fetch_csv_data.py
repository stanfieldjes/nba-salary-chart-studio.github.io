#!/usr/bin/env python3
"""
fetch_csv_data.py — scrape NBA team data from Basketball-Reference into CSVs
that the salary-chart app (and any roster viewer) can read.

Two kinds of data can be fetched:

  • Salary data  → one contracts table per team at
        https://www.basketball-reference.com/contracts/<CODE>.html
    Written to  csv/<CODE>.csv  — one file per team, in the unchanged
    format the salary app expects (OKC.csv, LAL.csv, …).

  • Player data  → one roster table per team at
        https://www.basketball-reference.com/teams/<CODE>/2026.html
    Written to a SINGLE league-wide file  csv/players.csv  with columns:
        team, name, position, height, weight, bday (M/D/Y numeric),
        years experience
    Every fetched team's roster is appended into this one file. Because each
    row carries its team code, there's no need for per-team player files.

Run with no arguments to be prompted interactively for which data you want
(salary, player, or both) and which team(s). Flags still work for scripting.
"""

import argparse
import csv
import os
import random
import re
import sys
import time

# ── Roster season ─────────────────────────────────────────────────────────────
# B-Ref roster pages live at /teams/<CODE>/<YEAR>.html. Bump this each season.
ROSTER_YEAR = 2026

# ── Output layout ─────────────────────────────────────────────────────────────
# Salary data is one file per team (csv/<CODE>.csv). Player data for the whole
# league lives in a single file, since every row carries its own team column.
CSV_DIR = "csv"
PLAYERS_CSV = os.path.join(CSV_DIR, "players.csv")

# ── Team Codes: Standard 3-letter codes ───────────────────────────────────────

TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
]

def resolve_team_code(team: str) -> str:
    up = team.strip().upper()
    if up in TEAMS:
        return up
    for t in TEAMS:
        if t in up:
            return t
    raise SystemExit(f"Unknown team '{team}'. Use a standard 3-letter code (e.g. OKC, LAL).")

def get_bref_code(code: str) -> str:
    """Basketball-Reference uses slightly older acronyms for 3 teams."""
    mapping = {
        "BKN": "BRK",
        "CHA": "CHO",
        "PHX": "PHO"
    }
    return mapping.get(code, code)


# ── Salary helpers ────────────────────────────────────────────────────────────

def clean_money(text: str):
    if text is None: return None
    s = text.strip()
    if not s or s in {"-", "—", "–"}: return None
    if "-" in s: return None
    m = re.search(r"\$?\s*([\d,]+)", s)
    if not m: return None
    digits = m.group(1).replace(",", "")
    if not digits.isdigit(): return None
    val = int(digits)
    if val < 100_000: return None
    return val

def is_year_header(text: str) -> bool:
    return bool(re.match(r"\d{4}-\d{2}", (text or "").strip()))


# ── Core parsing: B-Ref contracts table → CSV rows ────────────────────────────

def parse_table_html(html: str):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Locate B-Ref's dedicated contracts table
    target = soup.find("table", id="contracts")
    if not target:
        raise ValueError("Could not find the <table id='contracts'> on the page.")

    # Locate the header row containing 'Player' and 'Guaranteed'
    thead = target.find("thead")
    header_rows = thead.find_all("tr") if thead else target.find_all("tr", limit=3)

    header_row = None
    headers = []
    for tr in header_rows:
        cells = tr.find_all(["th", "td"])
        txts = [c.get_text(" ", strip=True) for c in cells]
        if "Player" in txts and "Guaranteed" in txts:
            header_row = tr
            headers = txts
            break

    if not header_row:
        raise ValueError("Could not locate the header row containing 'Player' and 'Guaranteed'.")

    year_idx = {h: i for i, h in enumerate(headers) if is_year_header(h)}
    year_cols = list(year_idx.keys())

    if not year_cols:
        raise ValueError("Could not locate season columns in the table header.")

    player_i = headers.index("Player")
    age_i = headers.index("Age") if "Age" in headers else None
    guar_i = headers.index("Guaranteed")

    body = target.find("tbody") or target
    rows = []

    for tr in body.find_all("tr"):
        # Skip B-Ref's repeating mid-table headers
        if "thead" in tr.get("class", []):
            continue

        cells = tr.find_all(["th", "td"])
        if len(cells) <= max(player_i, guar_i, *year_idx.values()):
            continue

        first_txt = cells[0].get_text(" ", strip=True).lower()
        if "totals" in first_txt or "team" in first_txt:
            continue

        name = cells[player_i].get_text(" ", strip=True)
        if not name or not re.search(r'[A-Za-z]', name) or name.lower() == "player":
            continue

        age = ""
        if age_i is not None:
            raw_age = cells[age_i].get_text(" ", strip=True)
            age_match = re.search(r'\d+', raw_age)
            age = age_match.group() if age_match else raw_age

        salaries = {}
        for yc, idx in year_idx.items():
            val = clean_money(cells[idx].get_text(" ", strip=True))
            if val is not None:
                salaries[yc] = val

        if not salaries:
            continue

        # Grab B-Ref's explicit Guaranteed total
        guaranteed = clean_money(cells[guar_i].get_text(" ", strip=True)) or 0

        row = {"Player": name, "Age": age}
        for yc in year_cols:
            row[yc] = salaries.get(yc, "")
        row["Guaranteed"] = guaranteed
        rows.append(row)

    return year_cols, rows


# ── Roster helpers ────────────────────────────────────────────────────────────

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    # common abbreviations, just in case
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

def parse_birthdate(text: str) -> str:
    """Convert 'November 7 2003' (or 'November 7, 2003') → '11/7/2003'.

    Returns '' if the date can't be parsed. Day and month are left
    un-padded (no leading zeros) to match the numeric M/D/Y request.
    """
    if not text:
        return ""
    s = text.strip()
    if not s:
        return ""
    # normalise: drop commas, collapse whitespace
    s = s.replace(",", " ")
    parts = s.split()
    if len(parts) < 3:
        return ""
    mon = MONTHS.get(parts[0].lower())
    day_m = re.search(r"\d+", parts[1])
    year_m = re.search(r"\d{4}", parts[2])
    if not (mon and day_m and year_m):
        return ""
    day = int(day_m.group())
    year = int(year_m.group())
    return f"{mon}/{day}/{year}"

def parse_experience(text: str) -> str:
    """B-Ref uses 'R' for rookies. Map to 0; otherwise keep the integer."""
    if text is None:
        return ""
    s = text.strip()
    if not s:
        return ""
    if s.upper() == "R":
        return "0"
    m = re.search(r"\d+", s)
    return m.group() if m else ""

def clean_player_name(text: str) -> str:
    """Strip B-Ref designation suffixes like '(TW)' / '(TWO)' and tidy spaces."""
    if not text:
        return ""
    # remove any parenthetical tag (TW, two-way, etc.)
    name = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    # collapse internal double-spaces B-Ref sometimes emits
    name = re.sub(r"\s{2,}", " ", name)
    return name


# ── Core parsing: B-Ref roster table → player CSV rows ────────────────────────

def parse_roster_html(html: str, team: str = ""):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    target = soup.find("table", id="roster")
    if not target:
        raise ValueError("Could not find the <table id='roster'> on the page.")

    # Build a header → column-index map from the table head.
    thead = target.find("thead")
    header_cells = []
    if thead:
        last_tr = thead.find_all("tr")[-1]
        header_cells = last_tr.find_all(["th", "td"])
    headers = [c.get_text(" ", strip=True) for c in header_cells]

    def col(*names):
        for n in names:
            if n in headers:
                return headers.index(n)
        return None

    # Header text is the most robust selector, but fall back to B-Ref's
    # stable data-stat attributes if a label is missing/renamed.
    idx_pos = col("Pos")
    idx_ht  = col("Ht")
    idx_wt  = col("Wt")
    idx_bd  = col("Birth Date")
    idx_exp = col("Exp")

    body = target.find("tbody") or target
    rows = []

    for tr in body.find_all("tr"):
        if "thead" in tr.get("class", []):
            continue

        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        # Map by data-stat too, so we're resilient to header drift.
        by_stat = {}
        for c in cells:
            ds = c.get("data-stat")
            if ds:
                by_stat[ds] = c.get_text(" ", strip=True)

        def get(header_idx, *stat_keys):
            if header_idx is not None and header_idx < len(cells):
                txt = cells[header_idx].get_text(" ", strip=True)
                if txt:
                    return txt
            for k in stat_keys:
                if k in by_stat:
                    return by_stat[k]
            return ""

        raw_name = by_stat.get("player", "")
        if not raw_name:
            # 'player' is the row's <th>; fall back to first cell text.
            raw_name = cells[0].get_text(" ", strip=True)
        name = clean_player_name(raw_name)
        if not name or not re.search(r"[A-Za-z]", name) or name.lower() == "player":
            continue

        position   = get(idx_pos, "pos")
        height     = get(idx_ht, "height")
        weight     = get(idx_wt, "weight")
        birth_raw  = get(idx_bd, "birth_date")
        exp_raw    = get(idx_exp, "years_experience")

        rows.append({
            "team": team,
            "name": name,
            "position": position,
            "height": height,
            "weight": weight,
            "bday": parse_birthdate(birth_raw),
            "years experience": parse_experience(exp_raw),
        })

    return rows


# ── Browser Render ────────────────────────────────────────────────────────────

def fetch_rendered_html(url: str, ready_markers, headless: bool = True,
                        timeout_s: int = 45) -> str:
    """Render a B-Ref page with Playwright and return HTML once `ready_markers`
    (a list of substrings) all appear in the page content."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "Playwright is not installed. Run:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)

        deadline = time.time() + timeout_s
        html = ""
        while time.time() < deadline:
            html = page.content()
            if all(m in html for m in ready_markers):
                page.wait_for_timeout(500)
                html = page.content()
                break
            page.wait_for_timeout(500)

        browser.close()
        return html


# ── Write CSVs ────────────────────────────────────────────────────────────────

def write_salary_csv(year_cols, rows, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    headers = ["Player", "Age"] + year_cols + ["Guaranteed"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] * 2 + ["Salary"] * len(year_cols) + [""])
        w.writerow(headers)

        for r in rows:
            line = [r["Player"], r["Age"]]
            for yc in year_cols:
                v = r.get(yc, "")
                line.append(f"${v:,}" if isinstance(v, int) else "")

            g = r["Guaranteed"]
            line.append(f"${g:,}" if isinstance(g, int) else "")

            w.writerow(line)

    return out_path


PLAYER_HEADERS = ["team", "name", "position", "height", "weight",
                  "bday", "years experience"]


def write_player_csv(rows, out_path):
    """Write all collected player rows (across any number of teams) to a single
    league-wide CSV. Rows already carry their own 'team' column."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(PLAYER_HEADERS)
        for r in rows:
            w.writerow([r.get(h, "") for h in PLAYER_HEADERS])

    return out_path


# ── Fetch orchestration ───────────────────────────────────────────────────────

def fetch_salary(code, out=None, headless=True, from_file=None, dump_html=None):
    out = out or os.path.join(CSV_DIR, f"{code}.csv")

    if from_file:
        with open(from_file, encoding="utf-8") as f:
            html = f.read()
        src = from_file
    else:
        bref_code = get_bref_code(code)
        url = f"https://www.basketball-reference.com/contracts/{bref_code}.html"
        print(f"  fetching salary  {url}")
        html = fetch_rendered_html(url, ['id="contracts"', "Guaranteed"],
                                   headless=headless)
        src = url

    if dump_html:
        with open(dump_html, "w", encoding="utf-8") as f:
            f.write(html)

    year_cols, rows = parse_table_html(html)
    if not rows:
        raise SystemExit(f"No player rows parsed from {src}.")

    write_salary_csv(year_cols, rows, out)
    print(f"  wrote {out}  ({len(rows)} players)")
    return out


def fetch_players(code, headless=True, from_file=None, dump_html=None):
    """Fetch and parse one team's roster, returning the list of player rows
    (each tagged with its team). Writing is deferred so every team's players
    can be collected into a single league-wide CSV by the caller."""
    if from_file:
        with open(from_file, encoding="utf-8") as f:
            html = f.read()
        src = from_file
    else:
        bref_code = get_bref_code(code)
        url = f"https://www.basketball-reference.com/teams/{bref_code}/{ROSTER_YEAR}.html"
        print(f"  fetching roster  {url}")
        html = fetch_rendered_html(url, ['id="roster"'], headless=headless)
        src = url

    if dump_html:
        with open(dump_html, "w", encoding="utf-8") as f:
            f.write(html)

    rows = parse_roster_html(html, team=code)
    if not rows:
        raise SystemExit(f"No player rows parsed from {src}.")

    print(f"  parsed roster    ({len(rows)} players)")
    return rows


def fetch_team(team, kinds, out_salary=None, headless=True,
               from_file=None, dump_html=None):
    """Fetch the requested `kinds` ({'salary','players'}) for one team.

    Salary data is written immediately to its per-team file. Player rows are
    NOT written here — they're returned so the caller can pool every team's
    players into one league-wide CSV. Returns the list of player rows (empty
    if 'players' wasn't requested)."""
    code = resolve_team_code(team)
    player_rows = []
    if "salary" in kinds:
        fetch_salary(code, out=out_salary, headless=headless,
                     from_file=from_file, dump_html=dump_html)
    if "players" in kinds:
        player_rows = fetch_players(code, headless=headless,
                                    from_file=from_file, dump_html=dump_html)
    return player_rows


# ── Interactive prompt ────────────────────────────────────────────────────────

def prompt_kinds():
    print("\nWhat data would you like to fetch?")
    print("  1) Team salary data")
    print("  2) Player data")
    print("  3) Both")
    while True:
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == "1":
            return {"salary"}
        if choice == "2":
            return {"players"}
        if choice == "3":
            return {"salary", "players"}
        print("  Please enter 1, 2, or 3.")

def prompt_teams():
    print("\nWhich team(s)?")
    print("  • Enter one or more 3-letter codes (e.g. OKC LAL BOS)")
    print("  • Or type ALL for every team")
    while True:
        raw = input("Team(s): ").strip()
        if not raw:
            print("  Please enter at least one team code (or ALL).")
            continue
        if raw.upper() == "ALL":
            return list(TEAMS)
        try:
            codes = [resolve_team_code(t) for t in raw.split()]
            return codes
        except SystemExit as e:
            print(f"  {e}")


# ── Batch runner ──────────────────────────────────────────────────────────────

def run_batch(codes, kinds, headless=True, players_out=PLAYERS_CSV):
    os.makedirs(CSV_DIR, exist_ok=True)
    multi = len(codes) > 1
    ok, fail = 0, []
    all_players = []          # pooled roster rows for the league-wide CSV
    for i, code in enumerate(codes):
        print(f"[{code}]")
        try:
            player_rows = fetch_team(code, kinds, headless=headless)
            all_players.extend(player_rows)
            ok += 1
        except Exception as e:
            print(f"  SKIPPED: {e}")
            fail.append(code)

        # B-Ref rate-limit avoidance between page loads (skip after the last team)
        if multi and i < len(codes) - 1:
            delay = random.uniform(6.0, 11.0)
            print(f"  sleeping for {delay:.1f}s to avoid rate limits...")
            time.sleep(delay)

    # Write every collected team's players into one league-wide file.
    if "players" in kinds and all_players:
        write_player_csv(all_players, players_out)
        print(f"\nWrote {players_out}  "
              f"({len(all_players)} players across {ok} team(s))")

    summary = f"\nDone: {ok} team(s) processed"
    if fail:
        summary += f", {len(fail)} failed ({', '.join(fail)})."
    print(summary)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Scrape NBA team salary and/or player data from B-Ref into CSVs.")
    ap.add_argument("team", nargs="?", help="3-letter code (e.g. OKC)")
    ap.add_argument("--all", action="store_true", help="fetch every team into csv/")
    ap.add_argument("--data", choices=["salary", "players", "both"],
                    help="which data to fetch (skips the interactive prompt)")
    ap.add_argument("--out", help="output CSV path for salary data (single team)")
    ap.add_argument("--out-players",
                    help=f"output path for the league-wide player CSV "
                         f"(default: {PLAYERS_CSV})")
    ap.add_argument("--from-file", help="parse a saved HTML file instead of fetching")
    ap.add_argument("--dump-html", help="save the rendered HTML to this path")
    ap.add_argument("--show", action="store_true", help="run the browser visibly")
    args = ap.parse_args()

    headless = not args.show

    # Resolve which kinds of data to fetch.
    if args.data == "salary":
        kinds = {"salary"}
    elif args.data == "players":
        kinds = {"players"}
    elif args.data == "both":
        kinds = {"salary", "players"}
    else:
        kinds = None  # decide below (prompt if nothing else specified)

    players_out = args.out_players or PLAYERS_CSV

    # --- Batch path: --all -------------------------------------------------
    if args.all:
        if kinds is None:
            kinds = prompt_kinds()
        run_batch(list(TEAMS), kinds, headless=headless, players_out=players_out)
        return

    # --- Single explicit team ---------------------------------------------
    if args.team:
        if kinds is None:
            kinds = prompt_kinds()
        code = resolve_team_code(args.team)
        os.makedirs(CSV_DIR, exist_ok=True)
        print(f"[{code}]")
        player_rows = fetch_team(code, kinds,
                                 out_salary=args.out, headless=headless,
                                 from_file=args.from_file,
                                 dump_html=args.dump_html)
        # Even for a single team, players go to the league-wide CSV.
        if "players" in kinds and player_rows:
            write_player_csv(player_rows, players_out)
            print(f"\nWrote {players_out}  ({len(player_rows)} players)")
        return

    # --- Fully interactive (no team given) --------------------------------
    if kinds is None:
        kinds = prompt_kinds()
    codes = prompt_teams()
    run_batch(codes, kinds, headless=headless, players_out=players_out)


if __name__ == "__main__":
    main()