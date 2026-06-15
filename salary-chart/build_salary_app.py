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
    width:368px; flex:0 0 auto; background:var(--sidebar);
    overflow-y:auto; padding:8px 14px 24px; border-right:1px solid var(--line);
  }
  #sidebar::-webkit-scrollbar{width:9px;}
  #sidebar::-webkit-scrollbar-thumb{background:#3a3a3a; border-radius:5px;}
  #chartwrap{flex:1; min-width:0; position:relative; background:var(--chart-bg);}
  #chart{position:absolute; inset:10px; width:calc(100% - 20px); height:calc(100% - 20px); cursor:pointer;}

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

  /* Roster section */
  .rost-card{background:var(--card); border:1px solid var(--line); border-radius:7px; margin:4px 0; overflow:hidden;}
  .rost-card.open{border-color:var(--accent);}
  .rost-card.selected{border-color:var(--accent); box-shadow:0 0 0 1px var(--accent);}
  .rost-head{display:flex; align-items:center; gap:7px; padding:7px 9px; cursor:pointer; user-select:none;}
  .rost-head:hover{background:var(--panel);}
  .rost-card .rc-chev{color:var(--subtext); font-size:10px; transition:transform .15s; display:inline-block;}
  .rost-card.open .rc-chev{transform:rotate(90deg);}
  .rc-name{flex:1; font-weight:600; font-size:12px; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  /* Name colour encodes change state (replaces the old pill tags):
     acquired→green, extended→blue, has removed seasons→red. */
  .rc-name.nm-added{color:var(--green);}
  .rc-name.nm-ext{color:var(--blue);}
  .rc-name.nm-rem{color:var(--red);}
  .rc-total{color:var(--subtext); font:11px Consolas,Menlo,monospace;}
  .rc-revert{background:none; border:none; color:var(--subtext); cursor:pointer; font-size:14px;
    line-height:1; padding:2px 4px; border-radius:5px; margin-left:2px;}
  .rc-revert:hover{color:var(--accent); background:var(--panel);}
  .rc-revert:disabled{opacity:.28; cursor:default; background:none; color:var(--subtext);}
  /* header "remove seasons" × toggle, sits just right of the undo button */
  .rc-rmtoggle{background:none; border:none; color:var(--subtext); cursor:pointer; font-size:13px;
    line-height:1; padding:2px 5px; border-radius:5px; margin-left:1px;}
  .rc-rmtoggle:hover{color:var(--red); background:var(--panel);}
  .rc-rmtoggle.active{color:#fff; background:var(--red);}
  .rc-rmtoggle:disabled{opacity:.28; cursor:default; background:none; color:var(--subtext);}
  /* when remove-mode is on, on-books year rows become clickable red boxes,
     newest (last) first */
  .rc-year.rcy-removable{cursor:pointer; border:1px solid rgba(232,106,106,0.55);
    background:rgba(232,106,106,0.12); border-radius:5px; padding:1px 6px; margin:2px 0;}
  .rc-year.rcy-removable:hover{background:rgba(232,106,106,0.24);}
  .rc-year.rcy-removable.rcy-locked{cursor:not-allowed; opacity:.4; border-color:var(--line);
    background:none;}
  .rc-rmhint{color:var(--red); font-size:10px; margin:5px 0 2px; font-style:italic;}
  .rost-body{padding:4px 10px 10px; border-top:1px solid var(--line);}
  .rc-year{display:flex; align-items:center; gap:6px; font:11px/1.7 Consolas,Menlo,monospace;}
  .rc-year .rcy-yr{color:var(--subtext); width:54px; flex:0 0 54px;}
  .rc-year .rcy-sal{color:var(--text); width:58px; flex:0 0 58px; text-align:right; font-weight:600;}
  .rc-year .rcy-pct{color:var(--subtext); width:42px; flex:0 0 42px; text-align:right; font-size:10px;}
  /* fixed-width tag slot so the number columns stay aligned whether or not a
     row carries an opt/ext/declined badge */
  .rc-year .rcy-tag{flex:0 0 26px; width:26px; font-size:9px; text-transform:uppercase; font-weight:700;}
  .rc-year .rcy-tag.t-opt{color:var(--blue);}
  .rc-year .rcy-tag.t-ext{color:var(--green);}
  .rc-year .rcy-tag.t-decl{color:var(--red);}
  .rc-year.rcy-declined .rcy-sal,
  .rc-year.rcy-declined .rcy-yr,
  .rc-year.rcy-declined .rcy-pct{text-decoration:line-through; opacity:.6;}
  .rc-year .rcy-spacer{flex:1;}
  /* inline option accept/decline beside the year */
  .rcy-opt-seg{display:inline-flex; gap:4px; margin-left:auto; flex:0 0 auto;}
  .rcy-opt-seg .ob{height:20px; padding:0 7px; line-height:1; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:.2px; border-radius:4px;
    display:flex; align-items:center; justify-content:center; cursor:pointer;}
  /* Pre-selection: each choice shows a faint tinted box hinting its colour. */
  .rcy-opt-seg .ob-acc{border:1px solid rgba(106,232,138,0.55); background:rgba(106,232,138,0.12); color:var(--green);}
  .rcy-opt-seg .ob-dec{border:1px solid rgba(232,106,106,0.55); background:rgba(232,106,106,0.12); color:var(--red);}
  .rcy-opt-seg .ob-acc:hover{background:rgba(106,232,138,0.22);}
  .rcy-opt-seg .ob-dec:hover{background:rgba(232,106,106,0.22);}
  /* Selected state: solid fill. */
  .rcy-opt-seg .ob.on-acc{color:#111; background:var(--green); border-color:var(--green);}
  .rcy-opt-seg .ob.on-dec{color:#111; background:var(--red);   border-color:var(--red);}
  .rcy-opt-seg .ob:disabled{opacity:.4; cursor:not-allowed;}
  .rcy-optlbl{color:var(--accent); font-size:9px; text-transform:uppercase; margin-left:6px;}
  /* inline year-remove (×) on the trailing edge of a contract row */
  .rcy-del{background:none; border:none; color:var(--subtext); cursor:pointer; font-size:12px;
    padding:0 2px; line-height:1; opacity:.55;}
  .rcy-del:hover{color:var(--red); opacity:1;}
  .opt-lock{color:var(--subtext); font-size:10px; margin-top:4px; font-style:italic;}
  /* "add extension year" plus row, styled like add-player */
  .rc-addyear{display:flex; align-items:center; gap:8px; margin:7px 0 2px; padding:6px 8px; cursor:pointer;
    border:1px dashed var(--line); border-radius:6px; color:var(--subtext); font-size:11px;}
  .rc-addyear:hover{border-color:var(--blue); color:var(--blue);}
  .rc-addyear .ay-plus{font-size:15px; width:16px; text-align:center;}
  .rc-addyear.disabled{opacity:.45; cursor:not-allowed; border-color:var(--line); color:var(--subtext);}
  .rc-addyear.disabled:hover{border-color:var(--line); color:var(--subtext);}
  /* remove-seasons button: red variant of the add-year affordance */
  .rc-removeyear:hover{border-color:var(--red); color:var(--red);}
  .rc-removeyear.active{border-style:solid; border-color:var(--red); color:#fff; background:var(--red);}
  .rc-removeyear.active:hover{border-color:var(--red); color:#fff; background:var(--red);}
  .rc-removeyear.disabled:hover{border-color:var(--line); color:var(--subtext);}
  .rc-btn.disabled,.rc-btn:disabled{opacity:.4; cursor:not-allowed;}
  .rc-actions{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;}
  .rc-btn{font-size:11px; font-weight:600; border-radius:5px; padding:4px 10px; cursor:pointer;
    background:var(--card); border:1px solid var(--line); color:var(--text);}
  .rc-remove{color:var(--red); border-color:var(--red);}    .rc-remove:hover{background:var(--red); color:#fff;}
  .rc-unext{color:var(--subtext);}                          .rc-unext:hover{background:var(--panel);}
  .rc-undo{color:var(--accent); border-color:var(--accent);} .rc-undo:hover{background:var(--accent); color:#fff;}
  .rost-add{display:flex; align-items:center; gap:8px; margin:6px 0; padding:8px 9px; cursor:pointer;
    border:1px dashed var(--line); border-radius:7px; color:var(--subtext);}
  .rost-add:hover{border-color:var(--green); color:var(--green);}
  .rost-add .ra-plus{font-size:16px; width:18px; text-align:center;}
  .rost-add .ra-label{font-size:11.5px;}
  .rost-add.open{border-style:solid; border-color:var(--green); color:var(--green);}

  /* Inline "add player from another team" panel (replaces the old modal) */
  .add-panel{margin:6px 0 10px; padding:10px 11px; border:1px solid var(--green);
    border-radius:8px; background:var(--card);}
  .add-panel .ap-title{font-size:11.5px; font-weight:700; color:var(--text); margin-bottom:8px;}
  .add-panel .ap-label{font-size:10px; font-weight:600; letter-spacing:.3px; color:var(--subtext);
    text-transform:uppercase; margin:8px 0 3px;}
  .add-panel select{width:100%; font-size:12px; padding:5px 8px;}
  .add-panel .ap-preview{margin-top:8px; font-size:10.5px; line-height:1.5; color:var(--subtext);}
  .add-panel .ap-err{color:var(--red); font-size:10.5px; min-height:13px; margin-top:5px;}
  .add-panel .ap-btns{display:flex; gap:8px; margin-top:10px;}
  .add-panel .ap-btns button{flex:1; padding:6px 0; font-size:12px; font-weight:600;}
  /* mode toggle: From league / Draft pick */
  .add-panel .ap-mode{display:flex; gap:6px; margin-bottom:6px;}
  .add-panel .ap-mode button{flex:1; padding:5px 0; font-size:11px; font-weight:600;
    color:var(--subtext); background:var(--sidebar); border:1px solid var(--line); border-radius:5px;}
  .add-panel .ap-mode button.on{color:#fff; background:var(--accent); border-color:var(--accent);}
  .add-panel input[type=text]{width:100%; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:5px 8px; font:inherit; font-size:12px;}
  .add-panel input[type=text]:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  /* season + pick on one row */
  .add-panel .ap-draftrow{display:flex; gap:8px; align-items:flex-end;}
  .add-panel .ap-draftrow .ap-col{flex:1;}
  .add-panel .ap-draftrow .ap-col-pick{flex:0 0 84px;}
  .add-panel .ap-draftrow .ap-label{margin-top:8px;}
  .add-panel input[type=number]#draftPick{width:100%; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:5px 8px; font:inherit; font-size:12px; text-align:center;}
  .add-panel input[type=number]#draftPick:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}

  /* Inline extension salary entry (rendered inside a player card) */
  .inline-form{margin-top:9px; padding-top:9px; border-top:1px solid var(--line);}
  .inline-form .if-title{font-size:11px; font-weight:700; color:var(--text); margin-bottom:6px;}
  .inline-form .if-row{display:flex; align-items:center; gap:6px; margin:5px 0; font-size:11px;}
  .inline-form .if-row .ifr-yr{width:54px; font-weight:600; color:var(--text); font-family:Consolas,Menlo,monospace;}
  .inline-form .if-row input[type=number]{width:60px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:4px 6px; font:inherit;}
  .inline-form .ifr-calc{color:var(--subtext); font-size:10px; font-family:Consolas,Menlo,monospace;}
  .inline-form .unit-tog{display:flex; border:1px solid var(--line); border-radius:5px; overflow:hidden;}
  .inline-form .unit-tog button{border:none; border-radius:0; padding:4px 7px; font-size:10.5px;
    background:var(--sidebar); color:var(--subtext); cursor:pointer;}
  .inline-form .unit-tog button.on{background:var(--accent); color:#fff; font-weight:700;}
  .inline-form .if-opt{display:flex; align-items:center; gap:5px; font-size:11px; color:var(--text); margin-top:6px; cursor:pointer;}
  .inline-form .if-err{color:var(--red); font-size:10.5px; min-height:13px; margin-top:4px;}
  .inline-form .if-btns{display:flex; gap:8px; margin-top:8px;}
  .inline-form .if-btns .rc-btn{flex:1;}
  .rc-btn.rc-extend{color:var(--blue); border-color:var(--blue);}
  .rc-btn.rc-extend:hover{background:var(--blue); color:#fff;}
  /* inline "make option year" toggle button */
  .if-optbtn{display:block; width:100%; margin-top:8px; font-size:11px; font-weight:600;
    color:var(--blue); border:1px solid rgba(106,176,245,0.55); background:rgba(106,176,245,0.10);}
  .if-optbtn:hover{background:rgba(106,176,245,0.20);}
  .if-optbtn.on{color:#111; background:var(--blue); border-color:var(--blue);}
  .rc-btn.active{background:var(--panel);}

  /* Yearly summary status boxes */
  #totals{display:flex; flex-direction:column; gap:4px; padding:0; background:none;}
  .ysum-cell{
    background:var(--card); border:1px solid var(--line); border-radius:6px;
    margin-bottom:4px; overflow:hidden;
  }
  .ys-head{display:flex; align-items:center; gap:8px; padding:6px 9px; cursor:pointer; user-select:none;
    font:11px/1.3 Consolas,Menlo,monospace; white-space:nowrap;}
  .ys-head:hover{filter:brightness(1.15);}
  .ys-chev{color:var(--subtext); font-size:10px; transition:transform .15s; display:inline-block;}
  .ysum-cell.open .ys-chev{transform:rotate(90deg);}
  .ysum-cell .ys-yr{color:var(--text); width:52px;}
  .ysum-cell .ys-status{flex:1; font-family:'Segoe UI',Arial,sans-serif; font-weight:600; font-size:11px;}
  .ysum-cell .ys-tot{color:var(--subtext); width:54px; text-align:right;}
  .ys-body{padding:4px 10px 9px; border-top:1px solid var(--line);}
  .ys-growth{display:flex; align-items:center; gap:6px; margin:6px 0 4px;}
  .ys-growth .ysg-lbl{flex:1; color:var(--subtext); font-size:10px;
    text-transform:uppercase; letter-spacing:.3px;}
  .ys-growth .ysg-inp{width:54px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:3px 6px; font:inherit;
    font-size:11px; text-align:right;}
  .ys-growth .ysg-inp:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  .ys-growth .ysg-pct{color:var(--subtext); font-size:11px;}
  .ys-body .ys-bsub{color:var(--subtext); font-size:10px; margin:3px 0 5px;}
  .yt-table{border-collapse:collapse; font:11px/1.6 Consolas,Menlo,monospace; width:100%;}
  .yt-lbl{color:var(--text); padding:1px 12px 1px 0; white-space:nowrap;}
  .yt-dot{display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:6px; vertical-align:middle;}
  .yt-line{text-align:right; padding:1px 8px 1px 0; color:var(--text); white-space:nowrap;}
  .yt-arrow{text-align:center; padding:1px 6px; color:var(--text); white-space:nowrap;}
  .yt-val{text-align:right; padding:1px 0; font-weight:700; color:var(--text); white-space:nowrap;}
  /* Payroll marker: a thin full-width line (same colour/weight as the box
     border) showing where total salary sits among the threshold rows. Drawn as a
     1px border on a zero-height row so it doesn't shift any text. */
  .yt-marker td{padding:0; height:0; line-height:0;}
  .yt-payline{height:0; border-top:1px solid var(--line); margin:3px -10px;}

  /* Selected-player panel (click a bar segment) */
  .player-panel{
    position:fixed; z-index:120; min-width:210px; max-width:280px;
    background:var(--panel); border:1px solid var(--line); border-radius:9px;
    padding:11px 12px; box-shadow:0 8px 26px rgba(0,0,0,.45);
    font:12px/1.4 'Segoe UI',Arial,sans-serif;
  }
  .player-panel .pp-head{display:flex; align-items:center; justify-content:space-between; gap:8px;}
  .player-panel .pp-name{font-weight:700; font-size:13px; color:var(--text);}
  .player-panel .pp-close{background:none; border:none; color:var(--subtext); font-size:13px; cursor:pointer; padding:0 2px;}
  .player-panel .pp-close:hover{color:var(--text);}
  .player-panel .pp-sub{color:var(--subtext); font-size:11px; margin-top:2px;}
  .player-panel .pp-table{width:100%; border-collapse:collapse; margin:8px 0 4px;
    font:11.5px/1.6 Consolas,Menlo,monospace;}
  .player-panel .pp-yr{color:var(--subtext); padding-right:10px;}
  .player-panel .pp-sal{color:var(--text); text-align:right; padding-right:10px; font-weight:600;}
  .player-panel .pp-pct{color:var(--subtext); text-align:right; padding-right:10px; font-size:10.5px;}
  .player-panel .pp-opt{color:var(--accent); font-size:10px;}
  .player-panel .pp-total{color:var(--subtext); font-size:11px; padding-top:5px; border-top:1px solid var(--line);}
  .player-panel .pp-actions{display:flex; gap:8px; margin-top:10px;}
  .player-panel .pp-btn{flex:1; padding:6px 0; font-size:12px; font-weight:600; border-radius:6px;
    border:1px solid var(--line); cursor:pointer; background:var(--card); color:var(--text);}
  .player-panel .pp-extend{color:var(--blue); border-color:var(--blue);}
  .player-panel .pp-extend:hover{background:var(--blue); color:#fff;}
  .player-panel .pp-remove{color:var(--red); border-color:var(--red);}
  .player-panel .pp-remove:hover{background:var(--red); color:#fff;}

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
  <button class="b-green" id="exportBtn">Export PNG</button>
</div>

<div id="main">
  <div id="sidebar">
    <div class="section-h"><div class="left">YEARLY SUMMARY</div></div>
    <div id="totals"></div>

    <div class="section-h collapsible" id="optHeader">
      <div class="left"><span class="chev">▼</span> ROSTER</div>
      <span class="count" id="optCount"></span>
    </div>
    <div class="collapse-body" id="optionsBody"><div id="rosterList"></div></div>
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

/* ── Cap / tax / apron model ──────────────────────────────────────────
   2025-26 values are the real, published figures (the base year). Every
   later year is derived by compounding the previous year's [cap, tax,
   1st apron, 2nd apron] by a user-editable growth % (default 6.7%, set
   per-year in the YEARLY SUMMARY panel). THRESHOLDS is rebuilt from these
   inputs by recomputeThresholds() and is what the rest of the app reads. */
const BASE_YEAR=2025;
const BASE_THRESHOLDS=[154.647,187.895,195.945,207.824];  // 2025-26 cap, tax, apron1, apron2
const DEFAULT_GROWTH=6.7;     // default year-over-year increase, in %
const LAST_YEAR=2034;         // build the table out to here
// year -> growth % applied to get THAT year's values from the prior year.
// Editable via the yearly-summary controls; missing years fall back to default.
const GROWTH={};
function growthFor(year){
  return (GROWTH[year]!==undefined && !isNaN(GROWTH[year])) ? GROWTH[year] : DEFAULT_GROWTH;
}
let THRESHOLDS={};
function recomputeThresholds(){
  const out={}; out[BASE_YEAR]=BASE_THRESHOLDS.slice();
  for(let y=BASE_YEAR+1; y<=LAST_YEAR; y++){
    const prev=out[y-1], f=1+growthFor(y)/100;
    out[y]=prev.map(v=>v*f);
  }
  THRESHOLDS=out;
  return out;
}
recomputeThresholds();
const FLOOR_PCT=0.90;   // salary floor = 90% of the cap

/* ── Rookie scale (1st-round picks) ───────────────────────────────────
   2025-26 figures at 120% of scale (the league norm for nearly every
   pick). Each pick is a four-season deal in a "2 guaranteed, 2 option"
   format: Year 1 & 2 are guaranteed, Year 3 & 4 are team options.
   Values for a draft class entering in a later year scale up by the same
   compounded growth % used for the cap (relative to the 2025 base year),
   so a pick in 2027-28 uses the 2025 base inflated two years. Index 0 is
   pick #1. Each row: [Year1, Year2, Year3(opt), Year4(opt)]. */
const ROOKIE_SCALE_BASE_YEAR=2025;
const ROOKIE_SCALE=[
  [13825920,14517480,15208680,19178146], // 1
  [12370320,12989040,13607760,17172994], // 2
  [11108880,11663880,12219840,15445878], // 3
  [10015680,10516560,11017560,13937214], // 4
  [9069840, 9523080, 9976560, 12640302], // 5
  [8237640, 8649600, 9061680, 11490211], // 6
  [7520040, 7896240, 8271960, 10505389], // 7
  [6889200, 7233720, 7578240, 9639522],  // 8
  [6332520, 6649560, 6966000, 8874684],  // 9
  [6016080, 6316680, 6617160, 8436880],  // 10
  [5715120, 6001080, 6286920, 8342743],  // 11
  [5429520, 5701200, 5972760, 8230464],  // 12
  [5157960, 5416080, 5673840, 8107918],  // 13
  [4900320, 5145360, 5390640, 7983539],  // 14
  [4655040, 4887720, 5120400, 7849573],  // 15
  [4422360, 4643520, 4864920, 7462788],  // 16
  [4201080, 4411200, 4621200, 7098163],  // 17
  [3991320, 4190520, 4390320, 6752312],  // 18
  [3811560, 4002000, 4193040, 6457282],  // 19
  [3658800, 3841680, 4024440, 6205687],  // 20
  [3512520, 3688320, 3864000, 6155352],  // 21
  [3372240, 3540600, 3709320, 6101832],  // 22
  [3237480, 3399480, 3560880, 6042814],  // 23
  [3108120, 3263400, 3418800, 5979481],  // 24
  [2983320, 3132360, 3282000, 5910882],  // 25
  [2884560, 3028560, 3172920, 5720776],  // 26
  [2801280, 2941440, 3081840, 5559640],  // 27
  [2783880, 2923560, 3062640, 5528065],  // 28
  [2763960, 2902080, 3040320, 5487778],  // 29
  [2743800, 2880960, 3018480, 5448356],  // 30
];
// Compounded growth factor from the 2025 base year up to `year` (the season
// the rookie class enters), using the same per-year GROWTH the cap uses.
function rookieGrowthFactor(year){
  let f=1;
  for(let y=ROOKIE_SCALE_BASE_YEAR+1; y<=year; y++) f*=1+growthFor(y)/100;
  return f;
}
// Four scaled salaries [Y1,Y2,Y3opt,Y4opt] for a given pick (1-based) entering
// in the given calendar start year (e.g. 2026 for the 2026-27 season).
function rookieSalaries(pick, enterYear){
  const row=ROOKIE_SCALE[pick-1]; if(!row) return null;
  const f=rookieGrowthFactor(enterYear);
  return row.map(v=>v*f);
}

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
  hasPendingOption(name){
    return this.optionsFound.concat([...this.extensionOptions].map(k=>{const [n,y]=k.split("|"); return [n,y];}))
      .some(([n,y])=>n===name && !this.isYearRemoved(n,y)
        && this.optionStates.get(this.key(n,y))==="pending");
  }
  expiringContracts(){
    const last=this.yearCols[this.yearCols.length-1],out=[];
    for(const p of this.active){const name=p["Player"];
      // A player with an unresolved (pending) option can't be extended until the
      // option is accepted or declined first.
      if(this.hasPendingOption(name)) continue;
      const filled=this.yearCols.filter(yc=>!this.isYearRemoved(name,yc) &&
        ((parseSalary(p[yc])&&!this.isDeclined(name,yc))||this.extensions.has(this.key(name,yc))));
      if(!filled.length) continue;
      const lastYr=filled[filled.length-1];
      if(lastYr!==last){const sal=parseSalary(p[lastYr])??this.extensions.get(this.key(name,lastYr))??0; out.push([name,lastYr,sal]);}
    }
    out.sort((a,b)=>this.yearCols.indexOf(a[1])-this.yearCols.indexOf(b[1])); return out;
  }
  addExtension(name,year,salary,isOption,label){
    // If a removal cutoff would hide this new season, lift it (extending past a
    // removed tail brings the player back on the books from here on).
    if(this.traded.has(name) &&
       this.yearCols.indexOf(year) >= this.yearCols.indexOf(this.traded.get(name))){
      this.traded.delete(name);
    }
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
  // Peel a single extension season (and any extension seasons after it, so the
  // contract stays contiguous) — used by the red × remove-mode on extension years.
  removeExtensionYear(name, yr){
    const cut=this.yearCols.indexOf(yr);
    const p=this.active.find(q=>q["Player"]===name);
    for(const k of [...this.extensions.keys()]){
      if(!k.startsWith(name+"|")) continue;
      const y=k.split("|")[1];
      if(this.yearCols.indexOf(y) >= cut){
        this.extensions.delete(k); this.extensionLabels.delete(k); this.extensionOptions.delete(k);
        // Only clear the option state if it belonged to the EXTENSION. If a CSV
        // option also lives at this season (e.g. a declined option that an
        // extension was layered onto), keep its accepted/declined state so the
        // crossed-out option year is restored intact.
        if(!(p && this.determineOption(p,y))) this.optionStates.delete(k);
      }
    }
  }
  rosterOnBooks(){const out=[];
    for(const p of this.active){const name=p["Player"];
      const yrs=this.yearCols.filter(yc=>(parseSalary(p[yc])&&!this.isDeclined(name,yc))||this.extensions.has(this.key(name,yc)));
      if(yrs.length) out.push([name,yrs]);}
    out.sort((a,b)=>this.yearCols.indexOf(a[1][a[1].length-1])-this.yearCols.indexOf(b[1][b[1].length-1])); return out;
  }
  trade(n,y){this.traded.set(n,y);} undoTrade(n){this.traded.delete(n);}
  // Revert a single player to their original contract: clear option decisions,
  // extensions, and trade cutoffs for this player. Acquired players are removed
  // entirely (their "original" state is not being on this roster). Any
  // CSV-detected option years reset to pending.
  revertPlayer(name){
    if(this.isAddedPlayer(name)){ this.removeAddedPlayer(name); return; }
    for(const k of [...this.optionStates.keys()]) if(k.startsWith(name+"|")) this.optionStates.delete(k);
    this.removeExtensionsFor(name);
    this.traded.delete(name);
    this.refreshOptions();
    for(const [n,y] of this.optionsFound) if(n===name) this.optionStates.set(this.key(n,y),"pending");
  }
  // Has the user made any change to this player vs their original contract?
  playerHasMoves(name){
    if(this.isAddedPlayer(name)) return true;
    if(this.traded.has(name)) return true;
    if([...this.extensions.keys()].some(k=>k.startsWith(name+"|"))) return true;
    // any option year resolved away from "pending"?
    for(const [n,y] of this.optionsFound)
      if(n===name && this.optionStates.get(this.key(n,y))!=="pending"
         && this.optionStates.has(this.key(n,y))) return true;
    return false;
  }
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
        // For each tier line: its actual $ value and the team's margin
        // (positive = payroll is above the line).
        breakdown=[
          {label:"2nd Apron",    line:a2,    value:tm-a2},
          {label:"1st Apron",    line:a1,    value:tm-a1},
          {label:"Luxury Tax",   line:tax,   value:tm-tax},
          {label:"Salary Cap",   line:cap,   value:tm-cap},
          {label:"Salary Floor", line:floor, value:tm-floor},
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
  // Total guaranteed money for a player = sum of their non-option salaries that
  // remain on the books (respecting declines, trades, and extensions).
  playerGuaranteed(p){
    const name=p["Player"]; let g=0;
    for(const yc of this.yearCols){
      if(this.isYearRemoved(name,yc)) continue;
      const csv=parseSalary(p[yc]);
      const ext=this.extensions.get(this.key(name,yc));
      let sal,isOpt;
      if(this.isDeclined(name,yc)){ sal=(ext!=null&&!this.extensionOptions.has(this.key(name,yc)))?ext:null; isOpt=false; }
      else { sal=csv??ext??null;
             isOpt=(csv==null&&ext!=null)?this.extensionOptions.has(this.key(name,yc))
                                          :(this.determineOption(p,yc)&&!this.isAccepted(name,yc)); }
      if(sal && !isOpt) g+=sal;
    }
    return g;
  }
  // All active players (base + acquired) sorted by guaranteed total, high→low.
  rosterSorted(){
    return this.active.slice().sort((a,b)=>this.playerGuaranteed(b)-this.playerGuaranteed(a));
  }
  // Per-year contract rows for a player (used by the roster list + click panel).
  // A declined CSV option year is kept as a row (declined:true) — it isn't
  // removed outright, so its Accept/Decline control stays reachable and the user
  // can re-accept later. Such a row contributes nothing to payroll.
  contractRows(name){
    const p=this.active.find(q=>q["Player"]===name); if(!p) return [];
    const rows=[];
    for(const yc of this.yearCols){
      if(this.isYearRemoved(name,yc)) continue;
      const csv=parseSalary(p[yc]); const ext=this.extensions.get(this.key(name,yc));
      const isExtOpt=this.extensionOptions.has(this.key(name,yc));
      if(this.isDeclined(name,yc)){
        // A declined option year is never removed outright — its original CSV
        // figure stays visible as a crossed-out row so it can be re-accepted (or
        // simply seen). If an extension was signed for that same season, that
        // extension shows as its OWN row right after, on the books.
        if(csv!=null) rows.push({yc,sal:csv,opt:true,fromExt:false,declined:true});
        if(ext!=null) rows.push({yc,sal:ext,opt:isExtOpt,fromExt:true,declined:false});
        continue;
      }
      let sal=csv??ext??null; const fromExt=csv==null&&ext!=null;
      if(sal==null) continue;
      const opt=fromExt?isExtOpt:(this.determineOption(p,yc)&&!this.isAccepted(name,yc));
      rows.push({yc,sal,opt,fromExt,declined:false});
    }
    return rows;
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
  // Highlight = the set of expanded player panels (kept in sync both ways).
  const selSet = (typeof highlightedPlayers!=='undefined' && highlightedPlayers) ? highlightedPlayers : null;
  let anySel = selSet && selSet.size>0;

  // Check to display normally if no selected player is present in the chart
  if (anySel) {
    anySel = years.some(yc => data.get(yc).some(p => selSet.has(p[0])));
  }
  years.forEach((yc,i)=>{let bottom=0; const cx=X(i);
    for(const [name,sal,isOpt] of data.get(yc)){
      const top=Y((bottom+sal)/1e6), h=Y(bottom/1e6)-top, x=cx-barW/2;
      const isSel = anySel && selSet.has(name);
      const dim = anySel && !isSel;
      ctx.save();
      if(dim) ctx.globalAlpha=0.28;
      ctx.fillStyle=THEME.bar; ctx.fillRect(x,top,barW,h);
      if(isOpt){ctx.fillStyle=hatch; ctx.fillRect(x,top,barW,h);}
      // separator line at top of segment
      ctx.fillStyle=THEME.sep; ctx.fillRect(x,top-0.6*s,barW,1.2*s);
      ctx.restore();
      // highlight outline on each highlighted player's segments
      if(isSel){
        ctx.save();
        ctx.strokeStyle=THEME.name; ctx.lineWidth=2.4*s;
        ctx.strokeRect(x+ctx.lineWidth/2, top+ctx.lineWidth/2, barW-ctx.lineWidth, h-ctx.lineWidth);
        ctx.restore();
      }
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
      const dim = anySel && !selSet.has(name);
      if(dim) ctx.save(), ctx.globalAlpha=0.30;
      fitLabel(ctx,name,cx,top,h,barW);
      if(dim) ctx.restore();
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

  // Interactive Hover Tooltip Render — player name only
  if (typeof activeTooltip !== 'undefined' && activeTooltip) {
    const t = activeTooltip;
    ctx.save();
    ctx.font = `bold ${12.5 * t.s}px ${BODYF}`;
    const txt1 = t.name;
    const boxW = ctx.measureText(txt1).width + 16 * t.s;
    const boxH = 26 * t.s;

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
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.font = `bold ${12.5 * t.s}px ${BODYF}`;
    ctx.fillText(txt1, tX + 8 * t.s, tY + boxH/2);
    ctx.restore();
  }

  ctx.restore();
}

/* ════ PNG EXPORT (yearly summary + roster left · chart center · changes right) ════ */
function exportPNG(state){
  refreshTheme();
  const TX=THEME.text, SUB=THEME.sub;
  const SC=2.5;
  const years=state.displayYears().filter(y=>state.chartData().has(y));
  const chartW=Math.max(1100,years.length*210)*SC, chartH=1200*SC;
  const MONO="Consolas,Menlo,monospace";
  const PAD=28*SC;

  // ---- helper to draw a column of items, returns the max text width used ----
  function measure(items){
    const m=document.createElement("canvas").getContext("2d"); let w=0;
    for(const it of items){
      if(it.cols){ w=Math.max(w, it.cols.reduce((a,c)=>a+c.w,0)*SC); }
      else { m.font=`${it.bold?"bold ":""}${it.size*SC}px ${MONO}`; w=Math.max(w,m.measureText(it.text).width); }
    }
    return w;
  }
  function drawItems(ctx,items,x0,y0){
    let y=y0; ctx.textAlign="left"; ctx.textBaseline="top";
    for(const it of items){
      if(it.cols){
        let cx=x0; ctx.font=`${(it.size||11.5)*SC}px ${MONO}`;
        for(const col of it.cols){ ctx.fillStyle=col.color; ctx.fillText(col.text,cx,y); cx+=col.w*SC; }
        y+=(it.size||11.5)*1.7*SC;
      }else{
        ctx.font=`${it.bold?"bold ":""}${it.size*SC}px ${MONO}`;
        ctx.fillStyle=it.color; ctx.fillText(it.text,x0,y);
        y+=(it.bold?it.size*1.85:it.size*1.5)*SC;
      }
    }
    return y;
  }
  const H=(arr,t,c)=>arr.push({text:t,color:c||TX,size:14,bold:true});
  const SUBH=(arr,t,c)=>arr.push({text:t,color:c||SUB,size:11,bold:true});
  const LINE=(arr,t,c)=>arr.push({text:t,color:c||TX,size:11,bold:false});
  const GAP=(arr)=>arr.push({text:"",color:TX,size:7,bold:false});
  const ROW=(arr,cols,size)=>arr.push({cols,size});

  // contiguous-year span helper → "2025-26 – 2028-29" or "2025-26"
  const yspan=yrs=>{
    if(!yrs.length) return "";
    return yrs.length>1 ? `${yrs[0]} – ${yrs[yrs.length-1]}` : yrs[0];
  };

  // ---- LEFT: condensed yearly summary, then condensed roster ----
  const left=[];
  H(left,"YEARLY SUMMARY");
  for(const r of state.yearlySummary()){
    GAP(left);
    ROW(left,[{text:r.yc,color:TX,w:60},
              {text:r.status,color:STATUS_COLOR[r.status]||SUB,w:96},
              {text:`$${r.total.toFixed(0)}M`,color:TX,w:64},
              {text:`${r.players}/15`,color:SUB,w:50}]);
  }
  GAP(left); GAP(left);
  H(left,"ROSTER");
  for(const p of state.rosterSorted()){
    const name=p["Player"]; const rows=state.contractRows(name);
    if(!rows.length) continue;
    let guarTot=0,optTot=0;
    const guarYrs=[], optYrs=[];
    for(const r of rows){ if(r.opt){optTot+=r.sal; optYrs.push(r.yc);} else {guarTot+=r.sal; guarYrs.push(r.yc);} }
    // contract total: guaranteed, with option money appended via "+"
    let tot=`$${(guarTot/1e6).toFixed(0)}M`; if(optTot>0) tot+=` +$${(optTot/1e6).toFixed(0)}M`;
    // years under contract: guaranteed span, plus option years tagged with "+"
    let yrsTxt=yspan(guarYrs);
    if(optYrs.length){ yrsTxt += (yrsTxt?"  ":"") + optYrs.map(y=>"+"+y).join(" "); }
    const from=state.addedFrom.get(name), traded=state.traded.get(name);
    const tag=from?" ‹from "+from+"›":(traded?" ‹removed›":"");
    GAP(left);
    ROW(left,[{text:name+tag,color:TX,w:230},{text:tot,color:SUB,w:96}]);
    ROW(left,[{text:"  "+yrsTxt,color:SUB,w:326}],10);
  }

  // ---- RIGHT: roster CHANGES only (acquired · removed · extensions) ----
  const {exts,added,trades}=state.summarySections();
  const right=[];
  H(right,"ROSTER CHANGES");
  const anyChange = added.length || trades.length || exts.length;
  if(!anyChange){ GAP(right); LINE(right,"No changes yet.",SUB); }

  if(added.length){
    GAP(right); SUBH(right,"ACQUIRED",THEME.green||SUB);
    for(const a of added){
      const span=yspan(a.rows.map(r=>r.yc));
      GAP(right);
      ROW(right,[{text:a.name,color:TX,w:200},
                 {text:`$${(a.total/1e6).toFixed(0)}M`,color:SUB,w:80}]);
      ROW(right,[{text:`  from ${a.from} · ${span}`,color:SUB,w:300}],10);
    }
  }
  if(trades.length){
    GAP(right); SUBH(right,"REMOVED",THEME.accent||SUB);
    for(const t of trades){
      const off=t.rows.reduce((s,r)=>s+r.sal,0);
      GAP(right);
      ROW(right,[{text:t.name,color:TX,w:200},
                 {text:`-$${(off/1e6).toFixed(0)}M`,color:SUB,w:80}]);
      ROW(right,[{text:`  from ${t.fromYr} onward`,color:SUB,w:300}],10);
    }
  }
  if(exts.length){
    GAP(right); SUBH(right,"EXTENSIONS",THEME.accent||SUB);
    // group extension rows by player
    const byName=new Map();
    for(const [n,y,s,isOpt] of exts){ if(!byName.has(n)) byName.set(n,[]); byName.get(n).push([y,s,isOpt]); }
    for(const [n,list] of byName){
      list.sort((a,b)=>state.yearCols.indexOf(a[0])-state.yearCols.indexOf(b[0]));
      const tot=list.reduce((s,r)=>s+r[1],0);
      GAP(right);
      ROW(right,[{text:n,color:TX,w:200},
                 {text:`+$${(tot/1e6).toFixed(0)}M`,color:SUB,w:80}]);
      for(const [y,s,isOpt] of list){
        const cap=THRESHOLDS[parseInt(y)]?THRESHOLDS[parseInt(y)][0]:null;
        const pct=cap?`${((s/1e6)/cap*100).toFixed(0)}%`:"";
        ROW(right,[{text:"  "+y,color:SUB,w:64},
                   {text:`$${(s/1e6).toFixed(1)}M`,color:TX,w:70},
                   {text:pct,color:SUB,w:44},
                   {text:isOpt?"option":"",color:THEME.accent,w:60}],10);
      }
    }
  }

  const leftW=measure(left)+PAD*2;
  const rightW=Math.max(measure(right)+PAD*2, 300*SC);
  const c=document.createElement("canvas"); c.width=leftW+chartW+rightW; c.height=chartH;
  const ctx=c.getContext("2d");
  ctx.fillStyle=THEME.bg; ctx.fillRect(0,0,c.width,c.height);

  // chart in the centre
  renderChart(ctx,state,leftW,0,chartW,chartH,SC);

  // dividers
  ctx.strokeStyle=THEME.legendLine; ctx.lineWidth=1*SC;
  ctx.beginPath(); ctx.moveTo(leftW,40*SC); ctx.lineTo(leftW,chartH-40*SC); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(leftW+chartW,40*SC); ctx.lineTo(leftW+chartW,chartH-40*SC); ctx.stroke();

  drawItems(ctx,left,PAD,46*SC);
  drawItems(ctx,right,leftW+chartW+PAD,46*SC);

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
let expandedPlayers=new Set();
// The chart highlight set is exactly the set of expanded player panels.
// They are one and the same, so highlighting and panels always match.
let highlightedPlayers=expandedPlayers;
let expandedYears=new Set();
let removeMode=new Set();   // player names whose "remove seasons" mode is active
let inlineForm=null;   // {name, mode:"extend"|"remove"} — open form inside a player card
let addPlayerOpen=false;   // is the inline "add player from another team" panel open?

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
    const expanded=expandedYears.has(r.yc);
    const cell=document.createElement("div"); cell.className="ysum-cell"+(expanded?" open":"");
    cell.style.background=`rgba(${rgb},0.10)`;
    cell.style.borderColor=`rgba(${rgb},0.45)`;
    const head=document.createElement("div"); head.className="ys-head";
    head.innerHTML=`<span class="ys-chev">▸</span>
      <span class="ys-yr">${r.yc}</span>
      <span class="ys-status" style="color:${lineClr}">${r.status}</span>
      <span class="ys-tot">$${r.total.toFixed(0)}M</span>`;
    head.onclick=()=>{ if(expandedYears.has(r.yc)) expandedYears.delete(r.yc); else expandedYears.add(r.yc); refreshTotals(); };
    cell.appendChild(head);
    if(expanded && r.breakdown){
      const body=document.createElement("div"); body.className="ys-body";
      const yr=parseInt(r.yc);
      // Growth control: every year except the fixed 2025-26 base year derives
      // its cap/tax/aprons from the prior year by this %.
      let growthHTML="";
      if(yr>BASE_YEAR){
        growthHTML=
          `<div class="ys-growth">`+
            `<span class="ysg-lbl">Increase vs prior year</span>`+
            `<input type="number" step="0.1" class="ysg-inp" id="growth-${yr}" value="${growthFor(yr).toFixed(1)}">`+
            `<span class="ysg-pct">%</span>`+
          `</div>`;
      }else{
        growthHTML=`<div class="ys-growth"><span class="ysg-lbl">Base year (actual values)</span></div>`;
      }
      let rows=growthHTML+`<div class="ys-bsub">${r.players}/15 players · payroll $${r.total.toFixed(1)}M</div><table class="yt-table"><tbody>`;
      // The breakdown rows run high→low (2nd Apron … Salary Floor). The payroll
      // sits just above the first line it clears, so insert a coloured marker row
      // — matching the box's status colour — at that boundary (or at the very top
      // if it's over the 2nd apron, or the very bottom if it's under the floor).
      const markerHTML=
        `<tr class="yt-marker"><td colspan="4"><div class="yt-payline" style="border-color:rgba(${rgb},0.45)"></div></td></tr>`;
      let markerPlaced=false;
      for(const b of r.breakdown){
        const over=b.value>=0, dot=tierLineColor(b.label);
        // Drop the marker just before the first line the payroll is above.
        if(over && !markerPlaced){ rows+=markerHTML; markerPlaced=true; }
        const arrow=over?"↑":"↓";
        const sign=over?"+":"−";
        rows+=`<tr><td class="yt-lbl"><span class="yt-dot" style="background:${dot}"></span>${b.label}</td>`+
              `<td class="yt-line">$${b.line.toFixed(1)}M</td>`+
              `<td class="yt-arrow">${arrow}</td>`+
              `<td class="yt-val">${sign}$${Math.abs(b.value).toFixed(1)}M</td></tr>`;
      }
      // Under the floor → payroll is below every line; marker goes at the bottom.
      if(!markerPlaced) rows+=markerHTML;
      rows+=`</tbody></table>`;
      body.innerHTML=rows;
      if(yr>BASE_YEAR){
        const inp=body.querySelector(`#growth-${yr}`);
        // Editing one year recompounds every later year too, so redraw fully.
        inp.onchange=()=>{
          const v=parseFloat(inp.value);
          if(isNaN(v)) { delete GROWTH[yr]; } else { GROWTH[yr]=v; }
          recomputeThresholds(); refreshTotals(); redrawChart();
        };
        // Don't let a click on the input collapse the cell.
        inp.onclick=e=>e.stopPropagation();
      }
      cell.appendChild(body);
    }
    box.appendChild(cell);
  }
  if(!box.children.length) box.innerHTML='<div class="muted">No data.</div>';
}
function tierLineColor(label){
  const t=TIERS.find(x=>x.key===label); return t?t.line:"#8A8A8A";
}

function rebuildSidebar(){
  refreshTotals();
  $("optCount").textContent=ST.active.length||"0";
  $("optHeader").classList.toggle("collapsed",optionsCollapsed);
  $("optionsBody").classList.toggle("collapsed",optionsCollapsed);
  const rl=$("rosterList"); rl.innerHTML="";

  for(const p of ST.rosterSorted()){
    const name=p["Player"];
    const total=ST.playerGuaranteed(p);
    const from=ST.addedFrom.get(name);
    const traded=ST.traded.get(name);
    const expanded=expandedPlayers.has(name);

    const card=document.createElement("div"); card.className="rost-card"+(expanded?" open selected":"");
    card.dataset.player=name;
    // header row (click to expand)
    const head=document.createElement("div"); head.className="rost-head";
    head.innerHTML=`<span class="rc-chev">▸</span>
      <span class="rc-name"></span>
      <span class="rc-total">$${(total/1e6).toFixed(1)}M</span>`;
    head.querySelector(".rc-name").textContent=name;
    // Name colour encodes change-state (replaces the old pill tags):
    //   acquired from another team → green
    //   has an extension on the books → blue
    //   has one or more seasons removed from the end → red
    // Priority when multiple apply: removed > extended > acquired.
    const hasExtTag=[...ST.extensions.keys()].some(k=>k.startsWith(name+"|"));
    const nameEl=head.querySelector(".rc-name");
    if(traded){ nameEl.classList.add("nm-rem"); nameEl.title="Seasons removed from "+traded+" onward"; }
    else if(hasExtTag){ nameEl.classList.add("nm-ext"); nameEl.title="Extended"; }
    else if(from){ nameEl.classList.add("nm-added"); nameEl.title="Acquired from "+from; }
    // revert-to-original button (top right, undo glyph) — only meaningful when expanded
    if(expanded){
      const rev=document.createElement("button"); rev.className="rc-revert"; rev.innerHTML="&#8634;";
      const hasMoves=ST.playerHasMoves(name);
      rev.title = hasMoves ? "Revert to original contract" : "No changes to revert";
      rev.disabled=!hasMoves;
      rev.onclick=(ev)=>{ ev.stopPropagation();
        ST.revertPlayer(name);
        if(inlineForm&&inlineForm.name===name) inlineForm=null;
        removeMode.delete(name);
        if(ST.isAddedPlayer(name)) expandedPlayers.delete(name);
        rebuildSidebar(); redrawChart(); };
      head.appendChild(rev);
    }
    head.onclick=()=>{ if(expandedPlayers.has(name)) expandedPlayers.delete(name); else expandedPlayers.add(name); rebuildSidebar(); redrawChart(); };
    card.appendChild(head);

    if(expanded){
      const body=document.createElement("div"); body.className="rost-body";
      const hasExtNow=[...ST.extensions.keys()].some(k=>k.startsWith(name+"|"));
      // Options freeze once an extension exists OR while the extension form is
      // open for this player — accepted/declined can't be changed during/after
      // an extension.
      const extFormOpenNow = inlineForm && inlineForm.name===name && inlineForm.mode==="extend";
      const optLocked = hasExtNow || extFormOpenNow;
      const rows=ST.contractRows(name);
      const inRemove=removeMode.has(name);
      // Removable years = any on-books season (CSV or extension), not declined.
      // Peeling happens from the LAST removable year. Extension years peel by
      // deleting that extension entry; CSV years peel via a trade cutoff.
      const removableIdx=rows.map((r,i)=>(!r.declined)?i:-1).filter(i=>i>=0);
      const lastRemovable=removableIdx.length?removableIdx[removableIdx.length-1]:-1;
      const myOptYears=new Set(ST.visibleOptions().filter(([n])=>n===name).map(([,y])=>y));

      if(inRemove){
        const hint=document.createElement("div"); hint.className="rc-rmhint";
        hint.textContent="Click the last season to remove it. Repeat to peel earlier seasons.";
        body.appendChild(hint);
      }

      rows.forEach((r,ri)=>{
        const cap=THRESHOLDS[parseInt(r.yc)]?THRESHOLDS[parseInt(r.yc)][0]:null;
        const pct=cap?`${((r.sal/1e6)/cap*100).toFixed(1)}%`:"";
        const d=document.createElement("div"); d.className="rc-year"+(r.declined?" rcy-declined":"");
        // Fixed-width tag slot keeps the salary/% columns aligned across every
        // row, regardless of whether this season carries an opt/ext/declined tag.
        let tag="", tagCls="";
        if(r.declined){ tag="dec"; tagCls="t-decl"; }
        else if(r.opt){ tag="opt"; tagCls="t-opt"; }
        else if(r.fromExt){ tag="ext"; tagCls="t-ext"; }
        let h=`<span class="rcy-yr">${r.yc}</span><span class="rcy-sal">${fmtM(r.sal)}</span>`+
              `<span class="rcy-pct">${pct}</span>`+
              `<span class="rcy-tag ${tagCls}">${tag}</span>`;
        d.innerHTML=h;

        // ── Remove-mode: turn removable rows into clickable red boxes ──
        // Only the LAST removable season is actionable; earlier ones show locked.
        if(inRemove){
          const isRemovable=!r.declined;
          const sp=document.createElement("span"); sp.className="rcy-spacer"; d.appendChild(sp);
          if(isRemovable){
            d.classList.add("rcy-removable");
            if(ri===lastRemovable){
              d.title=`Remove ${r.yc}`;
              d.onclick=(ev)=>{ev.stopPropagation();
                if(r.fromExt) ST.removeExtensionYear(name, r.yc);  // peel one extension year
                else ST.trade(name, r.yc);                         // cut CSV seasons from here on
                rebuildSidebar(); redrawChart();};
            }else{
              d.classList.add("rcy-locked");
              d.title="Remove the last season first";
            }
          }
          body.appendChild(d);
          return;   // skip option buttons while peeling seasons
        }

        // Inline option accept/decline — shown only on the CSV option row (never
        // on an extension row). It is INTERACTIVE only while the player has no
        // extension; once an extension is being/has been added, the option's
        // accepted/declined state is frozen (buttons disabled, current choice
        // still visible). A declined option year stays here, crossed out.
        const isOptionRow = myOptYears.has(r.yc) && !r.fromExt;
        if(isOptionRow){
          const cur=ST.optionStates.get(ST.key(name,r.yc));
          const seg=document.createElement("span"); seg.className="rcy-opt-seg";
          const dis=optLocked?"disabled":"";
          seg.innerHTML=`<button class="ob ob-acc ${cur==="accepted"?"on-acc":""}" data-s="accepted" ${dis} title="Accept option">Accept</button>`+
                        `<button class="ob ob-dec ${cur==="declined"?"on-dec":""}" data-s="declined" ${dis} title="Decline option">Decline</button>`;
          if(!optLocked) seg.querySelectorAll(".ob").forEach(b=>b.onclick=(ev)=>{ev.stopPropagation();
            const next=(cur===b.dataset.s)?"pending":b.dataset.s;
            ST.setOptionState(name,r.yc,next); rebuildSidebar(); redrawChart();});
          d.appendChild(seg);
        }else{
          const sp=document.createElement("span"); sp.className="rcy-spacer"; d.appendChild(sp);
        }
        body.appendChild(d);
      });

      // If years were removed via the × control, offer to restore them.
      if(traded){
        const ur=document.createElement("div"); ur.className="rc-addyear"; ur.style.borderColor="var(--red)"; ur.style.color="var(--red)";
        ur.innerHTML=`<span class="ay-plus">&#8634;</span><span>Restore removed seasons (from ${traded})</span>`;
        ur.onclick=()=>{ST.undoTrade(name); rebuildSidebar(); redrawChart();};
        body.appendChild(ur);
      }

      // option lock note when a committed extension is freezing a CSV option
      const hasCsvOptionRow = rows.some(r=>!r.fromExt && (r.opt||r.declined) && myOptYears.has(r.yc));
      if(!inRemove && hasExtNow && hasCsvOptionRow){
        const lk=document.createElement("div"); lk.className="opt-lock"; lk.textContent="option locked — remove the extension to change it";
        body.appendChild(lk);
      }

      // ── Remove-seasons toggle ──
      // A dedicated button (above the extension control). When active, on-books
      // year rows become clickable red boxes that peel off from the last year.
      const canRemove = lastRemovable>=0;
      const rmBtn=document.createElement("div");
      rmBtn.className="rc-addyear rc-removeyear"+(inRemove?" active":"")+((!canRemove&&!inRemove)?" disabled":"");
      rmBtn.innerHTML=`<span class="ay-plus">${inRemove?"✓":"–"}</span>`+
        `<span>${inRemove?"Done removing seasons":(canRemove?"Remove seasons":"No seasons to remove")}</span>`;
      if(canRemove||inRemove){
        rmBtn.onclick=()=>{
          if(removeMode.has(name)) removeMode.delete(name); else removeMode.add(name);
          rebuildSidebar(); };
      }
      body.appendChild(rmBtn);

      // ── Add-extension affordance ──
      // A single inline form stages one OR MORE consecutive years and commits
      // them together. Extension years are removed the same way as standard
      // years — via the remove-seasons toggle — so there's no separate remove button.
      const canExt=ST.expiringContracts().some(([n])=>n===name);
      const extFormOpen = inlineForm && inlineForm.name===name && inlineForm.mode==="extend";
      if(inRemove){
        /* remove-mode: no extension controls */
      }else if(extFormOpen){
        body.appendChild(buildExtendForm(name));
      }else if(canExt){
        const ay=document.createElement("div"); ay.className="rc-addyear";
        const nextYr=extNextYear(name);
        ay.innerHTML=`<span class="ay-plus">+</span><span>${hasExtNow?`Add year (${nextYr})`:`Add extension (${nextYr})`}</span>`;
        ay.onclick=()=>{ inlineForm={name,mode:"extend"}; inlineExtRows=[]; rebuildSidebar(); };
        body.appendChild(ay);
      }else if(!hasExtNow){
        const ay=document.createElement("div"); ay.className="rc-addyear disabled";
        ay.innerHTML=`<span class="ay-plus">+</span><span>${ST.hasPendingOption(name)?"Resolve option to extend":"No season available to extend"}</span>`;
        body.appendChild(ay);
      }

      card.appendChild(body);
    }
    rl.appendChild(card);
  }

  // "add player" — toggles an inline panel (no pop-up)
  const add=document.createElement("div"); add.className="rost-add"+(addPlayerOpen?" open":"");
  add.innerHTML=`<span class="ra-plus">${addPlayerOpen?"×":"+"}</span><span class="ra-label">Add player</span>`;
  add.onclick=()=>{ addPlayerOpen?closeAddPlayer():openAddPlayerPanel(); };
  rl.appendChild(add);

  if(addPlayerOpen){
    rl.appendChild(buildAddPlayerPanel());
    // populate the freshly-built selects for whichever mode is active
    if(addPlayerMode==="draft") rebuildDraftControls();
    else rebuildAddPlayerTeams();
  }
}

/* Build the inline add-player panel DOM. Two modes: add an existing player
   from another team (the original behavior) or add a drafted rookie whose
   salary comes from the rookie scale. The mode toggle swaps which block of
   controls is shown; element IDs are preserved so existing handlers work. */
function buildAddPlayerPanel(){
  const wrap=document.createElement("div"); wrap.className="add-panel";
  const leagueOn=addPlayerMode==="league";
  wrap.innerHTML=
    `<div class="ap-title">Add player</div>`+
    `<div class="ap-mode">`+
      `<button id="apModeLeague" class="${leagueOn?"on":""}">From league</button>`+
      `<button id="apModeDraft" class="${leagueOn?"":"on"}">Draft pick</button>`+
    `</div>`+
    // ── League block ──
    // ── League block: season, then team, then player ──
    `<div id="apLeague" style="display:${leagueOn?"block":"none"}">`+
      `<div class="ap-label">Join in season</div><select id="addPlayerYear"></select>`+
      `<div class="ap-label">From team</div><select id="addPlayerTeam"></select>`+
      `<div class="ap-label">Player</div><select id="addPlayerSelect"></select>`+
    `</div>`+
    // ── Draft block: season + pick (inline), then name ──
    `<div id="apDraft" style="display:${leagueOn?"none":"block"}">`+
      `<div class="ap-draftrow">`+
        `<div class="ap-col"><div class="ap-label">Rookie season</div><select id="draftYear"></select></div>`+
        `<div class="ap-col ap-col-pick"><div class="ap-label">Pick</div>`+
          `<input type="number" id="draftPick" min="1" max="30" step="1" value="1" placeholder="1–30"></div>`+
      `</div>`+
      `<div class="ap-label">Player name</div>`+
      `<input type="text" id="draftName" placeholder="Player name" autocomplete="off">`+
    `</div>`+
    `<div class="ap-preview" id="addPlayerPreview"></div>`+
    `<div class="ap-err" id="addPlayerErr"></div>`+
    `<div class="ap-btns">`+
      `<button id="addPlayerCancel">Cancel</button>`+
      `<button class="b-green" id="addPlayerSubmit">Add to roster</button>`+
    `</div>`;
  // mode toggle
  wrap.querySelector("#apModeLeague").onclick=()=>{ if(addPlayerMode!=="league"){addPlayerMode="league"; rebuildSidebar(); rebuildAddPlayerTeams();} };
  wrap.querySelector("#apModeDraft").onclick=()=>{ if(addPlayerMode!=="draft"){addPlayerMode="draft"; rebuildSidebar(); rebuildDraftControls();} };
  // league handlers
  wrap.querySelector("#addPlayerTeam").onchange=rebuildAddPlayerList;
  wrap.querySelector("#addPlayerSelect").onchange=()=>rebuildAddPlayerYears();
  wrap.querySelector("#addPlayerYear").onchange=updateAddPlayerPreview;
  // draft handlers
  wrap.querySelector("#draftName").oninput=updateDraftPreview;
  wrap.querySelector("#draftPick").oninput=updateDraftPreview;
  wrap.querySelector("#draftYear").onchange=updateDraftPreview;
  // shared
  wrap.querySelector("#addPlayerCancel").onclick=closeAddPlayer;
  wrap.querySelector("#addPlayerSubmit").onclick=submitAddPlayer;
  return wrap;
}

/* ── Inline extension entry (rendered inside a player card) ──
   Holds one or more consecutive years that are committed together in a single
   move. Each entry: {yr, unit:"dollar"|"percent", value:Number, isOpt:Bool}. */
let inlineExtRows=[];   // working rows for the open extension form
function capForYearM(yr){const t=THRESHOLDS[parseInt(yr)]; return (t?t[0]:154.647);}
// The next season available to extend into = the season right after the player's
// current last contracted year (their expiring year).
function extNextYear(name){
  const exp=ST.expiringContracts().find(([n])=>n===name);
  if(!exp) return null;
  const i=ST.yearCols.indexOf(exp[1]);
  return ST.yearCols[i+1]||null;
}
// The season following the last year currently staged in the open form (so the
// form can offer consecutive years without committing first).
function extFormNextYear(name){
  const first=extNextYear(name); if(!first) return null;
  if(!inlineExtRows.length) return first;
  const lastYr=inlineExtRows[inlineExtRows.length-1].yr;
  const i=ST.yearCols.indexOf(lastYr);
  return ST.yearCols[i+1]||null;
}
function buildExtendForm(name){
  const wrap=document.createElement("div"); wrap.className="inline-form";
  const first=extNextYear(name);
  if(!first){ wrap.innerHTML='<div class="if-err">No season available to extend into.</div>'; return wrap; }

  // Years already committed as part of this player's extension (across earlier
  // sessions). The final year of an extension may be an option only when the
  // extension spans 2+ years total, so these count toward that length.
  const existingExtCount=[...ST.extensions.keys()].filter(k=>k.startsWith(name+"|")).length;

  // Seed the first staged row if the form just opened.
  if(!inlineExtRows.length){
    inlineExtRows=[{yr:first, unit:"dollar", value:NaN, isOpt:false}];
  }

  const title=document.createElement("div"); title.className="if-title";
  title.textContent="Add extension";
  wrap.appendChild(title);

  // Render one editable line per staged year.
  inlineExtRows.forEach((er,ri)=>{
    const yr=er.yr;
    const row=document.createElement("div"); row.className="if-row";
    row.innerHTML=`<span class="ifr-yr">${yr}</span>
      <input type="number" step="0.1" min="0" placeholder="0.0">
      <div class="unit-tog">
        <button data-u="dollar" class="${er.unit==="dollar"?"on":""}">$M</button>
        <button data-u="percent" class="${er.unit==="percent"?"on":""}">% cap</button>
      </div><span class="ifr-calc"></span>`;
    const inp=row.querySelector("input");
    const calc=row.querySelector(".ifr-calc");
    if(!isNaN(er.value)) inp.value=er.value;
    function upd(){ if(isNaN(er.value)){calc.textContent=""; return;}
      if(er.unit==="percent") calc.textContent=`= $${(capForYearM(yr)*er.value/100).toFixed(1)}M`;
      else calc.textContent=`= ${(er.value/capForYearM(yr)*100).toFixed(1)}%`; }
    inp.oninput=()=>{er.value=parseFloat(inp.value); upd();};
    row.querySelectorAll(".unit-tog button").forEach(b=>b.onclick=()=>{
      er.unit=b.dataset.u;
      row.querySelectorAll(".unit-tog button").forEach(x=>x.classList.toggle("on",x===b)); upd();});
    wrap.appendChild(row);
    upd();

    // Option-year toggle — only the FINAL year of an extension may be an option,
    // and only when the extension spans more than one year total (a one-year
    // extension is always guaranteed). Counts years committed earlier too.
    const isLastStaged = ri===inlineExtRows.length-1;
    const totalExtYears = existingExtCount + inlineExtRows.length;
    if(isLastStaged && totalExtYears>1){
      const optBtn=document.createElement("button"); optBtn.className="rc-btn if-optbtn";
      const paint=()=>{ optBtn.textContent=er.isOpt?"✓ Final year is an option":"Make final year an option";
        optBtn.classList.toggle("on", er.isOpt); };
      optBtn.onclick=()=>{ er.isOpt=!er.isOpt; paint(); };
      paint();
      wrap.appendChild(optBtn);
    }
  });

  // "Add another year" — appends the next consecutive season as a new staged row.
  // Whatever year was previously last can no longer be an option (only the final
  // year may be), so clear its option flag as it loses "last" status.
  const moreYr=extFormNextYear(name);
  if(moreYr){
    const more=document.createElement("div"); more.className="rc-addyear";
    more.innerHTML=`<span class="ay-plus">+</span><span>Add another year (${moreYr})</span>`;
    more.onclick=()=>{
      if(inlineExtRows.length) inlineExtRows[inlineExtRows.length-1].isOpt=false;
      inlineExtRows.push({yr:moreYr, unit:"dollar", value:NaN, isOpt:false});
      rebuildSidebar(); };
    wrap.appendChild(more);
  }

  const err=document.createElement("div"); err.className="if-err"; wrap.appendChild(err);
  const btns=document.createElement("div"); btns.className="if-btns";
  const cancel=document.createElement("button"); cancel.className="rc-btn"; cancel.textContent="Cancel";
  cancel.onclick=()=>{ inlineForm=null; inlineExtRows=[]; rebuildSidebar(); };
  const apply=document.createElement("button"); apply.className="rc-btn rc-extend";
  apply.textContent=inlineExtRows.length>1?"Add extension":"Add year";
  apply.onclick=()=>{
    err.textContent="";
    // Validate every staged year before committing any.
    for(const er of inlineExtRows){
      if(isNaN(er.value)||er.value<0){err.textContent=`Enter a salary for ${er.yr}.`; return;}
    }
    const totalExtAtCommit = existingExtCount + inlineExtRows.length;
    for(const er of inlineExtRows){
      const isFinal = er===inlineExtRows[inlineExtRows.length-1];
      const v = er.unit==="percent" ? capForYearM(er.yr)*er.value/100*1e6 : er.value*1e6;
      const label = er.unit==="percent" ? `${er.value.toFixed(1)}% of cap = $${(v/1e6).toFixed(2)}M` : `$${(v/1e6).toFixed(2)}M`;
      // Only the final year of a 2+ year extension may be an option.
      const asOption = isFinal && totalExtAtCommit>1 && er.isOpt;
      ST.addExtension(name,er.yr,v,asOption,label);
    }
    inlineForm=null; inlineExtRows=[]; rebuildSidebar(); redrawChart();
  };
  btns.appendChild(cancel); btns.appendChild(apply); wrap.appendChild(btns);
  return wrap;
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
  expandedPlayers.clear(); expandedYears=new Set(); removeMode=new Set(); inlineForm=null; addPlayerOpen=false;
  rebuildStartSelector(); rebuildSidebar(); redrawChart();
}
function rebuildTeamSelector(selected){
  const sel=$("teamSelect"); sel.innerHTML="";
  for(const name of Object.keys(TEAMS)){
    const o=document.createElement("option"); o.value=name; o.textContent=name; sel.appendChild(o);}
  sel.value=selected;
}
$("teamSelect").onchange=e=>loadTeam(e.target.value);

$("exportBtn").onclick=()=>{if(ST) exportPNG(ST);};

/* Chart colours are read once from the (dark) CSS theme. */
refreshTheme();

/* ════ MOUSE INTERACTION LISTENERS ════ */
canvas.addEventListener("mousemove", (e) => {
  if (!ST) return;
  if (highlightedPlayers.size) return;   // one or more panels open; skip hover tooltip
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

// ── Click a segment to select a player (highlight across years + panel) ──
function segmentAtEvent(e){
  if(!ST) return null;
  const rect=canvas.getBoundingClientRect();
  const dpr=window.devicePixelRatio||1;
  const mx=(e.clientX-rect.left)*dpr, my=(e.clientY-rect.top)*dpr;
  const data=ST.chartData();
  const years=ST.displayYears().filter(y=>data.has(y));
  if(!years.length) return null;
  const s=dpr*(rect.width<900?0.85:1);
  const mL=58*s,mR=86*s,mT=34*s,mB=34*s;
  const pw=canvas.width-mL-mR, ph=canvas.height-mT-mB;
  const slotW=pw/years.length, barW=Math.min(slotW*0.62,150*s);
  let maxV=0;
  for(const yc of years){maxV=Math.max(maxV,data.get(yc).reduce((a,e)=>a+e[1],0)/1e6);
    const t=THRESHOLDS[parseInt(yc)]; if(t) maxV=Math.max(maxV,t[3]);}
  maxV*=1.07;
  const Y=v=>mT+ph-(v/maxV)*ph;
  for(let i=0;i<years.length;i++){
    const yc=years[i], cx=mL+slotW*(i+0.5);
    if(mx>=cx-barW/2 && mx<=cx+barW/2){
      let bottom=0;
      for(const [name,sal] of data.get(yc)){
        const top=Y((bottom+sal)/1e6), base=Y(bottom/1e6);
        if(my>=top && my<=base) return name;
        bottom+=sal;
      }
    }
  }
  return null;
}
canvas.addEventListener("click",(e)=>{
  const name=segmentAtEvent(e);
  // Clicking empty space clears everything.
  if(!name){ clearSelection(); return; }
  // Clicking an already-highlighted player deselects it (and closes its panel).
  if(expandedPlayers.has(name)){
    expandedPlayers.delete(name);
    if(inlineForm && inlineForm.name===name) inlineForm=null;
    rebuildSidebar();
    redrawChart();
    return;
  }
  // Otherwise add this player to the highlight set and open its panel,
  // leaving any other selected players in place.
  expandedPlayers.add(name);
  activeTooltip=null;            // hide the small hover tip
  // Make sure the ROSTER section is open so the card is visible, then scroll to it.
  if(optionsCollapsed){ optionsCollapsed=false; }
  rebuildSidebar();
  redrawChart();
  const card=document.querySelector(`.rost-card[data-player="${cssEsc(name)}"]`);
  if(card && card.scrollIntoView) card.scrollIntoView({block:"nearest"});
});
function cssEsc(s){ return (window.CSS&&CSS.escape)?CSS.escape(s):s.replace(/"/g,'\\"'); }
function clearSelection(){
  if(!expandedPlayers.size) return;
  expandedPlayers.clear();
  inlineForm=null;
  rebuildSidebar();
  redrawChart();
}

// ── (Floating player panel removed — selecting a player now expands their
//     roster card instead. Expanded panels and chart highlights are the same
//     set, so they always match: expanding/clicking adds a highlight, closing
//     a panel or clicking a highlighted bar removes it.) ──

/* ── Add Player (inline panel) ── */
let addPlayerCache=[];   // players for the currently-selected source team
let addPlayerMode="league";   // "league" (from another team) or "draft" (rookie scale)
function otherTeamNames(){
  return Object.keys(TEAMS).filter(t=>t!==ST.teamName);
}
function openAddPlayerPanel(){
  if(!ST) return;
  // Draft mode needs no other teams; only force draft if none are available.
  if(!otherTeamNames().length) addPlayerMode="draft";
  addPlayerOpen=true;
  rebuildSidebar();
  // scroll the panel into view once it's in the DOM
  const panel=document.querySelector(".add-panel");
  if(panel && panel.scrollIntoView) panel.scrollIntoView({block:"nearest"});
}
function closeAddPlayer(){
  if(!addPlayerOpen) return;
  addPlayerOpen=false;
  rebuildSidebar();
}
// Populate the team dropdown, then cascade to players/years/preview.
function rebuildAddPlayerTeams(){
  const tsel=$("addPlayerTeam"); if(!tsel) return;
  const others=otherTeamNames();
  tsel.innerHTML="";
  for(const t of others){const o=document.createElement("option"); o.value=t; o.textContent=t; tsel.appendChild(o);}
  tsel.value=others[0];
  $("addPlayerErr").textContent="";
  rebuildAddPlayerList();
}
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
// Handlers are bound inside buildAddPlayerPanel (the panel is rebuilt on each
// rebuildSidebar). submitAddPlayer adds the player and closes the panel.

/* ── Draft pick mode ──
   Pick is a number box (1–30). Populate the rookie-season dropdown, then build a
   rookie-scale contract: four consecutive seasons from the chosen entry year,
   years 1–2 guaranteed and years 3–4 as team options. */
function rebuildDraftControls(){
  const ysel=$("draftYear"); if(!ysel) return;
  if(!ysel.options.length){
    // Rookie season can be any charted season (the deal runs 4 years from there;
    // seasons past the chart's end are simply not shown).
    ST.yearCols.forEach((yc,idx)=>{const o=document.createElement("option"); o.value=idx; o.textContent=yc; ysel.appendChild(o);});
    ysel.value=0;
  }
  updateDraftPreview();
}
/* Build a rookie contract dict ({Player, Age, <year>…, Guaranteed}) for a pick
   entering at startYearIdx. Years 1–2 are guaranteed; years 3–4 are options, so
   Guaranteed is set to the sum of the first two on-chart seasons — which makes
   RosterState.determineOption flag years 3 & 4 as options automatically. */
function buildRookieContract(name, pick, startYearIdx){
  const enterYear=parseInt(ST.yearCols[startYearIdx]);   // e.g. 2026
  const sals=rookieSalaries(pick, enterYear);            // [Y1,Y2,Y3opt,Y4opt]
  if(!sals) return null;
  const dict={"Player":name||("Pick #"+pick),"Age":""};
  for(const yc of ST.yearCols) dict[yc]="";
  let guaranteed=0;
  for(let k=0;k<4;k++){
    const idx=startYearIdx+k;
    if(idx>=ST.yearCols.length) break;                   // runs past the chart → drop
    const yc=ST.yearCols[idx];
    dict[yc]="$"+Math.round(sals[k]).toLocaleString("en-US");
    if(k<2) guaranteed+=Math.round(sals[k]);             // first two years guaranteed
  }
  dict[ST.guaranteedCol]="$"+guaranteed.toLocaleString("en-US");
  return dict;
}
function updateDraftPreview(){
  const box=$("addPlayerPreview"); if(!box) return;
  const name=($("draftName").value||"").trim();
  const pick=parseInt($("draftPick").value);
  const startIdx=parseInt($("draftYear").value)||0;
  if(isNaN(pick)||pick<1||pick>ROOKIE_SCALE.length){
    box.innerHTML=`<span style="color:var(--orange)">Enter a pick from 1 to ${ROOKIE_SCALE.length}.</span>`; return;
  }
  const dict=buildRookieContract(name,pick,startIdx);
  if(!dict){box.textContent=""; return;}
  const guar=parseSalary(dict[ST.guaranteedCol]);
  const parts=ST.yearCols.map(yc=>{
    const s=parseSalary(dict[yc]); if(!s) return null;
    // option = a season beyond the guaranteed total (years 3–4)
    let run=0,opt=false;
    for(const y of ST.yearCols){const v=parseSalary(dict[y]); if(v==null)continue; run+=v; if(y===yc){opt=run>guar+1; break;}}
    return `${yc}: ${fmtM(s)}${opt?"  (option)":""}`;}).filter(Boolean);
  const shown=ST.yearCols.filter(yc=>parseSalary(dict[yc])).length;
  box.innerHTML="Rookie contract (2 guaranteed + 2 option):<br>"+(parts.join("<br>")||"(no seasons on chart)")
    +(shown<4?`<br><span style="color:var(--orange)">${4-shown} season(s) fall past the chart's end</span>`:"");
}

function submitAddPlayer(){
  const err=$("addPlayerErr"); err.textContent="";
  if(addPlayerMode==="draft"){
    const name=($("draftName").value||"").trim();
    if(!name){err.textContent="Enter the player's name."; return;}
    if(ST.active.some(p=>p["Player"]===name)){err.textContent="A player with that name is already on the roster."; return;}
    const pick=parseInt($("draftPick").value);
    if(isNaN(pick)||pick<1||pick>ROOKIE_SCALE.length){err.textContent="Enter a pick from 1 to "+ROOKIE_SCALE.length+"."; return;}
    const startIdx=parseInt($("draftYear").value)||0;
    const dict=buildRookieContract(name,pick,startIdx);
    if(!dict || !ST.yearCols.some(yc=>parseSalary(dict[yc]))){
      err.textContent="That rookie season leaves no years on the chart. Pick an earlier season."; return;
    }
    ST.addPlayer(dict, "Draft");
    addPlayerOpen=false; rebuildSidebar(); redrawChart();
    return;
  }
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
  addPlayerOpen=false; rebuildSidebar(); redrawChart();
}

/* ── Extension dialog ── */
const extDlg=$("extDialog"); let extExpiring=[];
function openExtensionDialog(preName){
  if(!ST) return;
  extExpiring=ST.expiringContracts();
  if(!extExpiring.length){alert("No players with expiring contracts found."); return;}
  const sel=$("extPlayer"); sel.innerHTML="";
  extExpiring.forEach(([n,y,s],i)=>{const o=document.createElement("option");
    o.value=i; o.textContent=`${n} — last year ${y} (${fmtM(s)})`; sel.appendChild(o);});
  let idx=0;
  if(preName){ const fi=extExpiring.findIndex(([n])=>n===preName); if(fi>=0) idx=fi; }
  sel.value=idx; $("extOptFlag").checked=false; $("extErr").textContent="";
  extRowState={};
  rebuildExtYears(); extDlg.showModal();
}
function openExtensionFor(name){
  // A pending option must be resolved before extending.
  if(ST.hasPendingOption(name)){
    alert(`${name} has a pending option. Accept or decline it in the Manage section before extending.`);
    return;
  }
  const can=ST.expiringContracts().some(([n])=>n===name);
  if(!can){ alert(`${name} has no expiring contract to extend (their deal already runs to the last charted season).`); return; }
  clearSelection();
  openExtensionDialog(name);
}
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
function openTradeDialog(preName){
  if(!ST) return;
  tradeRoster=ST.rosterOnBooks().filter(([n])=>!ST.traded.has(n));
  if(!tradeRoster.length){alert("No players left on the books."); return;}
  const sel=$("tradePlayer"); sel.innerHTML="";
  tradeRoster.forEach(([n,yrs],i)=>{const span=yrs.length>1?`${yrs[0]} – ${yrs[yrs.length-1]}`:yrs[0];
    const o=document.createElement("option"); o.value=i; o.textContent=`${n}   (${span})`; sel.appendChild(o);});
  let idx=0;
  if(preName){ const fi=tradeRoster.findIndex(([n])=>n===preName); if(fi>=0) idx=fi; }
  sel.value=idx; rebuildTradeYears(); $("tradeErr").textContent=""; tradeDlg.showModal();
}
function openRemoveFor(name){
  if(ST.traded.has(name)){ alert(`${name} is already removed from ${ST.traded.get(name)} onward.`); return; }
  clearSelection();
  openTradeDialog(name);
}
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