#!/usr/bin/env python3
"""
build_salary_app.py — generate a self-contained NBA salary-chart web app.

Usage
-----
    python build_salary_app.py [csv_folder] [output_html]

Defaults: csv_folder="csv", output_html="nba_salary_chart.html".

What it does
------------
Scans every *.csv in the csv folder, embeds them all into one HTML file, and
writes an offline app your friend can open by double-clicking. The team is
chosen in-app from a dropdown (one entry per CSV). No Python or internet is
needed to *use* the result — only to regenerate it after adding/editing CSVs.

CSV format (same as before): a header row beginning with "Player", season
columns like 2025-26 … 2030-31, and a trailing "Guaranteed" column. The file
name (minus .csv) becomes the team label, so name them OKC.csv, LAL.csv, etc.
"""

import csv
import io
import json
import os
import re
import sys


# ── CSV parsing (mirrors the app's own parser so embedded data is clean) ──────

def parse_salary(value):
    v = (value or "").strip().replace("$", "").replace(",", "")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def load_team_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.reader(f))

    header_idx = next((i for i, r in enumerate(raw)
                       if r and r[0].strip() == "Player"), None)
    if header_idx is None:
        raise ValueError("no header row starting with 'Player'")

    headers = [h.strip() for h in raw[header_idx]]
    year_cols = [h for h in headers if re.match(r"\d{4}-\d{2}", h)]
    if not year_cols:
        raise ValueError("no season columns (e.g. 2025-26) found")
    guaranteed_col = headers[-1]

    players = []
    for row in raw[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        d = dict(zip(headers, [c.strip() for c in row]))
        if d.get("Player"):
            players.append(d)

    # Re-serialize to a normalized CSV string the app parses identically.
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for d in players:
        w.writerow([d.get(h, "") for h in headers])
    return {"yearCols": year_cols, "csv": buf.getvalue()}


def discover_teams(folder):
    if not os.path.isdir(folder):
        raise SystemExit(f"CSV folder not found: {folder}\n"
                         f"Create it and drop one CSV per team inside "
                         f"(e.g. {folder}/OKC.csv).")
    teams = {}
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".csv"))
    if not files:
        raise SystemExit(f"No .csv files in {folder}. Add at least one team CSV.")
    for fn in files:
        label = os.path.splitext(fn)[0]
        try:
            teams[label] = load_team_csv(os.path.join(folder, fn))
            print(f"  embedded {label:<6} ({fn})")
        except Exception as e:
            print(f"  SKIPPED  {fn}: {e}")
    if not teams:
        raise SystemExit("No valid CSVs could be embedded.")
    return teams


# ── HTML template ─────────────────────────────────────────────────────────────

def build_html(teams):
    data_json = json.dumps(teams, ensure_ascii=False)
    return HTML_TEMPLATE.replace("/*__TEAM_DATA__*/", data_json)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NBA Salary Chart Studio</title>
<style>
  /* GUI shell — dark (default) */
  :root{
    --bg:#161616; --panel:#202020; --sidebar:#1d1d1d; --card:#282828;
    --text:#D4D4D4; --subtext:#8A8A8A; --line:#2e2e2e;
    --accent:#5EA8ED; --green:#6AE88A; --red:#E86A6A; --yellow:#F5D76E;
    --blue:#6AB0F5; --purple:#C07EF5; --orange:#EDA45E;
    /* Chart — dark */
    --chart-bg:#1A1A1A; --chart-panel:#242424; --chart-text:#D0D0D0;
    --chart-sub:#888888; --chart-edge:#1A1A1A; --chart-sep:#FFFFFF;
    --chart-name:#FFFFFF; --chart-legend-bg:#242424; --chart-legend-line:#30363D;
    --chart-swatch:#888888; --chart-tip-bg:#181818; --chart-tip-line:#444444;
    --chart-grid:rgba(255,255,255,0.05); --chart-bar:#1A1A1A; --chart-bar-edge:#000000;
    --chart-bar-top:#2C2C2C; --chart-bar-bot:#161616; --chart-name-col:#FFFFFF;
    --chart-hatch:rgba(150,150,150,0.55);
    --chart-floor:rgba(255,255,255,0.07);
  }
  /* Light theme override */
  body.light{
    --bg:#EEF0F3; --panel:#FFFFFF; --sidebar:#F4F6F8; --card:#FFFFFF;
    --text:#1E2228; --subtext:#6B7280; --line:#D8DCE2;
    --accent:#1F6FD6; --green:#1E9E54; --red:#D24747; --yellow:#C18A12;
    --blue:#1F6FD6; --purple:#8347C0; --orange:#C9701F;
    --chart-bg:#FFFFFF; --chart-panel:#F3F5F8; --chart-text:#2A2F36;
    --chart-sub:#7A828C; --chart-edge:#FFFFFF; --chart-sep:#1A1F26;
    --chart-name:#FFFFFF; --chart-legend-bg:#FFFFFF; --chart-legend-line:#C8CDD4;
    --chart-swatch:#9AA1AA; --chart-tip-bg:#FFFFFF; --chart-tip-line:#C8CDD4;
    --chart-grid:rgba(0,0,0,0.06); --chart-bar:#FFFFFF; --chart-bar-edge:#B8C0CA;
    --chart-bar-top:#EAEFF4; --chart-bar-bot:#CBD3DD; --chart-name-col:#1A1F26;
    --chart-hatch:rgba(90,100,115,0.55);
    --chart-floor:rgba(0,0,0,0.09);
  }
  *{box-sizing:border-box; margin:0; padding:0;}
  html,body{height:100%;}
  body{
    background:var(--bg); color:var(--text);
    font:13px/1.45 'Segoe UI','Helvetica Neue',Arial,sans-serif;
    display:flex; flex-direction:column; overflow:hidden;
  }
  #topbar{
    background:var(--sidebar); height:50px; flex:0 0 auto;
    display:flex; align-items:center; gap:10px; padding:0 14px;
    border-bottom:1px solid var(--line);
  }
  #topbar h1{font-size:15px; font-weight:700; white-space:nowrap; letter-spacing:.2px;}
  #topbar h1 .tag{color:var(--accent);}
  .spacer{flex:1;}
  label.bar-label{color:var(--subtext); font-size:11px;}
  select,button{
    background:var(--card); color:var(--text); border:1px solid var(--line);
    border-radius:5px; font:inherit; font-size:12px; padding:6px 10px; cursor:pointer;
  }
  select:focus-visible,button:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  #teamSelect{font-weight:700; min-width:120px;}
  button:hover{background:var(--panel);}
  button.b-accent{color:var(--accent); font-weight:600;}
  button.b-green {color:var(--green);  font-weight:600;}
  button.b-orange{color:var(--orange); font-weight:600;}
  button.b-blue  {color:var(--blue);   font-weight:600;}
  button.b-purple{color:var(--purple); font-weight:600;}
  button.b-red   {color:var(--red);    font-weight:600;}

  #main{flex:1; display:flex; min-height:0;}
  #sidebar{
    width:268px; flex:0 0 auto; background:var(--sidebar);
    overflow-y:auto; padding:8px 12px 24px; border-right:1px solid var(--line);
  }
  #sidebar::-webkit-scrollbar{width:9px;}
  #sidebar::-webkit-scrollbar-thumb{background:#3a3a3a; border-radius:5px;}
  #chartwrap{flex:1; min-width:0; position:relative; background:var(--chart-bg);}
  #chart{position:absolute; inset:10px; width:calc(100% - 20px); height:calc(100% - 20px);}

  .section-h{
    display:flex; align-items:center; justify-content:space-between;
    margin:16px 0 6px; font-size:12px; font-weight:700; letter-spacing:.4px;
    user-select:none;
  }
  .section-h.collapsible{cursor:pointer;}
  .section-h .left{display:flex; align-items:center; gap:7px;}
  .section-h .chev{
    display:inline-block; width:10px; transition:transform .15s; color:var(--subtext);
    font-size:10px;
  }
  .section-h.collapsed .chev{transform:rotate(-90deg);}
  .section-h .count{
    color:var(--subtext); font-weight:600; font-size:10px;
    background:var(--card); border-radius:9px; padding:1px 7px;
  }
  .section-h .add-btn{padding:3px 9px; font-size:11px;}
  .section-h .plus-btn{
    width:26px; height:26px; padding:0; line-height:1;
    display:flex; align-items:center; justify-content:center;
    font-size:18px; font-weight:400; color:var(--subtext);
    background:var(--card); border:1px solid var(--line); border-radius:6px;
  }
  .section-h .plus-btn:hover{background:var(--panel); color:var(--text);}
  .collapse-body.collapsed{display:none;}
  .muted{color:var(--subtext); font-size:11px; padding:2px 4px;}

  .card{background:var(--card); border-radius:7px; padding:8px 10px; margin:5px 0;}
  .card .row{display:flex; align-items:center; justify-content:space-between; gap:6px;}
  .card .name{font-weight:700; font-size:12px;}
  .card .meta{color:var(--subtext); font-size:11px; white-space:nowrap;}

  .seg{display:flex; gap:4px; margin-top:6px;}
  .seg button{
    flex:1; padding:3px 0; font-size:11px; border-radius:5px;
    color:var(--subtext); border-color:#3a3a3a; background:var(--sidebar);
  }
  .seg button.on-pending {color:#111; background:var(--yellow); border-color:var(--yellow); font-weight:700;}
  .seg button.on-accepted{color:#111; background:var(--green);  border-color:var(--green);  font-weight:700;}
  .seg button.on-declined{color:#111; background:var(--red);    border-color:var(--red);    font-weight:700;}

  .x-btn{background:none; border:none; color:var(--red); font-size:13px; padding:0 4px; cursor:pointer;}
  .undo-btn{background:none; border:none; color:var(--accent); font-size:11px; padding:0 4px; cursor:pointer;}
  .ext-year{font:11px/1.6 Consolas,Menlo,monospace; color:var(--text); padding-left:4px;}

  /* Yearly summary status boxes */
  #totals{display:flex; flex-direction:column; gap:4px; padding:0; background:none;}
  .ysum-cell{
    display:flex; align-items:center; gap:8px;
    background:var(--card); border:1px solid var(--line); border-radius:6px;
    padding:6px 9px; cursor:default;
    font:11px/1.3 Consolas,Menlo,monospace; white-space:nowrap;
  }
  .ysum-cell:hover{box-shadow:0 0 0 1px var(--accent);}
  .ysum-cell .ys-yr{color:var(--text); width:52px;}
  .ysum-cell .ys-tot{color:var(--subtext); width:54px;}
  .ysum-cell .ys-status{flex:1; text-align:right; font-family:'Segoe UI',Arial,sans-serif; font-weight:600; font-size:11px;}
  .ysum-tip{
    position:fixed; z-index:100; pointer-events:none;
    background:var(--panel); border:1px solid var(--line); border-radius:8px;
    padding:9px 11px; box-shadow:0 6px 20px rgba(0,0,0,.4);
    font:11px/1.4 'Segoe UI',Arial,sans-serif;
  }
  .ysum-tip .yt-head{color:var(--text); font-weight:700; font-size:11px; margin-bottom:6px;
    padding-bottom:5px; border-bottom:1px solid var(--line);}
  .ysum-tip .yt-table{border-collapse:collapse; font:11px/1.5 Consolas,Menlo,monospace;}
  .ysum-tip .yt-lbl{color:var(--text); padding:1px 12px 1px 0; white-space:nowrap;}
  .ysum-tip .yt-dot{display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:6px; vertical-align:middle;}
  .ysum-tip .yt-val{text-align:right; padding:1px 8px 1px 0; font-weight:700; color:var(--text);}
  .ysum-tip .yt-st{color:var(--subtext); font-size:10px;}

  dialog{
    background:var(--panel); color:var(--text); border:1px solid #3a3a3a;
    border-radius:9px; padding:18px 20px; min-width:380px; max-width:460px;
  }
  dialog::backdrop{background:rgba(0,0,0,.55);}
  dialog h2{font-size:14px; margin-bottom:12px;}
  dialog .f-label{font-size:12px; font-weight:700; margin:12px 0 4px;}
  dialog select,dialog input[type=text],dialog input[type=number]{
    width:100%; background:var(--card); color:var(--text);
    border:1px solid #3a3a3a; border-radius:5px; padding:6px 8px; font:inherit;
  }
  dialog input[type=number]{width:90px;}
  .chk-row{display:flex; flex-wrap:wrap; gap:10px;}
  .chk-row label,.radio-row label{display:flex; align-items:center; gap:5px; font-size:12px; cursor:pointer;}
  .radio-row{display:flex; gap:16px;}
  .sal-row{display:flex; align-items:center; gap:6px; margin:4px 0; font-size:12px;}
  .ext-row{display:flex; align-items:center; gap:8px; margin:6px 0; font-size:12px;}
  .ext-row .yr{width:62px; font-weight:600; color:var(--text);}
  .ext-row input[type=number]{width:78px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:5px 7px; font:inherit;}
  .unit-tog{display:flex; border:1px solid var(--line); border-radius:5px; overflow:hidden;}
  .unit-tog button{border:none; border-radius:0; padding:5px 10px; font-size:12px;
    background:var(--sidebar); color:var(--subtext); cursor:pointer;}
  .unit-tog button.on{background:var(--accent); color:#fff; font-weight:700;}
  .ext-row .calc{color:var(--subtext); font-size:11px; min-width:96px;}
  .dlg-btns{display:flex; justify-content:flex-end; gap:10px; margin-top:16px;}
  .err{color:var(--red); font-size:11px; min-height:15px; margin-top:8px;}

  body.dragging::after{
    content:"Drop a CSV to add it as the current team"; position:fixed; inset:0; z-index:50;
    display:flex; align-items:center; justify-content:center;
    background:rgba(20,20,20,.82); color:var(--text); font-size:20px; font-weight:700;
    border:3px dashed var(--accent);
  }
  @media (prefers-reduced-motion: no-preference){ button{transition:background .12s;} }
</style>
</head>
<body>

<div id="topbar">
  <h1>NBA Salary Chart <span class="tag">Studio</span></h1>
  <label class="bar-label" for="teamSelect">Team</label>
  <select id="teamSelect" aria-label="Team"></select>
  <label class="bar-label" for="startYear">From</label>
  <select id="startYear" aria-label="First season to display"></select>
  <span class="spacer"></span>
  <button class="b-accent" id="openBtn">Add CSV…</button>
  <input type="file" id="fileInput" accept=".csv,text/csv" hidden>
  <button class="b-orange" id="resetBtn">Reset moves</button>
  <button class="b-green" id="exportBtn">Export PNG</button>
  <button id="themeBtn" title="Toggle light / dark">☀ Light</button>
</div>

<div id="main">
  <div id="sidebar">
    <div class="section-h"><div class="left">YEARLY SUMMARY</div></div>
    <div id="totals"></div>

    <div class="section-h collapsible" id="optHeader">
      <div class="left"><span class="chev">▼</span> OPTIONS</div>
      <span class="count" id="optCount"></span>
    </div>
    <div class="collapse-body" id="optionsBody"><div id="optionsList"></div></div>

    <div class="section-h" style="color:var(--blue)">
      <div class="left">EXTENSIONS</div>
      <button class="plus-btn" id="addExtBtn" title="Add extension" aria-label="Add extension">+</button></div>
    <div id="extList"></div>

    <div class="section-h" style="color:var(--green)">
      <div class="left">ADD PLAYER</div>
      <button class="plus-btn" id="addPlayerBtn" title="Add player" aria-label="Add player">+</button></div>
    <div id="addPlayerList"></div>

    <div class="section-h" style="color:var(--red)">
      <div class="left">REMOVE PLAYER</div>
      <button class="plus-btn" id="addTradeBtn" title="Remove player" aria-label="Remove player">+</button></div>
    <div id="tradeList"></div>
  </div>
  <div id="chartwrap"><canvas id="chart"></canvas></div>
</div>

<dialog id="extDialog">
  <h2>Add extension</h2>
  <div class="f-label">Player (expiring contracts)</div>
  <select id="extPlayer"></select>
  <div class="f-label">Extension years (consecutive, starting from the first)</div>
  <div class="chk-row" id="extYears"></div>
  <div class="f-label" id="extSalHdr" style="display:none">Salary per year</div>
  <div id="extSalaries" style="margin-top:6px"></div>
  <label style="display:flex;gap:6px;align-items:center;margin-top:12px;font-size:12px">
    <input type="checkbox" id="extOptFlag"> Final selected year is an option year</label>
  <div class="err" id="extErr"></div>
  <div class="dlg-btns">
    <button id="extCancel">Cancel</button>
    <button class="b-green" id="extSubmit">Add extension</button></div>
</dialog>

<dialog id="addPlayerDialog">
  <h2>Add player from another team</h2>
  <div class="f-label">From team</div>
  <select id="addPlayerTeam"></select>
  <div class="f-label">Player</div>
  <select id="addPlayerSelect"></select>
  <div class="f-label">Join in season</div>
  <select id="addPlayerYear"></select>
  <div id="addPlayerPreview" class="muted" style="margin-top:8px"></div>
  <div class="err" id="addPlayerErr"></div>
  <div class="dlg-btns">
    <button id="addPlayerCancel">Cancel</button>
    <button class="b-green" id="addPlayerSubmit">Add to roster</button></div>
</dialog>

<dialog id="tradeDialog">
  <h2>Remove player</h2>
  <div class="f-label">Player</div><select id="tradePlayer"></select>
  <div class="f-label">Remove from this year onward</div><select id="tradeYear"></select>
  <div class="err" id="tradeErr"></div>
  <div class="dlg-btns">
    <button id="tradeCancel">Cancel</button>
    <button class="b-red" id="tradeSubmit">Remove player</button></div>
</dialog>

<script id="teamData" type="application/json">/*__TEAM_DATA__*/</script>

<script>
"use strict";
/* ════ THEME / CONSTANTS ════ */
const css=getComputedStyle(document.documentElement);
const C=n=>css.getPropertyValue(n).trim();
/* Chart colors live in CSS vars so the light/dark toggle updates them.
   THEME is refreshed from the live computed styles whenever the theme flips. */
const THEME={};
function refreshTheme(){
  const cs=getComputedStyle(document.body);
  const g=n=>cs.getPropertyValue(n).trim();
  THEME.bg=g("--chart-bg"); THEME.panel=g("--chart-panel");
  THEME.text=g("--chart-text"); THEME.sub=g("--chart-sub");
  THEME.bar=g("--chart-bar"); THEME.barEdge=g("--chart-bar-edge");
  THEME.sep=g("--chart-sep"); THEME.name=g("--chart-name-col")||g("--chart-name");
  THEME.legendBg=g("--chart-legend-bg"); THEME.legendLine=g("--chart-legend-line");
  THEME.swatch=g("--chart-swatch"); THEME.tipBg=g("--chart-tip-bg");
  THEME.tipLine=g("--chart-tip-line"); THEME.grid=g("--chart-grid");
  THEME.hatch=g("--chart-hatch"); THEME.floor=g("--chart-floor");
  THEME.accent=g("--accent");
}
const GREEN=C("--green"), RED=C("--red"), YELLOW=C("--yellow"),
      BLUE=C("--blue"), PURPLE=C("--purple"), SUBTEXT=C("--subtext"), TEXT=C("--text");
const BODYF="'Segoe UI','Helvetica Neue',Arial,sans-serif";

const THRESHOLDS={
  2025:[154.647,187.895,195.945,207.824], 2026:[165.000,201.000,209.000,222.000],
  2027:[173.250,210.499,219.481,232.789], 2028:[181.913,221.024,230.455,244.428],
  2029:[191.009,232.076,241.979,256.651], 2030:[201.774,245.155,255.616,271.115],
  2031:[211.863,257.414,268.398,284.672], 2032:[222.456,270.284,281.817,298.904],
  2033:[233.579,283.798,295.908,313.849], 2034:[245.258,297.988,310.703,329.542],
};
const FLOOR_PCT=0.90;   // salary floor = 90% of the cap

// ── Single source of truth for the threshold colour system ────────────
// Each tier line, top to bottom. `val(t)` extracts the dollar value (in $M)
// from a THRESHOLDS row [cap,tax,a1,a2]. `rgb` is used for shaded bands.
const TIERS=[
  {key:"2nd Apron",  line:"#C93040", rgb:"201,48,64",  val:t=>t[3]},
  {key:"1st Apron",  line:"#C97820", rgb:"201,120,32", val:t=>t[2]},
  {key:"Luxury Tax", line:"#C9B820", rgb:"201,184,32", val:t=>t[1]},
  {key:"Salary Cap", line:"#20C940", rgb:"32,201,64",  val:t=>t[0]},
  {key:"Salary Floor", line:"#3B82F6", rgb:"59,130,246", val:t=>t[0]*FLOOR_PCT},
];
// Status (region a payroll falls into) → colour of that region's band/line.
const STATUS_COLOR={
  "2nd Apron":"#C93040", "1st Apron":"#C97820", "Above Tax":"#C9B820",
  "Below Tax":"#20C940",       // above cap, below tax → green region
  "Below Cap":"#3B82F6",       // above floor, below cap → blue region
  "Below Floor":"#9AA1AA",     // under the floor → neutral (white region)
  "—":"#8A8A8A",
};
// Background tint (rgb) for each status, matching the chart region.
const STATUS_RGB={
  "2nd Apron":"201,48,64", "1st Apron":"201,120,32", "Above Tax":"201,184,32",
  "Below Tax":"32,201,64", "Below Cap":"59,130,246", "Below Floor":"154,161,170",
};
const REF_LINES=[["Salary Cap",0,"#20C940"],["Luxury Tax",1,"#C9B820"],
                 ["1st Apron",2,"#C97820"],["2nd Apron",3,"#C93040"]];

/* ════ DATA LAYER ════ */
function parseSalary(v){v=(v||"").trim().replace(/[$,]/g,""); return v?parseFloat(v):null;}
function parseCSVText(text){
  const rows=[]; let row=[],cell="",inQ=false;
  for(let i=0;i<text.length;i++){const c=text[i];
    if(inQ){ if(c==='"'){ if(text[i+1]==='"'){cell+='"';i++;} else inQ=false;} else cell+=c; }
    else if(c==='"') inQ=true;
    else if(c===',') {row.push(cell);cell="";}
    else if(c==='\n'){row.push(cell);rows.push(row);row=[];cell="";}
    else if(c!=='\r') cell+=c;}
  if(cell!==""||row.length){row.push(cell);rows.push(row);}
  return rows;
}
function loadCSV(text){
  const raw=parseCSVText(text);
  const hIdx=raw.findIndex(r=>r[0]&&r[0].trim()==="Player");
  if(hIdx<0) throw new Error('No header row starting with "Player" found.');
  const headers=raw[hIdx].map(h=>h.trim());
  const yearCols=headers.filter(h=>/^\d{4}-\d{2}/.test(h));
  if(!yearCols.length) throw new Error("No season columns (e.g. 2025-26) found.");
  const guaranteedCol=headers[headers.length-1];
  const players=[];
  for(const r of raw.slice(hIdx+1)){
    if(!r.some(c=>c&&c.trim())) continue;
    const d={}; headers.forEach((h,i)=>d[h]=(r[i]||"").trim());
    if(d["Player"]) players.push(d);
  }
  return {yearCols,players,guaranteedCol};
}

/* Parse a team's CSV (from the embedded TEAMS data) into player contract dicts. */
function teamPlayers(csvText){
  const {yearCols,players,guaranteedCol}=loadCSV(csvText);
  const active=players.filter(p=>yearCols.some(yc=>parseSalary(p[yc])));
  return {yearCols,players:active,guaranteedCol};
}

class RosterState{
  constructor(csvText,name){
    const {yearCols,players,guaranteedCol}=loadCSV(csvText);
    this.teamName=name; this.yearCols=yearCols; this.guaranteedCol=guaranteedCol;
    this.basePlayers=players.filter(p=>yearCols.some(yc=>parseSalary(p[yc])));
    this.addedPlayers=[];                 // incoming players acquired from other teams
    this.addedFrom=new Map();             // player name -> source team label
    this.active=this.basePlayers.slice();
    this.optionStates=new Map(); this.extensions=new Map();
    this.extensionOptions=new Set(); this.extensionLabels=new Map();
    this.traded=new Map(); this.displayStart=0;
    this.refreshOptions();
  }
  refreshOptions(){
    // Re-derive the active roster + option list (call after adding/removing players).
    this.active=this.basePlayers.concat(this.addedPlayers);
    this.optionsFound=this.detectOptions();
    for(const [n,y] of this.optionsFound)
      if(!this.optionStates.has(this.key(n,y))) this.optionStates.set(this.key(n,y),"pending");
  }
  addPlayer(playerDict, fromTeam){
    // playerDict matches the CSV player shape (Player, Age, <year>…, Guaranteed).
    // De-dupe by name; if already present, replace it.
    const name=playerDict["Player"];
    this.addedPlayers=this.addedPlayers.filter(p=>p["Player"]!==name);
    this.addedPlayers.push(playerDict);
    if(fromTeam) this.addedFrom.set(name,fromTeam);
    this.refreshOptions();
  }
  removeAddedPlayer(name){
    this.addedPlayers=this.addedPlayers.filter(p=>p["Player"]!==name);
    this.addedFrom.delete(name);
    // clear any moves attached to that player
    for(const k of [...this.optionStates.keys()]) if(k.startsWith(name+"|")) this.optionStates.delete(k);
    this.removeExtensionsFor(name);
    this.traded.delete(name);
    this.refreshOptions();
  }
  isAddedPlayer(name){return this.addedFrom.has(name);}
  key(n,y){return n+"|"+y;}
  displayYears(){return this.yearCols.slice(this.displayStart);}
  determineOption(p,yc){
    const sal=parseSalary(p[yc]); if(sal===null) return false;
    const guar=parseSalary(p[this.guaranteedCol]); if(guar===null) return true;
    let r=0;
    for(const y of this.yearCols){const s=parseSalary(p[y]); if(s===null)continue;
      r+=s; if(y===yc) return r>guar+1;}
    return false;
  }
  detectOptions(){const out=[];
    for(const yc of this.yearCols) for(const p of this.active)
      if(this.determineOption(p,yc)){const s=parseSalary(p[yc]); if(s) out.push([p["Player"],yc,s]);}
    return out;
  }
  optionYearsFor(n){return this.optionsFound.filter(o=>o[0]===n).map(o=>o[1]);}
  setOptionState(name,year,state){
    this.optionStates.set(this.key(name,year),state);
    const yrs=this.optionYearsFor(name),i=yrs.indexOf(year);
    if(state==="declined") for(const l of yrs.slice(i+1)) this.optionStates.set(this.key(name,l),"declined");
    if(state==="accepted") for(const e of yrs.slice(0,i)) this.optionStates.set(this.key(name,e),"accepted");
  }
  isDeclined(n,y){return this.optionStates.get(this.key(n,y))==="declined";}
  isAccepted(n,y){return this.optionStates.get(this.key(n,y))==="accepted";}
  expiringContracts(){
    const last=this.yearCols[this.yearCols.length-1],out=[];
    for(const p of this.active){const name=p["Player"];
      const filled=this.yearCols.filter(yc=>(parseSalary(p[yc])&&!this.isDeclined(name,yc))||this.extensions.has(this.key(name,yc)));
      if(!filled.length) continue;
      const lastYr=filled[filled.length-1];
      if(lastYr!==last){const sal=parseSalary(p[lastYr])??this.extensions.get(this.key(name,lastYr))??0; out.push([name,lastYr,sal]);}
    }
    out.sort((a,b)=>this.yearCols.indexOf(a[1])-this.yearCols.indexOf(b[1])); return out;
  }
  addExtension(name,year,salary,isOption,label){
    this.extensions.set(this.key(name,year),salary);
    this.extensionLabels.set(this.key(name,year),label);
    if(isOption){
      this.extensionOptions.add(this.key(name,year));
      if(!this.optionStates.has(this.key(name,year)))
        this.optionStates.set(this.key(name,year),"pending");
    }
  }
  removeExtensionsFor(name){
    for(const k of [...this.extensions.keys()]) if(k.startsWith(name+"|")){
      this.extensions.delete(k); this.extensionLabels.delete(k); this.extensionOptions.delete(k);}
  }
  rosterOnBooks(){const out=[];
    for(const p of this.active){const name=p["Player"];
      const yrs=this.yearCols.filter(yc=>(parseSalary(p[yc])&&!this.isDeclined(name,yc))||this.extensions.has(this.key(name,yc)));
      if(yrs.length) out.push([name,yrs]);}
    out.sort((a,b)=>this.yearCols.indexOf(a[1][a[1].length-1])-this.yearCols.indexOf(b[1][b[1].length-1])); return out;
  }
  trade(n,y){this.traded.set(n,y);} undoTrade(n){this.traded.delete(n);}
  isYearRemoved(name,yc){
    return this.traded.has(name) &&
      this.yearCols.indexOf(yc) >= this.yearCols.indexOf(this.traded.get(name));
  }
  // Options still in effect: CSV-detected options plus any option year created
  // by an extension. Hide any whose player+year was removed via a trade cutoff.
  visibleOptions(){
    const out=this.optionsFound.filter(([n,y])=>!this.isYearRemoved(n,y));
    // add extension-created option years (not already in optionsFound)
    const have=new Set(out.map(([n,y])=>this.key(n,y)));
    for(const k of this.extensionOptions){
      if(have.has(k)) continue;
      const [n,y]=k.split("|");
      if(this.isYearRemoved(n,y)) continue;
      const s=this.extensions.get(k);
      if(s) out.push([n,y,s]);
    }
    // sort by season then by name for stable display
    out.sort((a,b)=>{
      const d=this.yearCols.indexOf(a[1])-this.yearCols.indexOf(b[1]);
      return d!==0?d:a[0].localeCompare(b[0]);
    });
    return out;
  }
  chartData(){
    const data=new Map();
    for(const yc of this.displayYears()){const entries=[];
      for(const p of this.active){const name=p["Player"];
        const k=this.key(name,yc);
        const csvSal=parseSalary(p[yc]); const extSal=this.extensions.get(k)??null;
        const isExtOpt=this.extensionOptions.has(k);
        let sal,fromExt;
        if(this.isDeclined(name,yc)){
          // A declined option year is gone — unless it was re-signed via a
          // (non-option) extension for that same year.
          sal = (extSal!==null && !isExtOpt) ? extSal : null;
          fromExt = sal!==null;
        }else{
          sal=csvSal??extSal; fromExt=csvSal===null&&extSal!==null;
        }
        if(!sal) continue;
        if(this.traded.has(name)&&this.yearCols.indexOf(yc)>=this.yearCols.indexOf(this.traded.get(name))) continue;
        const opt=fromExt
          ? (isExtOpt && !this.isAccepted(name,yc))
          : (this.determineOption(p,yc)&&!this.isAccepted(name,yc));
        entries.push([name,sal,opt]);
      }
      entries.sort((a,b)=>(a[2]-b[2])||(b[1]-a[1]));
      if(entries.length) data.set(yc,entries);
    }
    return data;
  }
  yearTotals(){const t=new Map();
    for(const [yc,es] of this.chartData()) t.set(yc,es.reduce((s,e)=>s+e[1],0)); return t;}
  // Per-displayed-year summary used by both the sidebar panel and the PNG export.
  yearlySummary(){
    const totals=this.yearTotals(), data=this.chartData(), out=[];
    for(const yc of this.displayYears()){
      if(!totals.has(yc)) continue;
      const tm=totals.get(yc)/1e6, t=THRESHOLDS[parseInt(yc)];
      let status="—";
      let breakdown=null;
      if(t){const [cap,tax,a1,a2]=t; const floor=cap*FLOOR_PCT;
        if(tm>a2) status="2nd Apron";
        else if(tm>a1) status="1st Apron";
        else if(tm>tax) status="Above Tax";
        else if(tm>cap) status="Below Tax";   // above cap, below tax
        else if(tm>floor) status="Below Cap"; // above floor, below cap
        else status="Below Floor";            // under the salary floor
        // margin vs every line (positive = above the line)
        breakdown=[
          {label:"2nd Apron",    value:tm-a2},
          {label:"1st Apron",    value:tm-a1},
          {label:"Luxury Tax",   value:tm-tax},
          {label:"Salary Cap",   value:tm-cap},
          {label:"Salary Floor", value:tm-floor},
        ];
      }
      out.push({yc, total:tm, status, breakdown, players:(data.get(yc)||[]).length});
    }
    return out;
  }
  resetMoves(){
    this.optionStates=new Map();
    this.addedPlayers=[]; this.addedFrom.clear();
    this.extensions.clear(); this.extensionOptions.clear(); this.extensionLabels.clear(); this.traded.clear();
    this.refreshOptions();
    for(const [n,y] of this.optionsFound) this.optionStates.set(this.key(n,y),"pending");
  }
  summarySections(){
    const acc=[],pen=[],dec=[];
    for(const [n,y,s] of this.visibleOptions()){
      if(this.isAccepted(n,y)) acc.push([n,y,s]);
      else if(this.isDeclined(n,y)) dec.push([n,y,s]);
      else pen.push([n,y,s]);}
    const exts=[...this.extensions.entries()].map(([k,s])=>{const [n,y]=k.split("|"); return [n,y,s,this.extensionOptions.has(k)];});
    // Acquired players: name, source team, and per-year contract rows.
    const added=this.addedPlayers.map(p=>{
      const name=p["Player"];
      const rows=this.yearCols
        .map(yc=>({yc,sal:parseSalary(p[yc]),opt:this.determineOption(p,yc)||this.extensionOptions.has(this.key(name,yc))}))
        .filter(r=>r.sal);
      const total=rows.reduce((a,r)=>a+r.sal,0);
      return {name, from:this.addedFrom.get(name)||"", total, rows};
    });
    // Removed players: name, cutoff year, and the per-year salaries coming off.
    const trades=[...this.traded.entries()].map(([name,fromYr])=>{
      const pl=this.active.find(q=>q["Player"]===name);
      const fromIdx=this.yearCols.indexOf(fromYr);
      const rows=[];
      if(pl) for(const yc of this.yearCols){
        if(this.yearCols.indexOf(yc)<fromIdx) continue;
        const sal=parseSalary(pl[yc])??this.extensions.get(this.key(name,yc))??null;
        if(sal) rows.push({yc,sal});
      }
      return {name, fromYr, rows};
    });
    return {acc,pen,dec,exts,added,trades};
  }
}

/* ════ DARK CHART RENDERING (original style) ════ */
function makeHatch(scale){
  const c=document.createElement("canvas"); c.width=c.height=8*scale;
  const x=c.getContext("2d");
  x.strokeStyle=(THEME.hatch||"rgba(102,102,102,0.55)"); x.lineWidth=1.2*scale;
  for(const o of [-8,0,8]){x.beginPath(); x.moveTo(o*scale,8*scale); x.lineTo((o+8)*scale,0); x.stroke();}
  return x.canvas;
}
function hyphenSplit(name){const parts=[];
  for(const w of name.split(" ")){const i=w.indexOf("-");
    if(i>=0){parts.push(w.slice(0,i+1));parts.push(w.slice(i+1));} else parts.push(w);}
  return parts;}
function bestFontSize(ctx,lines,maxW,maxH,fam){
  const n=lines.length; let fs=Math.min(72,Math.floor(maxH*0.88/(1.35*n)));
  for(;fs>=4;fs--){ctx.font=`bold ${fs}px ${fam}`;
    const w=Math.max(...lines.map(l=>ctx.measureText(l).width));
    if(w<=maxW) return fs;}
  return null;}
function fitLabel(ctx,name,cx,top,h,w){
  if(h<7) return;
  const words=hyphenSplit(name);
  const cands=[words.join("\n")];
  if(words.length>=2) cands.push(words[0]+"\n"+words[words.length-1]);
  cands.push(name);
  const seen=new Set(); let best=null,bestFs=0,bestArea=0;
  for(const c of cands){ if(seen.has(c))continue; seen.add(c);
    const lines=c.split("\n"); const fs=bestFontSize(ctx,lines,w*0.85,h,BODYF);
    if(fs===null) continue;
    ctx.font=`bold ${fs}px ${BODYF}`;
    const tw=Math.max(...lines.map(l=>ctx.measureText(l).width)), th=lines.length*fs*1.35;
    if(tw*th>bestArea){bestArea=tw*th; best=lines; bestFs=fs;}}
  if(!best) return;
  ctx.font=`bold ${bestFs}px ${BODYF}`; ctx.fillStyle=THEME.name;
  ctx.textAlign="center"; ctx.textBaseline="middle";
  const lh=bestFs*1.2, y0=top+h/2-(best.length-1)*lh/2;
  best.forEach((l,i)=>ctx.fillText(l,cx,y0+i*lh));
}

function renderChart(ctx,state,x0,y0,W,H,s){
  refreshTheme();
  ctx.save(); ctx.translate(x0,y0);
  ctx.fillStyle=THEME.bg; ctx.fillRect(0,0,W,H);

  const data=state.chartData();
  const years=state.displayYears().filter(y=>data.has(y));
  const mL=58*s,mR=86*s,mT=34*s,mB=34*s;
  const pw=W-mL-mR, ph=H-mT-mB;

  if(!years.length){
    ctx.fillStyle=THEME.sub; ctx.font=`${15*s}px ${BODYF}`;
    ctx.textAlign="center"; ctx.textBaseline="middle";
    ctx.fillText("No salary data — choose a team or add a CSV", W/2, H/2);
    ctx.restore(); return;
  }

  // panel
  ctx.fillStyle=THEME.panel; ctx.fillRect(mL,mT,pw,ph);

  // y scale
  let maxV=0;
  for(const yc of years){
    maxV=Math.max(maxV,data.get(yc).reduce((a,e)=>a+e[1],0)/1e6);
    const t=THRESHOLDS[parseInt(yc)]; if(t) maxV=Math.max(maxV,t[3]);}
  maxV*=1.07;
  const Y=v=>mT+ph-(v/maxV)*ph;
  const slotW=pw/years.length, barW=Math.min(slotW*0.62,150*s), X=i=>mL+slotW*(i+0.5);

  // ── Shaded threshold regions (stepped per season, behind the bars) ──
  // Bands are defined by lower/upper value-functions (in $M). Colours come
  // from the single STATUS/TIER colour system so chart + summary always match.
  const fl=t=>t[0]*FLOOR_PCT;
  const BANDS=[
    {lo:()=>0,        hi:fl,             fill:THEME.floor},               // below floor → grey/white
    {lo:fl,           hi:t=>t[0],        rgb:STATUS_RGB["Below Cap"]},    // floor→cap → blue
    {lo:t=>t[0],      hi:t=>t[1],        rgb:STATUS_RGB["Below Tax"]},    // above cap → green
    {lo:t=>t[1],      hi:t=>t[2],        rgb:STATUS_RGB["Above Tax"]},    // above tax → yellow
    {lo:t=>t[2],      hi:t=>t[3],        rgb:STATUS_RGB["1st Apron"]},    // 1st apron → orange
    {lo:t=>t[3],      hi:()=>maxV,       rgb:STATUS_RGB["2nd Apron"]},    // 2nd apron → red
  ];
  const clampY=v=>Math.max(mT, Math.min(mT+ph, Y(v)));
  // gap between adjacent seasons' shaded regions (each side inset)
  const bandPad=Math.min(slotW*0.10, 16*s);
  for(const band of BANDS){
    years.forEach((yc,i)=>{
      const t=THRESHOLDS[parseInt(yc)]; if(!t) return;
      const lo=band.lo(t), hi=band.hi(t);
      const left=X(i)-slotW/2+bandPad, right=X(i)+slotW/2-bandPad;
      const yTop=clampY(hi), yBot=clampY(lo);
      if(yBot-yTop<=0) return;
      ctx.fillStyle=band.fill || `rgba(${band.rgb},0.10)`;
      ctx.fillRect(left,yTop,right-left,yBot-yTop);
    });
  }

  // y ticks
  const step=maxV>320?100:50;
  ctx.font=`${9*s}px ${BODYF}`; ctx.fillStyle=THEME.sub;
  ctx.textAlign="right"; ctx.textBaseline="middle";
  for(let v=0;v<=maxV;v+=step) ctx.fillText(`$${v}M`,mL-8*s,Y(v));
  ctx.save(); ctx.translate(14*s,mT+ph/2); ctx.rotate(-Math.PI/2);
  ctx.textAlign="center"; ctx.fillText("Total Payroll ($ millions)",0,0); ctx.restore();

  // reference lines (one discrete segment per season, matching the band gap)
  ctx.font=`italic ${9*s}px ${BODYF}`;
  for(const tier of TIERS){
    const pts=[]; years.forEach((yc,i)=>{const t=THRESHOLDS[parseInt(yc)]; if(t) pts.push([i,tier.val(t)]);});
    if(!pts.length) continue;
    ctx.strokeStyle=tier.line; ctx.lineWidth=1.4*s;
    for(const [xi,v] of pts){
      const left=X(xi)-slotW/2+bandPad, right=X(xi)+slotW/2-bandPad;
      ctx.beginPath(); ctx.moveTo(left,Y(v)); ctx.lineTo(right,Y(v)); ctx.stroke();
    }
    const [lxi,lv]=pts[pts.length-1];
    ctx.fillStyle=tier.line; ctx.textAlign="left"; ctx.textBaseline="bottom";
    ctx.fillText(tier.key,X(lxi)+slotW/2+6*s,Y(lv)-2*s);
  }

  // bars
  const hatch=ctx.createPattern(makeHatch(s),"repeat");
  years.forEach((yc,i)=>{let bottom=0; const cx=X(i);
    for(const [name,sal,isOpt] of data.get(yc)){
      const top=Y((bottom+sal)/1e6), h=Y(bottom/1e6)-top, x=cx-barW/2;
      ctx.fillStyle=THEME.bar; ctx.fillRect(x,top,barW,h);
      if(isOpt){ctx.fillStyle=hatch; ctx.fillRect(x,top,barW,h);}
      // separator line at top of segment
      ctx.fillStyle=THEME.sep; ctx.fillRect(x,top-0.6*s,barW,1.2*s);
      bottom+=sal;
    }
    // x label (centered under the bar)
    ctx.font=`600 ${12*s}px ${BODYF}`; ctx.textAlign="center"; ctx.textBaseline="top"; ctx.fillStyle=THEME.text;
    ctx.fillText(yc,cx,mT+ph+8*s);
  });

  // names
  years.forEach((yc,i)=>{let bottom=0; const cx=X(i);
    for(const [name,sal] of data.get(yc)){
      const top=Y((bottom+sal)/1e6), h=Y(bottom/1e6)-top;
      fitLabel(ctx,name,cx,top,h,barW);
      bottom+=sal;}
  });

  // legend
  const lw=168*s,lh=20*s,lx=mL+pw-lw-10*s,ly=mT+10*s;
  ctx.fillStyle=THEME.legendBg; ctx.strokeStyle=THEME.legendLine; ctx.lineWidth=1*s;
  ctx.fillRect(lx,ly,lw,lh); ctx.strokeRect(lx,ly,lw,lh);
  ctx.fillStyle=THEME.swatch; ctx.fillRect(lx+7*s,ly+5*s,14*s,10*s);
  ctx.fillStyle=hatch;  ctx.fillRect(lx+7*s,ly+5*s,14*s,10*s);
  ctx.strokeStyle=THEME.sep; ctx.strokeRect(lx+7*s,ly+5*s,14*s,10*s);
  ctx.fillStyle=THEME.text; ctx.font=`${9*s}px ${BODYF}`;
  ctx.textAlign="left"; ctx.textBaseline="middle";
  ctx.fillText("Option / Non-Guaranteed",lx+27*s,ly+lh/2);

  // Interactive Hover Tooltip Render
  if (typeof activeTooltip !== 'undefined' && activeTooltip) {
    const t = activeTooltip;
    ctx.save();
    
    // Calculate Cap Percentage dynamically using the THRESHOLDS lookup
    const yrInt = parseInt(t.year);
    const cap = THRESHOLDS[yrInt] ? THRESHOLDS[yrInt][0] : null;
    let pctStr = "";
    if (cap) {
      const pct = ((t.salary / 1e6) / cap) * 100;
      pctStr = ` (${pct.toFixed(1)}% of cap)`;
    }
    
    ctx.font = `bold ${12.5 * t.s}px ${BODYF}`;
    const txt1 = t.name;
    const txt2 = `${t.year}: $${(t.salary / 1e6).toFixed(2)}M${pctStr}`;
    const w1 = ctx.measureText(txt1).width;
    ctx.font = `${11.5 * t.s}px ${BODYF}`;
    const w2 = ctx.measureText(txt2).width;
    const boxW = Math.max(w1, w2) + 16 * t.s;
    const boxH = 44 * t.s;
    
    let tX = t.mx + 12 * t.s;
    let tY = t.my + 12 * t.s;
    if (tX + boxW > W) tX = t.mx - boxW - 12 * t.s;
    if (tY + boxH > H) tY = t.my - boxH - 12 * t.s;
    
    ctx.fillStyle = THEME.tipBg;
    ctx.strokeStyle = THEME.tipLine;
    ctx.lineWidth = 1 * t.s;
    ctx.fillRect(tX, tY, boxW, boxH);
    ctx.strokeRect(tX, tY, boxW, boxH);
    
    ctx.fillStyle = THEME.text;
    ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.font = `bold ${12.5 * t.s}px ${BODYF}`;
    ctx.fillText(txt1, tX + 8 * t.s, tY + 6 * t.s);
    ctx.font = `${11.5 * t.s}px ${BODYF}`;
    ctx.fillStyle = THEME.accent;
    ctx.fillText(txt2, tX + 8 * t.s, tY + 24 * t.s);
    ctx.restore();
  }

  ctx.restore();
}

/* ════ PNG EXPORT ════ */
function exportPNG(state){
  refreshTheme();
  const TX=THEME.text, SUB=THEME.sub;
  const SC=2.5;
  const years=state.displayYears().filter(y=>state.chartData().has(y));
  const chartW=Math.max(1200,years.length*220)*SC, chartH=1100*SC;
  const MONO="Consolas,Menlo,monospace";
  const {acc,pen,dec,exts,added,trades}=state.summarySections();
  const ROSTER_MAX=15;

  // Build a flat list of render items. Each item: {text,color,size,bold,cols?}
  // cols (optional) = array of {text,color,w} for aligned table rows.
  const items=[];
  const H=(t,c)=>items.push({text:t,color:c||TX,size:15,bold:true});
  const SUBH=(t)=>items.push({text:t,color:SUB,size:10,bold:true});
  const LINE=(t,c)=>items.push({text:t,color:c||TX,size:11,bold:false});
  const GAP=()=>items.push({text:"",color:TX,size:8,bold:false});
  const ROW=(cols)=>items.push({cols});

  // ── Yearly summary table ───────────────────────────────────────────
  // status name maps to which breakdown line is the "active" margin
  const statusRef={"2nd Apron":"2nd Apron","1st Apron":"1st Apron",
    "Above Tax":"Luxury Tax","Below Tax":"Salary Cap","Below Cap":"Salary Cap",
    "Below Floor":"Salary Floor"};
  H("YEARLY SUMMARY");
  ROW([{text:"SEASON",color:SUB,w:62},{text:"PAYROLL",color:SUB,w:74},
       {text:"STATUS",color:SUB,w:110},{text:"MARGIN",color:SUB,w:74},{text:"ROSTER",color:SUB,w:60}]);
  for(const r of state.yearlySummary()){
    let margin="—";
    if(r.breakdown){
      const refLbl=statusRef[r.status];
      const b=r.breakdown.find(x=>x.label===refLbl);
      if(b) margin=`${b.value>=0?"+":""}${b.value.toFixed(1)}M`;
    }
    ROW([
      {text:r.yc,color:TX,w:62},
      {text:`$${r.total.toFixed(1)}M`,color:TX,w:74},
      {text:r.status,color:STATUS_COLOR[r.status]||SUB,w:110},
      {text:margin,color:SUB,w:74},
      {text:`${r.players}/${ROSTER_MAX}`,color:SUB,w:60},
    ]);
  }

  // ── Moves (only sections where something was actively done) ────────
  // Pending options are the default state, not a move — only count decisions.
  const hasOpt=acc.length+dec.length>0;
  const anyMoves=hasOpt||exts.length||added.length||trades.length;
  GAP(); H("ROSTER MOVES");
  if(!anyMoves){
    LINE("  No moves made.",SUB);
  }else{
    if(hasOpt){
      GAP(); H("Options",TX);
      if(acc.length){SUBH("  Accepted");
        acc.forEach(([n,y,s])=>LINE(`  \u2713 ${n} ${y} ($${(s/1e6).toFixed(1)}M)`,GREEN));}
      if(dec.length){SUBH("  Declined");
        dec.forEach(([n,y,s])=>LINE(`  \u2717 ${n} ${y} ($${(s/1e6).toFixed(1)}M)`,RED));}
    }
    if(exts.length){
      GAP(); H("Extensions",BLUE);
      exts.forEach(([n,y,s,o])=>LINE(`  \u2713 ${n} ${y} ($${(s/1e6).toFixed(1)}M)${o?" (option)":""}`,BLUE));
    }
    if(added.length){
      GAP(); H("Added Players",GREEN);
      added.forEach(a=>{
        LINE(`  + ${a.name} from ${a.from} ($${(a.total/1e6).toFixed(1)}M)`,GREEN);
        a.rows.forEach(r=>LINE(`      ${r.yc}  $${(r.sal/1e6).toFixed(1)}M${r.opt?" (option)":""}`,SUB));
      });
    }
    if(trades.length){
      GAP(); H("Removed Players",RED);
      trades.forEach(t=>{
        LINE(`  \u2717 ${t.name} from ${t.fromYr} onward`,RED);
        t.rows.forEach(r=>LINE(`      ${r.yc}  \u2212$${(r.sal/1e6).toFixed(1)}M`,SUB));
      });
    }
  }

  // ── Measure width ──────────────────────────────────────────────────
  const meas=document.createElement("canvas").getContext("2d");
  let maxW=0;
  for(const it of items){
    if(it.cols){
      const w=it.cols.reduce((a,c)=>a+c.w,0);
      maxW=Math.max(maxW,w*SC);
    }else{
      meas.font=`${it.bold?"bold ":""}${it.size*SC}px ${MONO}`;
      maxW=Math.max(maxW,meas.measureText(it.text).width);
    }
  }
  const sumW=maxW+70*SC;

  const c=document.createElement("canvas"); c.width=chartW+sumW; c.height=chartH;
  const ctx=c.getContext("2d");
  ctx.fillStyle=THEME.bg; ctx.fillRect(0,0,c.width,c.height);
  renderChart(ctx,state,0,0,chartW,chartH,SC);

  // divider line between chart and summary
  ctx.strokeStyle=THEME.legendLine; ctx.lineWidth=1*SC;
  ctx.beginPath(); ctx.moveTo(chartW+12*SC,40*SC); ctx.lineTo(chartW+12*SC,chartH-40*SC); ctx.stroke();

  const x0=chartW+30*SC;
  let y=46*SC; ctx.textAlign="left"; ctx.textBaseline="top";
  for(const it of items){
    if(it.cols){
      let cx=x0;
      ctx.font=`${12*SC}px ${MONO}`;
      for(const col of it.cols){
        ctx.fillStyle=col.color;
        ctx.fillText(col.text, cx, y);
        cx+=col.w*SC;
      }
      y+=12*1.7*SC;
    }else{
      ctx.font=`${it.bold?"bold ":""}${it.size*SC}px ${MONO}`;
      ctx.fillStyle=it.color;
      ctx.fillText(it.text, x0, y);
      y+=(it.bold?it.size*1.9:it.size*1.5)*SC;
    }
  }
  c.toBlob(blob=>{const a=document.createElement("a");
    a.href=URL.createObjectURL(blob); a.download=`${state.teamName}_salaries.png`; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),5000);},"image/png");
}

/* ════ UI WIRING ════ */
const TEAMS=JSON.parse(document.getElementById("teamData").textContent);
let ST=null;
let activeTooltip = null;
const $=id=>document.getElementById(id);
const canvas=$("chart"), cctx=canvas.getContext("2d");
const fmtM=v=>`$${(v/1e6).toFixed(2)}M`;
let optionsCollapsed=false;

function redrawChart(){
  if(!ST) return;
  activeTooltip = null;
  const r=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
  canvas.width=Math.max(1,Math.round(r.width*dpr));
  canvas.height=Math.max(1,Math.round(r.height*dpr));
  renderChart(cctx,ST,0,0,canvas.width,canvas.height,dpr*(r.width<900?0.85:1));
}

function refreshTotals(){
  const box=$("totals"); box.innerHTML="";
  for(const r of ST.yearlySummary()){
    const lineClr=STATUS_COLOR[r.status]||SUBTEXT;
    const rgb=STATUS_RGB[r.status]||"138,138,138";
    const cell=document.createElement("div"); cell.className="ysum-cell";
    // background tint matches the chart region (same 0.10 alpha); a subtle
    // left border in the line colour reinforces the link.
    cell.style.background=`rgba(${rgb},0.10)`;
    cell.style.borderColor=`rgba(${rgb},0.45)`;
    cell.innerHTML=`<span class="ys-yr">${r.yc}</span>
      <span class="ys-tot">$${r.total.toFixed(0)}M</span>
      <span class="ys-status" style="color:${lineClr}">${r.status}</span>`;
    // hover tooltip with the full breakdown
    cell.onmouseenter=(e)=>showYsumTip(r,cell);
    cell.onmouseleave=hideYsumTip;
    box.appendChild(cell);
  }
  if(!box.children.length) box.innerHTML='<div class="muted">No data.</div>';
}

let ysumTipEl=null;
function hideYsumTip(){ if(ysumTipEl){ysumTipEl.remove(); ysumTipEl=null;} }
function tierLineColor(label){
  const t=TIERS.find(x=>x.key===label); return t?t.line:"#8A8A8A";
}
function showYsumTip(r,anchor){
  hideYsumTip();
  if(!r.breakdown) return;
  const tip=document.createElement("div"); tip.className="ysum-tip";
  let rows=`<div class="yt-head">${r.yc} · $${r.total.toFixed(1)}M · ${r.players}/15 players</div>`;
  rows+=`<table class="yt-table"><tbody>`;
  for(const b of r.breakdown){
    const over=b.value>=0;
    const sign = over ? "+" : "";
    const dot=tierLineColor(b.label);
    rows+=`<tr>`+
          `<td class="yt-lbl"><span class="yt-dot" style="background:${dot}"></span>${b.label}</td>`+
          `<td class="yt-val">${sign}${b.value.toFixed(1)}M</td>`+
          `<td class="yt-st">${over?"over":"under"}</td></tr>`;
  }
  rows+=`</tbody></table>`;
  tip.innerHTML=rows;
  document.body.appendChild(tip);
  const a=anchor.getBoundingClientRect();
  tip.style.left=Math.round(a.right+8)+"px";
  tip.style.top=Math.round(a.top)+"px";
  // keep on-screen
  const tb=tip.getBoundingClientRect();
  if(tb.right>window.innerWidth-8){
    tip.style.left=Math.round(a.left-tb.width-8)+"px";
  }
  if(tb.bottom>window.innerHeight-8){
    tip.style.top=Math.round(window.innerHeight-tb.height-8)+"px";
  }
  ysumTipEl=tip;
}

function rebuildSidebar(){
  refreshTotals();
  /* OPTIONS (collapsible) */
  const visOpts=ST.visibleOptions();
  $("optCount").textContent=visOpts.length||"0";
  $("optHeader").classList.toggle("collapsed",optionsCollapsed);
  $("optionsBody").classList.toggle("collapsed",optionsCollapsed);
  const ol=$("optionsList"); ol.innerHTML="";
  if(!visOpts.length) ol.innerHTML='<div class="muted">None detected in this roster.</div>';
  for(const [name,yc,sal] of visOpts){
    const cur=ST.optionStates.get(ST.key(name,yc));
    const card=document.createElement("div"); card.className="card";
    card.innerHTML=`<div class="row"><span class="name"></span>
        <span class="meta">${yc} &nbsp; ${fmtM(sal)}</span></div>
      <div class="seg">
        <button data-s="pending"  class="${cur==="pending"?"on-pending":""}">~ Pending</button>
        <button data-s="accepted" class="${cur==="accepted"?"on-accepted":""}">✓ Accept</button>
        <button data-s="declined" class="${cur==="declined"?"on-declined":""}">✗ Decline</button>
      </div>`;
    card.querySelector(".name").textContent=name;
    card.querySelectorAll(".seg button").forEach(b=>b.onclick=()=>{
      ST.setOptionState(name,yc,b.dataset.s); rebuildSidebar(); redrawChart();});
    ol.appendChild(card);
  }
  /* EXTENSIONS */
  const el=$("extList"); el.innerHTML="";
  const byP=new Map();
  for(const [k,sal] of ST.extensions){const [n,y]=k.split("|"); if(!byP.has(n))byP.set(n,[]); byP.get(n).push([y,sal]);}
  if(!byP.size) el.innerHTML='<div class="muted">None.</div>';
  for(const [name,yrs] of byP){
    yrs.sort((a,b)=>ST.yearCols.indexOf(a[0])-ST.yearCols.indexOf(b[0]));
    const card=document.createElement("div"); card.className="card";
    const head=document.createElement("div"); head.className="row";
    head.innerHTML=`<span class="name" style="color:var(--blue)"></span><button class="x-btn" title="Remove">✕</button>`;
    head.querySelector(".name").textContent=name;
    head.querySelector("button").onclick=()=>{ST.removeExtensionsFor(name); rebuildSidebar(); redrawChart();};
    card.appendChild(head);
    for(const [y,sal] of yrs){
      const opt=ST.extensionOptions.has(ST.key(name,y))?"  (option)":"";
      const d=document.createElement("div"); d.className="ext-year";
      d.textContent=`${y}   ${ST.extensionLabels.get(ST.key(name,y))||fmtM(sal)}${opt}`;
      card.appendChild(d);}
    el.appendChild(card);
  }
  /* ADD PLAYER (acquisitions) */
  const apl=$("addPlayerList"); apl.innerHTML="";
  if(!ST.addedPlayers.length) apl.innerHTML='<div class="muted">None.</div>';
  for(const p of ST.addedPlayers){
    const name=p["Player"]; const from=ST.addedFrom.get(name)||"";
    const yrSals=ST.yearCols.map(yc=>[yc,parseSalary(p[yc])]).filter(([,s])=>s);
    const card=document.createElement("div"); card.className="card";
    const head=document.createElement("div"); head.className="row";
    head.innerHTML=`<span class="name" style="color:var(--green)"></span><button class="x-btn" title="Remove acquired player">✕</button>`;
    head.querySelector(".name").textContent=name;
    head.querySelector("button").onclick=()=>{ST.removeAddedPlayer(name); rebuildSidebar(); redrawChart();};
    card.appendChild(head);
    const src=document.createElement("div"); src.className="ext-year"; src.style.color="var(--subtext)";
    src.textContent=`from ${from}`;
    card.appendChild(src);
    for(const [y,sal] of yrSals){
      const opt = (ST.determineOption(p,y) || ST.extensionOptions.has(ST.key(name,y))) ? "  (option)" : "";
      const d=document.createElement("div"); d.className="ext-year";
      d.textContent=`${y}   ${fmtM(sal)}${opt}`;
      card.appendChild(d);
    }
    apl.appendChild(card);
  }
  /* REMOVE PLAYER */
  const tl=$("tradeList"); tl.innerHTML="";
  if(!ST.traded.size) tl.innerHTML='<div class="muted">None.</div>';
  for(const [name,fromYr] of ST.traded){
    const card=document.createElement("div"); card.className="card";
    const head=document.createElement("div"); head.className="row";
    head.innerHTML=`<span class="name" style="color:var(--red)">✗ <span></span></span>
        <span class="meta">from ${fromYr}</span><button class="undo-btn">undo</button></div>`;
    head.querySelector(".name span").textContent=name;
    head.querySelector(".undo-btn").onclick=()=>{ST.undoTrade(name); rebuildSidebar(); redrawChart();};
    card.appendChild(head);
    // show the salaries coming off the books (from the cutoff year onward)
    const pl=ST.active.find(q=>q["Player"]===name);
    if(pl){
      const fromIdx=ST.yearCols.indexOf(fromYr);
      for(const yc of ST.yearCols){
        if(ST.yearCols.indexOf(yc)<fromIdx) continue;
        const sal=parseSalary(pl[yc])??ST.extensions.get(ST.key(name,yc))??null;
        if(!sal) continue;
        const d=document.createElement("div"); d.className="ext-year"; d.style.color="var(--subtext)";
        d.textContent=`${yc}   −${fmtM(sal)}`;
        card.appendChild(d);
      }
    }
    tl.appendChild(card);
  }
}

/* options collapse toggle */
$("optHeader").onclick=()=>{optionsCollapsed=!optionsCollapsed; rebuildSidebar();};

/* team + start-year selectors */
function rebuildStartSelector(){
  const sel=$("startYear"); sel.innerHTML="";
  ST.yearCols.forEach((yc,i)=>{const o=document.createElement("option"); o.value=i; o.textContent=yc; sel.appendChild(o);});
  sel.value=ST.displayStart;
}
$("startYear").onchange=e=>{ST.displayStart=parseInt(e.target.value); refreshTotals(); redrawChart();};

function loadTeam(name, csvText){
  let st;
  try{ st=new RosterState(csvText??TEAMS[name].csv, name); }
  catch(err){ alert("Could not parse CSV:\n"+err.message); return; }
  ST=st; optionsCollapsed=false;
  rebuildStartSelector(); rebuildSidebar(); redrawChart();
}
function rebuildTeamSelector(selected){
  const sel=$("teamSelect"); sel.innerHTML="";
  for(const name of Object.keys(TEAMS)){
    const o=document.createElement("option"); o.value=name; o.textContent=name; sel.appendChild(o);}
  sel.value=selected;
}
$("teamSelect").onchange=e=>loadTeam(e.target.value);

/* Add CSV (file or drag-drop) → becomes a new team entry */
$("openBtn").onclick=()=>$("fileInput").click();
function ingestCSVFile(file){
  const r=new FileReader();
  r.onload=()=>{
    const name=file.name.replace(/\.csv$/i,"");
    try{ new RosterState(r.result,name); }    // validate
    catch(err){ alert("Could not parse CSV:\n"+err.message); return; }
    TEAMS[name]={csv:r.result};
    rebuildTeamSelector(name); loadTeam(name,r.result);
  };
  r.readAsText(file);
}
$("fileInput").onchange=e=>{const f=e.target.files[0]; if(f) ingestCSVFile(f); e.target.value="";};
let dragDepth=0;
addEventListener("dragenter",e=>{e.preventDefault();dragDepth++;document.body.classList.add("dragging");});
addEventListener("dragleave",e=>{e.preventDefault();if(--dragDepth<=0){dragDepth=0;document.body.classList.remove("dragging");}});
addEventListener("dragover",e=>e.preventDefault());
addEventListener("drop",e=>{e.preventDefault();dragDepth=0;document.body.classList.remove("dragging");
  const f=e.dataTransfer.files[0]; if(f) ingestCSVFile(f);});

$("resetBtn").onclick=()=>{if(ST){ST.resetMoves(); rebuildSidebar(); redrawChart();}};
$("exportBtn").onclick=()=>{if(ST) exportPNG(ST);};

/* ── Light / dark theme toggle ── */
function applyTheme(light){
  document.body.classList.toggle("light",light);
  $("themeBtn").textContent = light ? "🌙 Dark" : "☀ Light";
  refreshTheme();
  redrawChart();
}
$("themeBtn").onclick=()=>applyTheme(!document.body.classList.contains("light"));

/* ════ MOUSE INTERACTION LISTENERS ════ */
canvas.addEventListener("mousemove", (e) => {
  if (!ST) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const mx = (e.clientX - rect.left) * dpr;
  const my = (e.clientY - rect.top) * dpr;
  
  const data = ST.chartData();
  const years = ST.displayYears().filter(y => data.has(y));
  if (!years.length) return;
  
  const s = dpr * (rect.width < 900 ? 0.85 : 1);
  const mL = 58 * s, mR = 86 * s, mT = 34 * s, mB = 34 * s;
  const pw = canvas.width - mL - mR, ph = canvas.height - mT - mB;
  const slotW = pw / years.length;
  const barW = Math.min(slotW * 0.62, 150 * s);
  
  let found = null;
  let maxV = 0;
  for (const yc of years) {
      maxV = Math.max(maxV, data.get(yc).reduce((a, e) => a + e[1], 0) / 1e6);
      const t = THRESHOLDS[parseInt(yc)]; if (t) maxV = Math.max(maxV, t[3]);
  }
  maxV *= 1.07;
  const Y = v => mT + ph - (v / maxV) * ph;
  
  for (let i = 0; i < years.length; i++) {
      const yc = years[i];
      const cx = mL + slotW * (i + 0.5);
      if (mx >= cx - barW / 2 && mx <= cx + barW / 2) {
          let bottom = 0;
          for (const [name, sal, isOpt] of data.get(yc)) {
              const top = Y((bottom + sal) / 1e6);
              const base = Y(bottom / 1e6);
              if (my >= top && my <= base) {
                  found = { name, salary: sal, year: yc, mx, my, s };
                  break;
              }
              bottom += sal;
          }
      }
      if (found) break;
  }
  
  if (JSON.stringify(activeTooltip) !== JSON.stringify(found)) {
      activeTooltip = found;
      renderChart(cctx, ST, 0, 0, canvas.width, canvas.height, s);
  } else if (activeTooltip) {
      activeTooltip.mx = mx;
      activeTooltip.my = my;
      renderChart(cctx, ST, 0, 0, canvas.width, canvas.height, s);
  }
});

canvas.addEventListener("mouseleave", () => {
  if (activeTooltip) {
      activeTooltip = null;
      redrawChart();
  }
});

/* ── Add Player dialog ── */
const addPlayerDlg=$("addPlayerDialog");
let addPlayerCache=[];   // players for the currently-selected source team
function otherTeamNames(){
  return Object.keys(TEAMS).filter(t=>t!==ST.teamName);
}
$("addPlayerBtn").onclick=()=>{
  if(!ST) return;
  const others=otherTeamNames();
  if(!others.length){alert("No other teams loaded. Add more team CSVs first."); return;}
  const tsel=$("addPlayerTeam"); tsel.innerHTML="";
  for(const t of others){const o=document.createElement("option"); o.value=t; o.textContent=t; tsel.appendChild(o);}
  tsel.value=others[0];
  $("addPlayerErr").textContent="";
  rebuildAddPlayerList();
  addPlayerDlg.showModal();
};
function rebuildAddPlayerList(){
  const team=$("addPlayerTeam").value;
  const sel=$("addPlayerSelect"); sel.innerHTML="";
  addPlayerCache=[];
  try{
    const {players}=teamPlayers(TEAMS[team].csv);
    // exclude players already on this roster (base or already-added)
    const onRoster=new Set(ST.active.map(p=>p["Player"]));
    addPlayerCache=players.filter(p=>!onRoster.has(p["Player"]));
  }catch(err){ $("addPlayerErr").textContent="Could not read "+team+": "+err.message; }
  if(!addPlayerCache.length){
    const o=document.createElement("option"); o.textContent="(no available players)"; o.value="-1"; sel.appendChild(o);
  }else{
    addPlayerCache.forEach((p,i)=>{
      const o=document.createElement("option"); o.value=i; o.textContent=p["Player"]; sel.appendChild(o);});
    sel.value=0;
  }
  rebuildAddPlayerYears();
}
function rebuildAddPlayerYears(){
  // Offer only seasons where this player actually has a salary — picking a join
  // year keeps that year and everything after it (in real calendar terms).
  const ysel=$("addPlayerYear"); ysel.innerHTML="";
  const i=parseInt($("addPlayerSelect").value);
  const src=(!isNaN(i)&&i>=0)?addPlayerCache[i]:null;
  let firstFilled=0, any=false;
  ST.yearCols.forEach((yc,idx)=>{
    const has=src&&parseSalary(src[yc])!=null;
    if(has){ if(!any){firstFilled=idx; any=true;}
      const o=document.createElement("option"); o.value=idx; o.textContent=yc; ysel.appendChild(o);}
  });
  if(!any){const o=document.createElement("option"); o.value="0"; o.textContent="(no seasons)"; ysel.appendChild(o);}
  ysel.value=firstFilled;            // default: their first contract season
  updateAddPlayerPreview();
}
/* Return {Player, Age, <year>…, Guaranteed} shifted so the player's contract
   begins at startYearIdx. Salaries keep their order and option flags; any years
   that would fall past the roster's final season are dropped. */
function buildShiftedContract(src, startYearIdx){
  // Keep the player's REAL calendar years; drop only the seasons before the
  // chosen join year. A 25-26→28-29 deal joined in 27-28 keeps 27-28 and 28-29.
  const dict={"Player":src["Player"],"Age":src["Age"]||""};
  for(const yc of ST.yearCols) dict[yc]="";
  const optionYears=[];
  let guaranteed=0;
  ST.yearCols.forEach((yc,idx)=>{
    if(idx<startYearIdx) return;                   // before the join year → dropped
    const sal=parseSalary(src[yc]); if(sal===null) return;
    dict[yc]=src[yc];                              // keep original formatted string in its real year
    if(isSourceOption(src,yc)) optionYears.push(yc); else guaranteed+=sal;
  });
  dict[ST.guaranteedCol]="$"+guaranteed.toLocaleString("en-US");
  return {dict,optionYears};
}
/* Does the source player's season look like an option/non-guaranteed year?
   Mirrors RosterState.determineOption using the source's own Guaranteed total. */
function isSourceOption(src,yc){
  const sal=parseSalary(src[yc]); if(sal===null) return false;
  const guar=parseSalary(src["Guaranteed"]); if(guar===null) return true;
  let r=0;
  for(const y of ST.yearCols){const s=parseSalary(src[y]); if(s===null)continue;
    r+=s; if(y===yc) return r>guar+1;}
  return false;
}
function updateAddPlayerPreview(){
  const i=parseInt($("addPlayerSelect").value);
  const box=$("addPlayerPreview");
  if(isNaN(i)||i<0||!addPlayerCache[i]){box.textContent=""; return;}
  const startIdx=parseInt($("addPlayerYear").value)||0;
  const src=addPlayerCache[i];
  const {dict,optionYears}=buildShiftedContract(src,startIdx);
  const optSet=new Set(optionYears);
  const parts=ST.yearCols.map(yc=>{
    const s=parseSalary(dict[yc]); if(!s) return null;
    return `${yc}: ${fmtM(s)}${optSet.has(yc)?"  (option)":""}`;}).filter(Boolean);
  // count source seasons that were dropped because they precede the join year
  const dropped=ST.yearCols.filter((yc,idx)=>idx<startIdx && parseSalary(src[yc])!=null).length;
  box.innerHTML="Contract as added:<br>"+(parts.join("<br>")||"(no seasons at this start year)")
    +(dropped>0?`<br><span style="color:var(--orange)">${dropped} earlier season(s) dropped — joining mid-contract</span>`:"");
}
$("addPlayerYear").onchange=updateAddPlayerPreview;
$("addPlayerTeam").onchange=rebuildAddPlayerList;
$("addPlayerSelect").onchange=()=>{rebuildAddPlayerYears();};
$("addPlayerCancel").onclick=()=>addPlayerDlg.close();
$("addPlayerSubmit").onclick=()=>{
  const err=$("addPlayerErr"); err.textContent="";
  const team=$("addPlayerTeam").value;
  const i=parseInt($("addPlayerSelect").value);
  if(isNaN(i)||i<0||!addPlayerCache[i]){err.textContent="Pick a player."; return;}
  const startIdx=parseInt($("addPlayerYear").value)||0;
  const {dict}=buildShiftedContract(addPlayerCache[i],startIdx);
  // Guard: at least one season must land within the chart.
  if(!ST.yearCols.some(yc=>parseSalary(dict[yc]))){
    err.textContent="That start year leaves no seasons on the chart. Pick an earlier season.";
    return;
  }
  ST.addPlayer(dict, team);
  addPlayerDlg.close(); rebuildSidebar(); redrawChart();
};

/* ── Extension dialog ── */
const extDlg=$("extDialog"); let extExpiring=[];
$("addExtBtn").onclick=()=>{
  if(!ST) return;
  extExpiring=ST.expiringContracts();
  if(!extExpiring.length){alert("No players with expiring contracts found."); return;}
  const sel=$("extPlayer"); sel.innerHTML="";
  extExpiring.forEach(([n,y,s],i)=>{const o=document.createElement("option");
    o.value=i; o.textContent=`${n} — last year ${y} (${fmtM(s)})`; sel.appendChild(o);});
  sel.value=0; $("extOptFlag").checked=false; $("extErr").textContent="";
  extRowState={};
  rebuildExtYears(); extDlg.showModal();
};
function extAvailableYears(){
  const i=parseInt($("extPlayer").value);
  if(isNaN(i)||!extExpiring[i]) return [];
  return ST.yearCols.slice(ST.yearCols.indexOf(extExpiring[i][1])+1);
}
function rebuildExtYears(){
  const box=$("extYears"); box.innerHTML="";
  for(const yr of extAvailableYears()){
    const l=document.createElement("label");
    l.innerHTML=`<input type="checkbox" value="${yr}"> ${yr}`;
    l.querySelector("input").onchange=rebuildExtSalaries; box.appendChild(l);}
  rebuildExtSalaries();
}
function extChosenYears(){return [...$("extYears").querySelectorAll("input:checked")].map(i=>i.value);}
$("extPlayer").onchange=rebuildExtYears;
// Per-year salary state: yr -> {unit:"dollar"|"percent", value:number}
let extRowState={};
function capForYear(yr){const t=THRESHOLDS[parseInt(yr)]; return (t?t[0]:154.647)*1e6;}
function extComputed(yr){
  const st=extRowState[yr]; if(!st||isNaN(st.value)) return null;
  return st.unit==="percent" ? capForYear(yr)*st.value/100 : st.value*1e6;
}
function rebuildExtSalaries(){
  const box=$("extSalaries"); box.innerHTML="";
  const chosen=extChosenYears();
  $("extSalHdr").style.display = chosen.length ? "block" : "none";
  if(!chosen.length){box.innerHTML='<div class="muted">Select extension years above.</div>'; extRowState={}; return;}
  // keep state for still-selected years, drop the rest
  const next={}; for(const yr of chosen) next[yr]=extRowState[yr]||{unit:"dollar",value:NaN};
  extRowState=next;
  for(const yr of chosen){
    const st=extRowState[yr];
    const row=document.createElement("div"); row.className="ext-row";
    row.innerHTML=
      `<span class="yr">${yr}</span>`+
      `<input type="number" step="0.1" min="0" data-yr="${yr}" placeholder="0.0">`+
      `<div class="unit-tog">`+
        `<button data-u="dollar" class="${st.unit==="dollar"?"on":""}">$M</button>`+
        `<button data-u="percent" class="${st.unit==="percent"?"on":""}">% cap</button>`+
      `</div>`+
      `<span class="calc" data-calc="${yr}"></span>`;
    const inp=row.querySelector("input");
    if(!isNaN(st.value)) inp.value=st.value;
    inp.oninput=()=>{extRowState[yr].value=parseFloat(inp.value); updateExtCalc(yr);};
    row.querySelectorAll(".unit-tog button").forEach(b=>b.onclick=()=>{
      extRowState[yr].unit=b.dataset.u;
      row.querySelectorAll(".unit-tog button").forEach(x=>x.classList.toggle("on",x===b));
      updateExtCalc(yr);
    });
    box.appendChild(row);
    updateExtCalc(yr);
  }
}
function updateExtCalc(yr){
  const el=document.querySelector(`[data-calc="${yr}"]`); if(!el) return;
  const st=extRowState[yr];
  const v=extComputed(yr);
  if(v===null){el.textContent=""; return;}
  el.textContent = st.unit==="percent"
    ? `= $${(v/1e6).toFixed(2)}M`
    : `= ${(v/capForYear(yr)*100).toFixed(1)}% of cap`;
}
$("extCancel").onclick=()=>extDlg.close();
$("extSubmit").onclick=()=>{
  const err=$("extErr"); err.textContent="";
  const i=parseInt($("extPlayer").value);
  if(isNaN(i)||!extExpiring[i]){err.textContent="Pick a player first."; return;}
  const name=extExpiring[i][0];
  const avail=extAvailableYears(), chosen=extChosenYears();
  if(!chosen.length){err.textContent="Select at least one extension year."; return;}
  const idx=chosen.map(y=>avail.indexOf(y));
  if(!(idx[0]===0 && idx.every((v,k)=>v===k))){err.textContent="Years must be consecutive, starting with the first year after the contract ends."; return;}
  const results=[];
  for(const yr of chosen){
    const st=extRowState[yr];
    if(!st||isNaN(st.value)||st.value<0){err.textContent=`Enter a salary for ${yr}.`; return;}
    const v=extComputed(yr);
    const label = st.unit==="percent"
      ? `${st.value.toFixed(1)}% of cap = $${(v/1e6).toFixed(2)}M`
      : `$${(v/1e6).toFixed(2)}M`;
    results.push([yr,v,label]);
  }
  const optLast=$("extOptFlag").checked;
  for(const [yr,v,label] of results) ST.addExtension(name,yr,v, optLast&&yr===chosen[chosen.length-1], label);
  extDlg.close(); rebuildSidebar(); redrawChart();
};

/* ── Trade dialog ── */
const tradeDlg=$("tradeDialog"); let tradeRoster=[];
$("addTradeBtn").onclick=()=>{
  if(!ST) return;
  tradeRoster=ST.rosterOnBooks().filter(([n])=>!ST.traded.has(n));
  if(!tradeRoster.length){alert("No players left on the books."); return;}
  const sel=$("tradePlayer"); sel.innerHTML="";
  tradeRoster.forEach(([n,yrs],i)=>{const span=yrs.length>1?`${yrs[0]} – ${yrs[yrs.length-1]}`:yrs[0];
    const o=document.createElement("option"); o.value=i; o.textContent=`${n}   (${span})`; sel.appendChild(o);});
  sel.value=0; rebuildTradeYears(); $("tradeErr").textContent=""; tradeDlg.showModal();
};
function rebuildTradeYears(){
  const i=parseInt($("tradePlayer").value), sel=$("tradeYear"); sel.innerHTML="";
  if(isNaN(i)||!tradeRoster[i]) return;
  for(const y of tradeRoster[i][1]){const o=document.createElement("option"); o.value=y; o.textContent=y; sel.appendChild(o);}
}
$("tradePlayer").onchange=rebuildTradeYears;
$("tradeCancel").onclick=()=>tradeDlg.close();
$("tradeSubmit").onclick=()=>{
  const i=parseInt($("tradePlayer").value);
  if(isNaN(i)||!tradeRoster[i]){$("tradeErr").textContent="Pick a player first."; return;}
  const yr=$("tradeYear").value;
  if(!yr){$("tradeErr").textContent="Pick a starting year."; return;}
  ST.trade(tradeRoster[i][0],yr); tradeDlg.close(); rebuildSidebar(); redrawChart();
};

/* ── Boot ── */
new ResizeObserver(()=>redrawChart()).observe($("chartwrap"));
const first=Object.keys(TEAMS)[0];
rebuildTeamSelector(first);
loadTeam(first);
</script>
</body>
</html>
"""


def main():
    csv_folder = sys.argv[1] if len(sys.argv) > 1 else "csv"
    out_html = sys.argv[2] if len(sys.argv) > 2 else "nba_salary_chart.html"

    print(f"Scanning {csv_folder}/ for team CSVs…")
    teams = discover_teams(csv_folder)
    html = build_html(teams)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {out_html}  ({len(teams)} team(s), {len(html)//1024} KB)")
    print("Open it by double-clicking — no install needed. "
          "Re-run this script after adding or editing CSVs.")


if __name__ == "__main__":
    main()