# NBA Salary Chart Studio

An offline salary-cap chart viewer. The finished app is a single HTML file
(`nba_salary_chart.html`) — your friend just **double-clicks it** to open it in
a browser. No installs, no internet.

## Folder layout

```
salary-chart/
├─ build_salary_app.py      ← the generator (needs Python)
├─ nba_salary_chart.html    ← the finished app (share THIS file)
├─ README.md
└─ csv/                     ← one CSV per team
   ├─ OKC.csv
   ├─ LAL.csv
   └─ BOS.csv
```

## Using the app (no coding)

Open `nba_salary_chart.html`. From the top bar you can:

- **Team** — switch between every team in the `csv/` folder.
- **From** — drop earlier seasons you no longer care about.
- **Options** — click the section header to collapse/expand it; set each option
  year to Pending / Accept / Decline. Declining cascades to later option years;
  accepting cascades to earlier ones.
- **Extensions** — add a contract extension ($ per year or % of the cap), with
  an optional option year on the final season.
- **Trades / Waives** — remove a player from a chosen year onward (with undo).
- **Add CSV** — load a one-off team file without rebuilding (or drag a CSV onto
  the window). It won't be saved into the folder — to make it permanent, drop it
  in `csv/` and re-run the generator.
- **Export PNG** — save the chart plus a roster-moves summary as an image.

## Adding or changing teams (needs Python once)

1. Put a new CSV in the `csv/` folder. Name it with the team label, e.g.
   `MIA.csv` → shows up as "MIA" in the picker.
2. Re-run the generator:

   ```
   python build_salary_app.py
   ```

   (Optionally `python build_salary_app.py csv my_app.html` to choose folders/names.)

3. Send the updated `nba_salary_chart.html`.

## CSV format

A header row starting with `Player`, one column per season (`2025-26`,
`2026-27`, …), and a trailing `Guaranteed` column. Salaries may include `$` and
commas. Blank cells mean no salary that year. A year's salary that pushes a
player's running total above their guaranteed amount is auto-detected as an
option / non-guaranteed year (shown hatched on the chart).

## Auto-fetching salaries from Spotrac (optional)

Instead of typing CSVs by hand, `fetch_team_csv.py` scrapes a team's salary
table straight from Spotrac and writes it in the format above. It uses a real
browser (Playwright) under the hood because Spotrac builds its table with
JavaScript — the Google Sheets `IMPORTHTML` trick and plain scrapers can't see
that table, but this can.

One-time setup:

```
pip install playwright beautifulsoup4
python -m playwright install chromium
```

Then fetch one team (3-letter code or full Spotrac slug):

```
python fetch_team_csv.py OKC
python fetch_team_csv.py oklahoma-city-thunder
```

…or every team at once:

```
python fetch_team_csv.py --all
```

Files land in `csv/` (e.g. `csv/OKC.csv`). Re-run `build_salary_app.py`
afterwards to fold the new data into the app.

Spotrac doesn't publish a per-player "guaranteed total," so the scraper derives
it: a player's Guaranteed amount is the sum of their seasons that Spotrac does
**not** color-code as a player/club option. That's what drives the hatched
option years in the chart. If a future Spotrac redesign changes how options are
marked, run with `--dump-html page.html` to save the rendered page so the
detection can be adjusted. Always spot-check a fetched team against Spotrac the
first time.

