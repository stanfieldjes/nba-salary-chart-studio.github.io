#!/usr/bin/env python3
"""
fetch_team_csv.py — scrape a team's salary table from Basketball-Reference 
into a CSV that the salary-chart app understands.
"""

import argparse
import csv
import os
import random
import re
import sys
import time

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


# ── Core parsing: B-Ref Table → CSV rows ──────────────────────────────────────

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


# ── Browser Render ────────────────────────────────────────────────────────────

def fetch_rendered_html(url: str, headless: bool = True, timeout_s: int = 45) -> str:
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
        
        # Wait for B-Ref's table to be parsed
        deadline = time.time() + timeout_s
        html = ""
        while time.time() < deadline:
            html = page.content()
            if 'id="contracts"' in html and "Guaranteed" in html:
                page.wait_for_timeout(500)
                html = page.content()
                break
            page.wait_for_timeout(500)
            
        browser.close()
        return html


# ── Write CSV ─────────────────────────────────────────────────────────────────

def write_csv(year_cols, rows, out_path):
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


# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_team(team, out=None, headless=True, from_file=None, dump_html=None):
    code = resolve_team_code(team)
    out = out or os.path.join("csv", f"{code}.csv")
    
    if from_file:                       
        with open(from_file, encoding="utf-8") as f:
            html = f.read()
        src = from_file
    else:
        bref_code = get_bref_code(code)
        url = f"https://www.basketball-reference.com/contracts/{bref_code}.html"
        print(f"  fetching {url}")
        html = fetch_rendered_html(url, headless=headless)
        src = url
        
    if dump_html:
        with open(dump_html, "w", encoding="utf-8") as f:
            f.write(html)
            
    year_cols, rows = parse_table_html(html)
    if not rows:
        raise SystemExit(f"No player rows parsed from {src}.")
        
    write_csv(year_cols, rows, out)
    print(f"  wrote {out}  ({len(rows)} players)")
    return out


def main():
    ap = argparse.ArgumentParser(description="Scrape NBA team salaries from B-Ref into a CSV.")
    ap.add_argument("team", nargs="?", help="3-letter code (e.g. OKC)")
    ap.add_argument("--all", action="store_true", help="fetch every team into csv/")
    ap.add_argument("--out", help="output CSV path (single team)")
    ap.add_argument("--from-file", help="parse a saved HTML file instead of fetching")
    ap.add_argument("--dump-html", help="save the rendered HTML to this path")
    ap.add_argument("--show", action="store_true", help="run the browser visibly")
    args = ap.parse_args()

    if args.all:
        os.makedirs("csv", exist_ok=True)
        ok, fail = 0, []
        for code in TEAMS:
            print(f"[{code}]")
            try:
                fetch_team(code, headless=not args.show)
                ok += 1
                
                # B-Ref rate limit avoidance
                delay = random.uniform(6.0, 11.0)
                print(f"  sleeping for {delay:.1f}s to avoid rate limits...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"  SKIPPED: {e}")
                fail.append(code)
                
        print(f"\nDone: {ok} teams written" + (f", {len(fail)} failed." if fail else ""))
        return

    if not args.team:
        ap.error("give a team code (e.g. OKC) or use --all")
        
    fetch_team(args.team, out=args.out, headless=not args.show,
               from_file=args.from_file, dump_html=args.dump_html)

if __name__ == "__main__":
    main()