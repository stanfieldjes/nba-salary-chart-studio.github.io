#!/usr/bin/env python3
"""Generate a self-contained NBA salary-chart web app.

Usage: python build_salary_app.py [csv_folder] [output_html]
Defaults: csv_folder="csv", output_html="nba_salary_chart.html".

Scans every *.csv in the folder and embeds them into one offline HTML file.
Each CSV's name (minus .csv) becomes the team label (e.g. OKC.csv -> OKC).
An optional players.csv enriches expanded player cards and is not treated as
a team file.
"""

import csv
import io
import json
import os
import re
import sys

PLAYERS_FILENAME = "players.csv"


def parse_salary(value):
    v = (value or "").strip().replace("$", "").replace(",", "")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def load_team_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.reader(f))

    header_idx = next((i for i, r in enumerate(raw) if r and r[0].strip() == "Player"), None)
    if header_idx is None:
        raise ValueError("no header row starting with 'Player'")

    headers = [h.strip() for h in raw[header_idx]]
    year_cols = [h for h in headers if re.match(r"\d{4}-\d{2}", h)]
    if not year_cols:
        raise ValueError("no season columns (e.g. 2025-26) found")

    players = []
    for row in raw[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        d = dict(zip(headers, [c.strip() for c in row]))
        if d.get("Player"):
            players.append(d)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for d in players:
        w.writerow([d.get(h, "") for h in headers])
    return {"yearCols": year_cols, "csv": buf.getvalue()}


def discover_teams(folder):
    if not os.path.isdir(folder):
        raise SystemExit(f"CSV folder not found: {folder}\n"
                         f"Create it and drop one CSV per team inside (e.g. {folder}/OKC.csv).")

    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith(".csv") and f.lower() != PLAYERS_FILENAME.lower())
    if not files:
        raise SystemExit(f"No team .csv files in {folder}. Add at least one team CSV.")

    teams = {}
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


def load_players(folder):
    """Load the optional players.csv into a name -> info lookup for the app.

    Also stores a "TEAM|Name" key to disambiguate duplicate names. A missing
    file is not an error.
    """
    path = os.path.join(folder, PLAYERS_FILENAME)
    if not os.path.isfile(path):
        print(f"  (no {PLAYERS_FILENAME} found — player info strips will be omitted)")
        return {}

    fields = ("team", "position", "height", "weight", "bday")
    by_name = {}
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            info = {k: (row.get(k) or "").strip() for k in fields}
            by_name[name] = info
            if info["team"]:
                by_name[f"{info['team']}|{name}"] = info
            count += 1
    print(f"  embedded player info ({count} players from {PLAYERS_FILENAME})")
    return by_name


def build_html(teams, players=None):
    return (HTML_TEMPLATE
            .replace("/*__TEAM_DATA__*/", json.dumps(teams, ensure_ascii=False))
            .replace("/*__PLAYER_DATA__*/", json.dumps(players or {}, ensure_ascii=False)))


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
    /* Year-slider greys (dark) */
    --ysl-fill:rgba(190,190,190,0.20); --ysl-fill-active:rgba(190,190,190,0.30);
    --ysl-edge:#8A8A8A; --ysl-handle:#9A9A9A; --ysl-handle-grip:#1A1A1A;
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
    /* Year-slider greys (light) */
    --ysl-fill:rgba(70,80,90,0.16); --ysl-fill-active:rgba(70,80,90,0.26);
    --ysl-edge:#8A929C; --ysl-handle:#6B7280; --ysl-handle-grip:#FFFFFF;
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
  #chartcol{flex:1; min-width:0; display:flex; flex-direction:column;}
  #chartwrap{flex:1; min-width:0; position:relative; background:var(--chart-bg);}
  #chart{position:absolute; inset:10px; width:calc(100% - 20px); height:calc(100% - 20px); cursor:pointer;}

  /* ── Year-range slider beneath the chart (custom, themed) ── */
  #yearSliderBar{
    flex:0 0 auto; display:flex; align-items:center; gap:14px;
    padding:12px 24px 14px; background:var(--sidebar); border-top:1px solid var(--line);
  }
  #yearSlider{
    position:relative; flex:1; height:42px; user-select:none; touch-action:none;
  }
  /* base rail */
  #yearSlider .ysl-rail{
    position:absolute; left:0; right:0; top:8px; height:24px; border-radius:7px;
    background:var(--card); border:1px solid var(--line);
  }
  /* per-season tick segments live in here */
  #yearSlider .ysl-ticks{position:absolute; left:0; right:0; top:8px; height:24px;}
  #yearSlider .ysl-tick{
    position:absolute; top:0; height:24px; display:flex; align-items:center; justify-content:center;
    font:10px/1 Consolas,Menlo,monospace; color:var(--subtext); white-space:nowrap;
    border-left:1px solid var(--line); cursor:pointer; overflow:hidden;
  }
  #yearSlider .ysl-tick:first-child{border-left:none;}
  #yearSlider .ysl-tick.in-range{color:var(--text); font-weight:700;}
  /* highlighted selection window — draggable to shift the whole range */
  #yearSlider .ysl-fill{
    position:absolute; top:8px; height:24px; border-radius:7px; cursor:grab;
    background:var(--ysl-fill);
    border:1px solid var(--ysl-edge); box-sizing:border-box; pointer-events:auto;
  }
  #yearSlider .ysl-fill:active{cursor:grabbing;}
  #yearSlider.dragging-fill .ysl-fill{background:var(--ysl-fill-active);}
  /* draggable end handles */
  #yearSlider .ysl-handle{
    position:absolute; top:2px; width:14px; height:36px; border-radius:6px;
    background:var(--ysl-handle); border:1px solid var(--bg);
    box-shadow:0 1px 4px rgba(0,0,0,.5); cursor:ew-resize; transform:translateX(-50%);
    display:flex; align-items:center; justify-content:center; z-index:3;
  }
  #yearSlider .ysl-handle::before{
    content:""; width:2px; height:16px; border-radius:2px;
    background:var(--ysl-handle-grip); opacity:.8;
  }
  #yearSlider .ysl-handle:hover{filter:brightness(1.12);}
  #yearSlider .ysl-handle:focus-visible{outline:2px solid var(--text); outline-offset:2px;}


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
  /* Player info strip — a single horizontal bio line above the salary rows. */
  .rc-pinfo{display:flex; align-items:center; gap:7px; flex-wrap:nowrap;
    padding:5px 2px 6px; margin-bottom:3px; border-bottom:1px solid var(--line);
    font:11px/1.3 'Segoe UI',Arial,sans-serif; white-space:nowrap; overflow:hidden;}
  .rc-pinfo .pi-item{display:inline-flex; align-items:baseline; gap:4px; min-width:0;}
  .rc-pinfo .pi-k{color:var(--subtext); font-size:9px; font-weight:600;
    letter-spacing:.4px; text-transform:uppercase;}
  .rc-pinfo .pi-v{color:var(--text); font-weight:600;}
  .rc-pinfo .pi-sep{color:var(--subtext); opacity:.5;}
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
  .add-panel .ap-contract.inline-form{margin-top:4px; padding-top:0; border-top:none;}
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
  /* pick grid: 3 rows of 10 selectable boxes (1–30) */
  .add-panel .ap-pickgrid{display:grid; grid-template-columns:repeat(10,1fr); gap:4px; margin:2px 0 2px;}
  .add-panel .ap-pickcell{padding:5px 0; font-size:11px; font-weight:600; cursor:pointer;
    color:var(--text); background:var(--sidebar); border:1px solid var(--line); border-radius:4px;
    text-align:center; transition:background .1s,border-color .1s;}
  .add-panel .ap-pickcell:hover{border-color:var(--accent); color:var(--accent);}
  .add-panel .ap-pickcell.on{color:#fff; background:var(--accent); border-color:var(--accent);}
  /* reworked add-player: league filter row, list, preview card */
  .add-panel .ap-filterrow{display:flex; gap:8px; align-items:flex-end;}
  .add-panel .ap-filterrow .ap-filtercol-team{flex:0 0 96px;}
  .add-panel .ap-filterrow .ap-filtercol-search{flex:1;}
  .add-panel .ap-list{margin-top:7px; max-height:188px; overflow-y:auto;
    border:1px solid var(--line); border-radius:6px; background:var(--sidebar);}
  .add-panel .ap-list::-webkit-scrollbar{width:8px;}
  .add-panel .ap-list::-webkit-scrollbar-thumb{background:#3a3a3a; border-radius:5px;}
  .add-panel .apl-row{display:flex; align-items:center; gap:7px; padding:5px 9px;
    cursor:pointer; border-bottom:1px solid var(--line); font-size:11.5px;}
  .add-panel .apl-row:last-child{border-bottom:none;}
  .add-panel .apl-row:hover{background:rgba(94,168,237,0.12);}
  .add-panel .apl-row.sel{background:rgba(94,168,237,0.20);}
  .add-panel .apl-row .apl-name{flex:1; color:var(--text); white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis;}
  .add-panel .apl-row .apl-pos{color:var(--subtext); font-size:9.5px; font-weight:600;
    letter-spacing:.3px; flex:0 0 auto;}
  .add-panel .apl-row .apl-team{color:var(--subtext); font-size:9.5px; font-weight:700;
    letter-spacing:.4px; flex:0 0 30px; text-align:right;}
  .add-panel .apl-empty{padding:10px; text-align:center; color:var(--subtext); font-size:10.5px;}
  .add-panel .ap-hint{color:var(--subtext); font-size:10.5px; padding:4px 1px;}
  /* preview card — mirrors a rostered player's card; staged contract is blue */
  .add-panel .ap-card-prev{margin-top:9px; padding:8px 9px; border:1px dashed var(--accent);
    border-radius:7px; background:rgba(94,168,237,0.06);}
  .add-panel .apc-head{display:flex; align-items:center; gap:8px;
    font:12px/1.3 'Segoe UI',Arial,sans-serif;}
  .add-panel .apc-head .apc-name{flex:1; font-weight:700; color:var(--text);}
  .add-panel .apc-head .apc-nameinp{flex:1; min-width:0; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:4px 7px; font:inherit;
    font-size:12px; font-weight:600;}
  .add-panel .apc-head .apc-nameinp:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  .add-panel .apc-head .apc-nameinp::placeholder{color:var(--subtext); font-weight:400;}
  .add-panel .apc-head .apc-total{color:var(--chart-name-col); font-weight:600;
    font-family:Consolas,Menlo,monospace; font-size:11px;}
  .add-panel .apc-yearrow{margin:7px 0 2px;}
  .add-panel .apc-yearrow select{width:100%; font-size:12px; padding:5px 8px;}
  .add-panel .ap-card-prev .rc-year{font:11px/1.6 Consolas,Menlo,monospace;}
  .add-panel .apc-cbody{margin-top:5px;}
  .add-panel .apc-note{color:var(--orange); font-size:10px; margin-top:4px;}

  /* Inline extension salary entry (rendered inside a player card) */
  .inline-form{margin-top:9px; padding-top:9px; border-top:1px solid var(--line);}
  .inline-form .if-title{font-size:11px; font-weight:700; color:var(--text); margin-bottom:6px;}
  .inline-form .if-capnote{font-size:10px; color:var(--subtext); margin:-2px 0 7px; font-style:italic;}
  .inline-form .if-row{display:flex; align-items:center; gap:6px; margin:5px 0; font-size:11px;}
  .inline-form .if-row .ifr-yr{width:54px; font-weight:600; color:var(--text); font-family:Consolas,Menlo,monospace;}
  .inline-form .if-row input[type=number]{width:60px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:4px 6px; font:inherit;}
  .inline-form .ifr-calc{color:var(--subtext); font-size:10px; font-family:Consolas,Menlo,monospace;}
  .inline-form .if-terms{display:flex; flex-direction:column; gap:8px; margin:4px 0 8px;}
  .inline-form .if-term{display:flex; flex-direction:column; gap:4px; font-size:11px; color:var(--text);}
  .inline-form .if-term .if-pctval{color:var(--accent);}
  .inline-form .if-term input[type=number]{width:80px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:4px 6px; font:inherit;}
  .inline-form .if-term input[type=range]{width:100%;}
  .inline-form .if-prehdr{font-size:10px; color:var(--subtext); font-style:italic; margin:2px 0 4px;}
  .inline-form .if-prerow{display:flex; align-items:center; gap:8px; margin:4px 0; font-size:11px;}
  .inline-form .if-prerow .ifr-yr{width:54px; font-weight:600; color:var(--text); font-family:Consolas,Menlo,monospace;}
  .inline-form .if-prerow .ifp-amt{color:var(--text); font-weight:600; font-family:Consolas,Menlo,monospace; min-width:64px;}
  .inline-form .if-prerow .ifr-calc{flex:1 1 auto;}
  /* Small clickable OPT box on the final preview row — looks like a committed
     option badge but framed in a little box; dim outline until toggled on. */
  .inline-form .ifp-opt{flex:0 0 auto; font:inherit; font-size:9px; font-weight:700; text-transform:uppercase;
    color:var(--blue); background:transparent; border:1px solid rgba(106,176,245,0.55);
    border-radius:4px; padding:1px 5px; cursor:pointer; line-height:1.5;}
  .inline-form .ifp-opt:hover{background:rgba(106,176,245,0.15);}
  .inline-form .ifp-opt.on{color:#fff; background:var(--blue); border-color:var(--blue);}
  .inline-form .ifp-opt.ifp-opt-empty{visibility:hidden; cursor:default;}
  .inline-form .if-muted{font-size:10px; color:var(--subtext);}
  /* Shared contract terms: control row (years · total · change%) */
  .inline-form .mc-row{display:flex; align-items:flex-end; gap:8px; margin:4px 0 8px;}
  .inline-form .mc-field{display:flex; flex-direction:column; gap:3px; font-size:10px; color:var(--subtext);}
  .inline-form .mc-field input[type=number]{background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:4px 6px; font:inherit; font-size:11px; height:25px; box-sizing:border-box;}
  .inline-form .mc-field .mc-total{width:64px;}
  .inline-form .mc-field .mc-years{width:46px;}
  .inline-form .mc-pctwrap{position:relative; display:inline-flex; align-items:center;}
  .inline-form .mc-pctwrap .mc-pct{width:56px; padding-right:16px;}
  .inline-form .mc-pctwrap .mc-pctsign{position:absolute; right:6px; font-size:11px; color:var(--subtext); pointer-events:none;}
  .inline-form .mc-pctwrap.muted .mc-pct{opacity:0.4;}
  /* Per-year override % field on each preview row (extension form only). Same
     width as the overall Change % box so decimal values aren't clipped. Dim
     ("muted") while it's just mirroring the overall Change % — full-strength
     once the user has typed a custom value for that specific year. */
  .inline-form .if-prerow .ifr-pctbase{width:56px; text-align:center; font-size:9.5px;
    color:var(--subtext); font-style:italic;}
  .inline-form .if-prerow .ifr-pctwrap{position:relative; display:inline-flex; align-items:center; width:56px;}
  .inline-form .if-prerow .ifr-pctinput{width:56px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:3px 16px 3px 6px; font:inherit;
    font-size:10.5px; box-sizing:border-box;}
  .inline-form .if-prerow .ifr-pctinput.muted{opacity:0.4;}
  .inline-form .if-prerow .ifr-pctsign{position:absolute; right:6px; font-size:9.5px; color:var(--subtext); pointer-events:none;}
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
  .ysum-cell .ys-yr{color:var(--chart-name-col); width:52px; font-weight:600;}
  .ysum-cell .ys-status{flex:1; font-family:'Segoe UI',Arial,sans-serif; font-weight:600; font-size:11px;}
  .ysum-cell .ys-count{color:var(--subtext); text-align:right; opacity:.85;}
  .ysum-cell .ys-tot{color:var(--text); width:54px; text-align:right;}
  .ys-body{padding:4px 10px 9px; border-top:1px solid var(--line);}
  .ys-growth{display:flex; align-items:center; gap:6px; margin:6px 0 4px;}
  .ys-growth .ysg-lbl{flex:1; color:var(--subtext); font-size:10px;
    text-transform:uppercase; letter-spacing:.3px;}
  .ys-growth .ysg-inp{width:54px; background:var(--card); color:var(--text);
    border:1px solid var(--line); border-radius:5px; padding:3px 6px; font:inherit;
    font-size:11px; text-align:right;}
  .ys-growth .ysg-inp:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  .ys-growth .ysg-pct{color:var(--subtext); font-size:11px;}
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
  <span class="spacer"></span>
  <button class="b-blue" id="saveStateBtn" title="Download the current team state as a .json file you can reload later">Save state</button>
  <button class="b-purple" id="loadStateBtn" title="Load a previously saved team state (.json)">Load state</button>
  <input type="file" id="loadStateInput" accept=".json,application/json" style="display:none">
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
  <div id="chartcol">
    <div id="chartwrap"><canvas id="chart"></canvas></div>
    <div id="yearSliderBar">
      <div id="yearSlider">
        <div class="ysl-rail"></div>
        <div class="ysl-ticks" id="yslTicks"></div>
        <div class="ysl-fill" id="yslFill" title="Drag to shift the selected range"></div>
        <div class="ysl-handle" id="yslHandleLo" tabindex="0" role="slider" aria-label="First season"></div>
        <div class="ysl-handle" id="yslHandleHi" tabindex="0" role="slider" aria-label="Last season"></div>
      </div>
    </div>
  </div>
</div>

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
<script id="playerData" type="application/json">/*__PLAYER_DATA__*/</script>

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
const LAST_YEAR=2040;         // build the table out to here
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
/* Season-label helpers. A season column looks like "2025-26": its starting
   calendar year is 2025. nextSeason("2025-26") → "2026-27". These let the app
   build seasons past the documented range (e.g. extending into 2031-32). */
function seasonStartYear(yc){const m=/^(\d{4})-\d{2}/.exec(yc); return m?parseInt(m[1]):NaN;}
function seasonLabel(startYear){
  const end=(startYear+1)%100;
  return `${startYear}-${end.toString().padStart(2,"0")}`;
}
function nextSeason(yc){const y=seasonStartYear(yc); return isNaN(y)?null:seasonLabel(y+1);}
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
    // Number of documented seasons (before any user-added future years). Seasons
    // appended past this via extensions live in yearCols[origYearCount …].
    this.origYearCount=yearCols.length;
    // Last displayed season index (inclusive). Defaults to the last documented one.
    this.displayEnd=yearCols.length-1;
    this.refreshOptions();
  }
  // Make sure yearCols runs at least as far as `yc`, appending consecutive
  // seasons as needed so contracts can extend past the documented range.
  ensureYearTo(yc){
    if(this.yearCols.includes(yc)) return;
    let last=this.yearCols[this.yearCols.length-1];
    let guard=0;
    while(last!==yc && guard++<60){
      const nxt=nextSeason(last); if(!nxt) break;
      this.yearCols.push(nxt); last=nxt;
      if(nxt===yc) break;
    }
  }
  // Append one new season to the end of the chart and return its label.
  appendYear(){
    const last=this.yearCols[this.yearCols.length-1];
    const nxt=nextSeason(last); if(!nxt) return null;
    this.yearCols.push(nxt);
    return nxt;
  }
  // Drop empty trailing seasons that were appended past the original CSV range
  // and hold no salary for any active player (used to undo a cancelled preview
  // that extended the chart for a future draft pick).
  trimEmptyTrailingYears(){
    while(this.yearCols.length>this.origYearCount &&
          this.yearCols.length>1 &&
          !this.yearHasData(this.yearCols[this.yearCols.length-1])){
      this.yearCols.pop();
    }
    const max=this.yearCols.length-1;
    if(this.displayEnd>max) this.displayEnd=max;
    if(this.displayStart>max) this.displayStart=Math.max(0,max);
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
  displayYears(){
    const end=(this.displayEnd==null?this.yearCols.length-1:this.displayEnd);
    return this.yearCols.slice(this.displayStart, end+1);
  }
  // Does this season have ANY salary on the books for ANY active player,
  // respecting declines and trade cutoffs? Independent of the display window.
  // Also counts the live add-player preview so the chart/slider extend to show
  // a future draft pick's seasons while it's being staged.
  yearHasData(yc){
    if(typeof previewContract!=='undefined' && previewContract &&
       parseSalary(previewContract.dict[yc])!==null) return true;
    for(const p of this.active){
      const name=p["Player"];
      if(this.isYearRemoved(name,yc)) continue;
      const k=this.key(name,yc);
      const ext=this.extensions.get(k)??null;
      if(this.isDeclined(name,yc)){
        // a declined option only counts if re-signed via a non-option extension
        if(ext!==null && !this.extensionOptions.has(k)) return true;
        continue;
      }
      if(parseSalary(p[yc])!==null || ext!==null) return true;
    }
    return false;
  }
  // Index of the last season that has data (so trailing empty seasons are
  // excluded from the slider). Returns -1 if nothing has data.
  lastDataYearIdx(){
    for(let i=this.yearCols.length-1;i>=0;i--) if(this.yearHasData(this.yearCols[i])) return i;
    return -1;
  }
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
  // Maximum number of NEW extension years a player may sign (flat 5-year limit).
  EXT_CAP(name){ return 5; }
  // How many extension years are already committed for this player.
  extYearCount(name){
    return [...this.extensions.keys()].filter(k=>k.startsWith(name+"|")).length;
  }
  // The player's last on-books contract year (CSV or extension), respecting
  // declines and trade cutoffs. Returns null if they have no seasons on the books.
  lastContractYear(name){
    const p=this.active.find(q=>q["Player"]===name); if(!p) return null;
    const filled=this.yearCols.filter(yc=>!this.isYearRemoved(name,yc) &&
      ((parseSalary(p[yc])&&!this.isDeclined(name,yc))||this.extensions.has(this.key(name,yc))));
    return filled.length?filled[filled.length-1]:null;
  }
  // The last season we have ANY record of for this player — on the books or
  // declined — respecting trade cutoffs. Used as a fallback anchor for players
  // with no season currently on the books (e.g. their only season was an
  // option that just got declined).
  lastKnownYear(name){
    const p=this.active.find(q=>q["Player"]===name); if(!p) return null;
    const known=this.yearCols.filter(yc=>!this.isYearRemoved(name,yc) &&
      (parseSalary(p[yc])||this.extensions.has(this.key(name,yc))));
    return known.length?known[known.length-1]:null;
  }
  // The first season a new extension can be signed into. Normally this is the
  // season right after the player's last on-books year. But if the player has
  // NO season on the books at all — their only season was an option they just
  // declined, with no earlier guaranteed seasons — the extension instead takes
  // the PLACE of that lost season rather than starting after it.
  firstExtendableYear(name){
    const onBooks=this.lastContractYear(name);
    if(onBooks) return nextSeason(onBooks);
    return this.lastKnownYear(name);
  }
  // A player can still be extended if they have some season on record, no
  // pending option, and haven't yet used up their extension-year cap. Seasons
  // can run past the documented range (extra seasons are appended on demand).
  canExtend(name){
    if(this.hasPendingOption(name)) return false;
    if(this.lastKnownYear(name)===null) return false;
    return this.extYearCount(name) < this.EXT_CAP(name);
  }
  expiringContracts(){
    const out=[];
    for(const p of this.active){const name=p["Player"];
      if(!this.canExtend(name)) continue;
      const lastYr=this.lastContractYear(name)??this.lastKnownYear(name);
      if(!lastYr) continue;
      const sal=this.isDeclined(name,lastYr)
        ? (this.extensions.get(this.key(name,lastYr))??0)
        : (parseSalary(p[lastYr])??this.extensions.get(this.key(name,lastYr))??0);
      out.push([name,lastYr,sal]);
    }
    out.sort((a,b)=>this.yearCols.indexOf(a[1])-this.yearCols.indexOf(b[1])); return out;
  }
  addExtension(name,year,salary,isOption,label){
    // The season may run past the documented range — append it if needed.
    this.ensureYearTo(year);
    // Keep the visible window covering newly-signed seasons.
    const yi=this.yearCols.indexOf(year);
    if(yi>this.displayEnd) this.displayEnd=yi;
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
      // Append the live add-player preview (if any) as a special top segment.
      // Tagged isPreview=true so the chart paints it blue and ignores clicks.
      if(typeof previewContract!=='undefined' && previewContract){
        const ps=parseSalary(previewContract.dict[yc]);
        const isOpt = !!(previewContract.optYears && previewContract.optYears.has(yc));
        if(ps) entries.push([previewContract.name, ps, isOpt, true]);
      }
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
  // ── Save / load ──────────────────────────────────────────────────────
  // Capture everything needed to rebuild this exact state in a later session.
  // The base roster is rebuilt from the embedded team CSV (referenced by name),
  // so only user moves + acquired players + any future seasons are stored.
  serialize(){
    return {
      _fmt:"nba-salary-state", _v:1,
      teamName:this.teamName,
      yearCols:this.yearCols.slice(),       // includes any seasons added past the docs
      origYearCount:this.origYearCount,
      guaranteedCol:this.guaranteedCol,
      displayStart:this.displayStart,
      displayEnd:this.displayEnd,
      addedPlayers:this.addedPlayers,
      addedFrom:[...this.addedFrom.entries()],
      optionStates:[...this.optionStates.entries()],
      extensions:[...this.extensions.entries()],
      extensionOptions:[...this.extensionOptions],
      extensionLabels:[...this.extensionLabels.entries()],
      traded:[...this.traded.entries()],
      growth:Object.entries(GROWTH),        // global cap-growth overrides
    };
  }
  static restore(obj, csvText){
    const st=new RosterState(csvText, obj.teamName);
    if(Array.isArray(obj.yearCols) && obj.yearCols.length) st.yearCols=obj.yearCols.slice();
    if(typeof obj.origYearCount==="number") st.origYearCount=obj.origYearCount;
    if(obj.guaranteedCol) st.guaranteedCol=obj.guaranteedCol;
    st.addedPlayers=Array.isArray(obj.addedPlayers)?obj.addedPlayers:[];
    st.addedFrom=new Map(obj.addedFrom||[]);
    st.optionStates=new Map(obj.optionStates||[]);
    st.extensions=new Map(obj.extensions||[]);
    st.extensionOptions=new Set(obj.extensionOptions||[]);
    st.extensionLabels=new Map(obj.extensionLabels||[]);
    st.traded=new Map(obj.traded||[]);
    st.refreshOptions();
    // Re-apply stored option decisions on top of any freshly-detected pending ones.
    for(const [k,v] of (obj.optionStates||[])) st.optionStates.set(k,v);
    st.displayStart=(typeof obj.displayStart==="number")?obj.displayStart:0;
    st.displayEnd=(typeof obj.displayEnd==="number")?obj.displayEnd:st.yearCols.length-1;
    return st;
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
    for(const seg of data.get(yc)){
      const name=seg[0], sal=seg[1], isOpt=seg[2], isPrev=seg[3]===true;
      const top=Y((bottom+sal)/1e6), h=Y(bottom/1e6)-top, x=cx-barW/2;
      const isSel = anySel && selSet.has(name);
      const dim = anySel && !isSel && !isPrev;   // never dim the preview
      ctx.save();
      if(dim) ctx.globalAlpha=0.28;
      if(isPrev){
        // Blue translucent fill marks the staged (not-yet-added) contract; an
        // option year additionally gets the diagonal hatch, like a committed one.
        ctx.fillStyle=THEME.accent||"#5EA8ED"; ctx.globalAlpha=(ctx.globalAlpha||1)*0.34;
        ctx.fillRect(x,top,barW,h);
        ctx.globalAlpha=1;
        if(isOpt){ ctx.fillStyle=hatch; ctx.fillRect(x,top,barW,h); }
      }else{
        ctx.fillStyle=THEME.bar; ctx.fillRect(x,top,barW,h);
        if(isOpt){ctx.fillStyle=hatch; ctx.fillRect(x,top,barW,h);}
      }
      // separator line at top of segment
      ctx.fillStyle=THEME.sep; ctx.fillRect(x,top-0.6*s,barW,1.2*s);
      ctx.restore();
      // highlight outline: white for a selected roster player, blue for preview.
      if(isSel || isPrev){
        ctx.save();
        ctx.strokeStyle=isPrev?(THEME.accent||"#5EA8ED"):THEME.name; ctx.lineWidth=2.4*s;
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
    for(const seg of data.get(yc)){
      const name=seg[0], sal=seg[1], isPrev=seg[3]===true;
      const top=Y((bottom+sal)/1e6), h=Y(bottom/1e6)-top;
      const dim = anySel && !selSet.has(name) && !isPrev;
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

/* ════ PNG EXPORT (chart only, honoring the slider's year selection) ════ */
function exportPNG(state){
  refreshTheme();
  const SC=2.5;
  // renderChart draws exactly state.displayYears() (the slider window), so the
  // export automatically reflects the user's From/To selection.
  const years=state.displayYears().filter(y=>state.chartData().has(y));
  const chartW=Math.max(1100,years.length*210)*SC, chartH=1200*SC;

  const c=document.createElement("canvas"); c.width=chartW; c.height=chartH;
  const ctx=c.getContext("2d");
  ctx.fillStyle=THEME.bg; ctx.fillRect(0,0,c.width,c.height);

  renderChart(ctx,state,0,0,chartW,chartH,SC);

  c.toBlob(blob=>{const a=document.createElement("a");
    a.href=URL.createObjectURL(blob); a.download=`${state.teamName}_salaries.png`; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),5000);},"image/png");
}

/* ════ UI WIRING ════ */
const TEAMS=JSON.parse(document.getElementById("teamData").textContent);
// League-wide player info (position/height/weight/birthday), keyed by player
// name (and "TEAM|name" as a fallback). Empty object if no players.csv was
// embedded — the expanded-card info strip is simply skipped in that case.
const PLAYERS=JSON.parse(document.getElementById("playerData").textContent);

// Look up a player's metadata, preferring the team-qualified key so that two
// players who share a name don't collide.
function playerInfo(name){
  if(ST && ST.teamName && PLAYERS[`${ST.teamName}|${name}`]) return PLAYERS[`${ST.teamName}|${name}`];
  return PLAYERS[name] || null;
}

// Current age computed live from a M/D/Y birthday string (e.g. "7/12/1998"),
// returned as a number with one decimal of precision (e.g. 20.9). The fraction
// is the share of the way from the most recent birthday to the next one.
// Returns null if the date is missing or unparseable.
function ageFromBday(bday){
  if(!bday) return null;
  const m=String(bday).split("/");
  if(m.length!==3) return null;
  const mon=parseInt(m[0],10), day=parseInt(m[1],10), yr=parseInt(m[2],10);
  if(isNaN(mon)||isNaN(day)||isNaN(yr)) return null;
  const today=new Date(); today.setHours(0,0,0,0);
  let whole=today.getFullYear()-yr;
  // Subtract a year if this year's birthday hasn't occurred yet.
  const m0=mon-1;
  if(today.getMonth()<m0 || (today.getMonth()===m0 && today.getDate()<day)) whole--;
  // Fractional part: days since the most recent birthday divided by the number
  // of days until the following birthday (handles leap years naturally).
  const lastBday=new Date(yr+whole, m0, day);
  const nextBday=new Date(yr+whole+1, m0, day);
  const frac=(today-lastBday)/(nextBday-lastBday);
  const age=whole+frac;
  return (age>0 && age<100) ? age : null;
}
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
  syncYearSlider();
  activeTooltip = null;
  const r=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
  canvas.width=Math.max(1,Math.round(r.width*dpr));
  canvas.height=Math.max(1,Math.round(r.height*dpr));
  renderChart(cctx,ST,0,0,canvas.width,canvas.height,dpr*(r.width<900?0.85:1));
}
// Keep the slider's range in step with the data after any mutation. Cheap on the
// hot path: only rebuilds the tick DOM when the number of data-bearing seasons
// changed; otherwise it just re-clamps the window and repaints.
let _yslLastCount=-1;
function syncYearSlider(){
  if(typeof yslCount!=="function" || !$("yslTicks")) return;
  const n=yslCount();
  const max=n-1;
  let changed=false;
  if(ST.displayEnd>max){ ST.displayEnd=max; changed=true; }
  if(ST.displayStart>max){ ST.displayStart=Math.max(0,max); changed=true; }
  if(ST.displayEnd<ST.displayStart){ ST.displayEnd=ST.displayStart; changed=true; }
  if(n!==_yslLastCount){ _yslLastCount=n; rebuildYearSlider(); return; }
  if(changed) paintYearSlider();
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
      <span class="ys-count">${r.players} players</span>
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
            `<input type="number" step="0.01" class="ysg-inp" id="growth-${yr}" value="${growthFor(yr).toFixed(2)}">`+
            `<span class="ysg-pct">%</span>`+
          `</div>`;
      }else{
        growthHTML=`<div class="ys-growth"><span class="ysg-lbl">Base year (actual values)</span></div>`;
      }
      let rows=growthHTML+`<table class="yt-table"><tbody>`;
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

      // ── Player info strip ──
      // A single horizontal line of bio facts (position · height · weight · age)
      // pulled from the embedded players.csv. Age is computed live from the
      // stored birthday so it stays current without regenerating the file. The
      // strip is skipped entirely when no player info is available.
      const info=playerInfo(name);
      if(info){
        const bits=[];
        if(info.position) bits.push(`<span class="pi-item"><span class="pi-k">POS</span><span class="pi-v">${info.position}</span></span>`);
        if(info.height)   bits.push(`<span class="pi-item"><span class="pi-k">HT</span><span class="pi-v">${info.height}</span></span>`);
        if(info.weight)   bits.push(`<span class="pi-item"><span class="pi-k">WT</span><span class="pi-v">${info.weight} lb</span></span>`);
        const age=ageFromBday(info.bday);
        if(age!=null)     bits.push(`<span class="pi-item"><span class="pi-k">AGE</span><span class="pi-v">${age.toFixed(1)}</span></span>`);
        if(bits.length){
          const strip=document.createElement("div");
          strip.className="rc-pinfo";
          strip.innerHTML=bits.join('<span class="pi-sep">·</span>');
          body.appendChild(strip);
        }
      }

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
      // A player may hold at most one extension. Once they have one, no further
      // extension can be added (the years it created are edited via remove-mode).
      const canExt=!hasExtNow && ST.expiringContracts().some(([n])=>n===name);
      const extFormOpen = inlineForm && inlineForm.name===name && inlineForm.mode==="extend";
      if(inRemove){
        /* remove-mode: no extension controls */
      }else if(extFormOpen){
        body.appendChild(buildExtendForm(name));
      }else if(canExt){
        const ay=document.createElement("div"); ay.className="rc-addyear";
        const nextYr=extNextYear(name);
        ay.innerHTML=`<span class="ay-plus">+</span><span>Add extension (${nextYr})</span>`;
        ay.onclick=()=>{ inlineForm={name,mode:"extend"}; extState=null; previewContract=null; rebuildSidebar(); };
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
    else rebuildLeagueControls();
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
    // ── Top row: source mode (From League / From Draft) only ──
    `<div class="ap-mode">`+
      `<button id="apModeLeague" class="${leagueOn?"on":""}">From League</button>`+
      `<button id="apModeDraft" class="${leagueOn?"":"on"}">From Draft</button>`+
    `</div>`+
    // ── League block: team filter, search, scrollable list ──
    `<div id="apLeague" style="display:${leagueOn?"block":"none"}">`+
      `<div class="ap-filterrow">`+
        `<div class="ap-filtercol-team"><div class="ap-label">Team</div><select id="addPlayerTeam"></select></div>`+
        `<div class="ap-filtercol-search"><div class="ap-label">Search</div>`+
          `<input type="text" id="addPlayerSearchInp" placeholder="Type a name…" autocomplete="off"></div>`+
      `</div>`+
      `<div class="ap-list" id="apList"></div>`+
    `</div>`+
    // ── Draft block: pick grid + name ──
    `<div id="apDraft" style="display:${leagueOn?"none":"block"}">`+
      `<div class="ap-label">Draft year</div>`+
      `<select id="draftYear"></select>`+
      `<div class="ap-label">Pick</div>`+
      `<div class="ap-pickgrid" id="draftPickGrid"></div>`+
    `</div>`+
    `<div class="ap-preview" id="addPlayerPreview"></div>`+
    `<div class="ap-err" id="addPlayerErr"></div>`+
    `<div class="ap-btns">`+
      `<button id="addPlayerCancel">Cancel</button>`+
      `<button class="b-green" id="addPlayerSubmit">Add to roster</button>`+
    `</div>`;
  // mode toggle
  wrap.querySelector("#apModeLeague").onclick=()=>{ if(addPlayerMode!=="league"){addPlayerMode="league"; clearPreview(); rebuildSidebar(); rebuildLeagueControls();} };
  wrap.querySelector("#apModeDraft").onclick=()=>{ if(addPlayerMode!=="draft"){addPlayerMode="draft"; clearPreview(); rebuildSidebar(); rebuildDraftControls();} };
  if(leagueOn){
    // league handlers
    wrap.querySelector("#addPlayerTeam").onchange=e=>{ addPlayerFilterTeam=e.target.value; rebuildCandidateList(); };
    const si=wrap.querySelector("#addPlayerSearchInp");
    si.value=addPlayerSearch;
    si.oninput=()=>{ addPlayerSearch=si.value.trim().toLowerCase(); rebuildCandidateList(); };
  }else{
    // draft handlers
    const ysel=wrap.querySelector("#draftYear");
    populateDraftYears(ysel);
    ysel.onchange=updateDraftPreview;
    buildPickGrid(wrap.querySelector("#draftPickGrid"));
  }
  // shared
  wrap.querySelector("#addPlayerCancel").onclick=closeAddPlayer;
  wrap.querySelector("#addPlayerSubmit").onclick=submitAddPlayer;
  return wrap;
}

/* ── Shared contract-terms model (used by BOTH the manual new-contract form and
   the extension form) ──────────────────────────────────────────────────────
   A contract is defined by: total ($M), a list of consecutive season strings,
   and a SIGNED percent change (−8…+8; the sign is the raise/decline direction).
   splitContract distributes the total across the years; the total itself is
   capped so year 1 never exceeds 35% of its season cap. One implementation. */
function capForYearM(yr){const t=THRESHOLDS[parseInt(yr)]; return (t?t[0]:154.647);}
// Cumulative growth multipliers for each year [1, ...]. Year 0 is always the
// base (multiplier 1, no rate). For year i>0, uses the per-year override in
// `overrides[i]` if present (and not NaN/null), otherwise falls back to the
// overall `pct`. Passing overrides=null/undefined reproduces the old flat-pct
// ramp exactly.
function _extMultipliers(n, pct, overrides){
  const mult=[1];
  for(let i=1;i<n;i++){
    const ov=overrides?overrides[i]:null;
    const r=((ov!=null && !isNaN(ov))?ov:pct)/100;
    mult.push(mult[i-1]*(1+r));
  }
  return mult;
}
// Largest total ($M) that keeps year 1 at or below 35% of its season cap, given
// the chosen years, overall percent, and any per-year overrides. Returns
// Infinity if no years.
function maxTotalForTerms(yrs, pct, overrides){
  if(!yrs||!yrs.length) return Infinity;
  const mult=_extMultipliers(yrs.length, pct, overrides);
  return 0.35*capForYearM(yrs[0])*mult.reduce((a,b)=>a+b,0);
}
function splitContract(total, yrs, pct, overrides){
  if(!yrs||!yrs.length||isNaN(total)||total<0) return null;
  const n=yrs.length;
  const mult=_extMultipliers(n, pct, overrides);
  const denom=mult.reduce((a,b)=>a+b,0);
  const base=(total*1e6)/denom;
  // rates[i] = the effective YoY growth used for year i (0 for year 0).
  const rates=mult.map((m,i)=>i===0?0:(mult[i]/mult[i-1]-1));
  return {rows:yrs.map((yr,i)=>[yr, base*mult[i]]), rates};
}
/* buildTermsBlock — renders the shared control row (Years · Total · Change %) plus
   a per-year preview, wired to a `state` object {total, years, pct, isOpt} and a
   yearsList(state.years)->[seasons] fn. `pct` is signed. The Total is capped: if
   the user enters more than maxTotalForTerms allows (year 1 would exceed 35% of
   cap), the value reverts to that maximum. Calls opts.onChange() after any change.
   If opts.perYearPct is true, `state.yearPcts` (an array, one slot per year — slot
   0 is unused since year 1 has no growth rate) lets each year's raise be edited
   individually instead of following the overall Change % uniformly:
     - Editing a specific year's % overrides just that year; the overall Change %
       field greys out (it's no longer a single value applied to every year).
     - Editing the overall Change % clears all per-year overrides, so every year
       goes back to following it (and the per-year fields grey back out).
   Returns {el, preview()}. */
function buildTermsBlock(state, yearsForCount, opts){
  opts=opts||{};
  const maxYears=opts.maxYears||5;
  const perYearPct=!!opts.perYearPct;
  const el=document.createElement("div");

  const ctl=document.createElement("div"); ctl.className="mc-row";
  ctl.innerHTML=
    `<label class="mc-field"><span>Years</span>`+
      `<input type="number" step="1" min="1" max="${maxYears}" class="mc-years"></label>`+
    `<label class="mc-field"><span>Total ($M)</span>`+
      `<input type="number" step="0.1" min="0" placeholder="0.0" class="mc-total"></label>`+
    `<label class="mc-field"><span>${perYearPct?"Overall change":"Change"}</span>`+
      `<span class="mc-pctwrap"><input type="number" step="0.5" min="-8" max="8" placeholder="0" class="mc-pct"><span class="mc-pctsign">%</span></span></label>`;
  const yearsInp=ctl.querySelector(".mc-years");
  const totalInp=ctl.querySelector(".mc-total");
  const pctInp=ctl.querySelector(".mc-pct");
  const pctWrap=ctl.querySelector(".mc-pctwrap");
  yearsInp.value=state.years;
  if(!isNaN(state.total)) totalInp.value=state.total;
  pctInp.value=isNaN(state.pct)||state.pct===0?"":state.pct;
  el.appendChild(ctl);

  const preHdr=document.createElement("div"); preHdr.className="if-prehdr";
  preHdr.textContent=perYearPct?"Per-year breakdown — click a year's % to override it":"Per-year preview (not editable)";
  el.appendChild(preHdr);
  const preBox=document.createElement("div"); preBox.className="if-prebox";
  el.appendChild(preBox);

  // Keep state.yearPcts sized to the current year count so stale overrides from
  // a previous (longer) year count don't linger.
  function normalizeYearPcts(n){
    if(!perYearPct) return;
    if(!Array.isArray(state.yearPcts)) state.yearPcts=[];
    while(state.yearPcts.length<n) state.yearPcts.push(null);
    state.yearPcts.length=n;
  }
  function currentOverrides(){ return perYearPct?state.yearPcts:null; }

  // Enforce the 35%-of-cap-on-year-1 ceiling by snapping the entered total down.
  // Returns true if it changed the value (so we can flash a note).
  let cappedNote=false;
  function enforceTotalCap(){
    const yrs=yearsForCount(state.years);
    normalizeYearPcts(yrs.length);
    const cap=maxTotalForTerms(yrs, isNaN(state.pct)?0:state.pct, currentOverrides());
    cappedNote=false;
    if(!isNaN(state.total) && state.total>cap+1e-9){
      state.total=Math.floor(cap*100)/100;   // round down to cents so it stays ≤ cap
      totalInp.value=state.total;
      cappedNote=true;
    }
  }
  function preview(){
    preBox.innerHTML="";
    const yrs=yearsForCount(state.years);
    normalizeYearPcts(yrs.length);
    const hasOverride=perYearPct && state.yearPcts.some(v=>v!=null && !isNaN(v));
    if(perYearPct) pctWrap.classList.toggle("muted", hasOverride);
    const res=splitContract(state.total, yrs, isNaN(state.pct)?0:state.pct, currentOverrides());
    if(!res){ preBox.innerHTML='<div class="if-muted">Enter a total to preview.</div>'; return; }
    const optOn = opts.opt && opts.opt.enabled();
    res.rows.forEach(([yr,v],i)=>{
      const isLast=i===res.rows.length-1;
      const r=document.createElement("div"); r.className="if-prerow";
      let pctHtml="";
      if(perYearPct){
        if(i===0){
          pctHtml=`<span class="ifr-pctbase">base</span>`;
        }else{
          const ov=state.yearPcts[i];
          const overridden=ov!=null && !isNaN(ov);
          const shown=overridden?ov:(isNaN(state.pct)?0:state.pct);
          pctHtml=`<span class="ifr-pctwrap"><input type="number" step="0.5" min="-8" max="8" `+
            `class="ifr-pctinput${overridden?"":" muted"}" data-idx="${i}" placeholder="0" `+
            `value="${shown===0?"":shown}"><span class="ifr-pctsign">%</span></span>`;
        }
      }
      r.innerHTML=`<span class="ifr-yr">${yr}</span>`+pctHtml+
        `<span class="ifp-amt">$${(v/1e6).toFixed(2)}M</span>`+
        `<span class="ifr-calc">= ${(v/(capForYearM(yr)*1e6)*100).toFixed(1)}%</span>`;
      // The final season of a 2+ year deal can be flagged an option — shown as a
      // small clickable blue OPT box in the tag slot, matching a committed row.
      const tag=document.createElement("button"); tag.type="button"; tag.className="ifp-opt";
      if(optOn && isLast){
        const paint=()=>{ tag.classList.toggle("on", opts.opt.get()); tag.textContent="opt"; };
        tag.onclick=()=>{ opts.opt.set(!opts.opt.get()); paint(); };
        paint();
      }else{
        tag.classList.add("ifp-opt-empty"); tag.tabIndex=-1; tag.textContent="";
      }
      r.appendChild(tag);
      preBox.appendChild(r);
    });
    if(perYearPct){
      preBox.querySelectorAll(".ifr-pctinput").forEach(inp=>{
        inp.oninput=()=>{
          const idx=parseInt(inp.dataset.idx);
          const raw=inp.value;
          if(raw===""){ state.yearPcts[idx]=null; fire(); return; }
          let v=parseFloat(raw);
          if(isNaN(v)){ return; }
          v=Math.max(-8,Math.min(8,v));
          if(v!==parseFloat(raw)) inp.value=v;
          state.yearPcts[idx]=v;
          fire();
        };
      });
    }
    if(cappedNote){
      const n=document.createElement("div"); n.className="if-muted"; n.style.marginTop="4px";
      n.textContent=`Total capped so year 1 stays at 35% of the cap (max $${state.total.toFixed(2)}M for these terms).`;
      preBox.appendChild(n);
    }
  }
  const fire=()=>{ enforceTotalCap(); preview(); if(opts.onChange) opts.onChange(); };
  yearsInp.oninput=()=>{
    let y=parseInt(yearsInp.value); if(isNaN(y)) return;
    y=Math.max(1,Math.min(maxYears,y)); state.years=y; yearsInp.value=y;
    if(opts.onYears) opts.onYears(); fire(); };
  totalInp.oninput=()=>{ state.total=parseFloat(totalInp.value); preview(); if(opts.onChange) opts.onChange(); };
  // Snap the total only when the user finishes editing it (not on every keystroke,
  // so typing "12" through "1" then "2" isn't fought by the cap mid-entry).
  totalInp.onchange=()=>{ state.total=parseFloat(totalInp.value); fire(); };
  pctInp.oninput=()=>{ let p=parseFloat(pctInp.value); state.pct=isNaN(p)?0:Math.max(-8,Math.min(8,p));
    if(!isNaN(p)&&(p<-8||p>8)) pctInp.value=state.pct;
    // Editing the overall rate re-establishes it as the single source of truth
    // for every year — clear any individual year overrides.
    if(perYearPct && Array.isArray(state.yearPcts)) state.yearPcts.fill(null);
    fire(); };

  preview();
  return {el, preview};
}

/* ── Inline extension entry (rendered inside a player card) ──
   Terms live in the shared `extState` object; the year list is derived from the
   player's first extendable season forward, capped by years and the league
   extension cap. */
let extState=null;            // {total, years, pct, isOpt, yearPcts} or null when closed
// The next season available to extend into = the season right after the player's
// current last contracted year (their expiring year). Uses season-string math so
// it works past the documented range.
function extNextYear(name){
  if(!ST.canExtend(name)) return null;
  return ST.firstExtendableYear(name);
}
// Up to `count` consecutive seasons available to extend into, starting at the
// player's first extendable year, limited by the league extension cap. Uses
// season-string math so it can run past the charted range (addExtension extends
// yearCols on commit).
function extYearList(name, count){
  const first=extNextYear(name); if(!first) return [];
  const room=ST.EXT_CAP(name)-ST.extYearCount(name);
  const n=Math.max(0, Math.min(count, room));
  const out=[]; let y=first;
  for(let i=0;i<n && y;i++){ out.push(y); y=nextSeason(y); }
  return out;
}
function extMaxYears(name){
  if(!extNextYear(name)) return 0;
  return Math.max(0, ST.EXT_CAP(name)-ST.extYearCount(name));
}
function buildExtendForm(name){
  const wrap=document.createElement("div"); wrap.className="inline-form";
  const first=extNextYear(name);
  if(!first){ wrap.innerHTML='<div class="if-err">No season available to extend into.</div>'; return wrap; }

  const maxYears=extMaxYears(name);

  // Seed terms when the form first opens.
  if(!extState){ extState={total:NaN, years:1, pct:0, isOpt:false, yearPcts:[]}; }
  if(!Array.isArray(extState.yearPcts)) extState.yearPcts=[];
  if(extState.years>maxYears) extState.years=Math.max(1,maxYears);

  const title=document.createElement("div"); title.className="if-title";
  title.textContent="Add extension";
  wrap.appendChild(title);

  // Live blue preview on the chart for the staged extension. The preview dict
  // fills only the new extension seasons; the player's existing bars stay as-is.
  // If the staged years run past the charted range, extend the chart now so the
  // preview is visible (trimmed back when the preview shrinks or is cancelled).
  // When the final year is flagged an option, mark it so the chart paints it as
  // an option segment (matching a committed option year).
  function pushExtPreview(){
    previewContract=null;
    ST.trimEmptyTrailingYears();
    const res=splitContract(extState.total, extYearList(name, extState.years), extState.pct, extState.yearPcts);
    if(res && res.rows.length){
      const lastYr=res.rows[res.rows.length-1][0];
      ST.ensureYearTo(lastYr);   // grow yearCols to fit future extension seasons
      const dict={}; for(const [yr,v] of res.rows) dict[yr]="$"+Math.round(v).toLocaleString("en-US");
      const optYears=new Set();
      if(optEnabled() && extState.isOpt) optYears.add(lastYr);
      previewContract = ST.yearCols.some(yc=>parseSalary(dict[yc])) ? {name, dict, optYears} : null;
    }
    ST.displayEnd=ST.lastDataYearIdx();
    if(ST.displayEnd<ST.displayStart) ST.displayStart=0;
    rebuildYearSlider();
    redrawChart();
  }

  // The final year of a 2+ year extension may be flagged an option.
  function optEnabled(){ return extState.years>1; }

  const terms=buildTermsBlock(extState, c=>extYearList(name,c), {
    maxYears: Math.max(1,maxYears),
    onYears: ()=>{ if(!optEnabled()) extState.isOpt=false; },
    onChange: pushExtPreview,
    opt: { enabled:optEnabled, get:()=>extState.isOpt, set:v=>{ extState.isOpt=v; pushExtPreview(); } },
    perYearPct: true,
  });
  wrap.appendChild(terms.el);
  pushExtPreview();

  const err=document.createElement("div"); err.className="if-err"; wrap.appendChild(err);
  const btns=document.createElement("div"); btns.className="if-btns";
  const cancel=document.createElement("button"); cancel.className="rc-btn"; cancel.textContent="Cancel";
  cancel.onclick=()=>{ inlineForm=null; extState=null; previewContract=null;
    ST.trimEmptyTrailingYears(); rebuildYearSlider(); rebuildSidebar(); redrawChart(); };
  const apply=document.createElement("button"); apply.className="rc-btn rc-extend";
  apply.textContent="Add extension";
  apply.onclick=()=>{
    err.textContent="";
    if(isNaN(extState.total)||extState.total<=0){err.textContent="Enter a total salary greater than 0."; return;}
    const res=splitContract(extState.total, extYearList(name, extState.years), extState.pct, extState.yearPcts);
    const rows=res.rows;
    const actualTotal=rows.reduce((s,[,v])=>s+v,0)/1e6;
    const totalExtAtCommit=rows.length;
    for(let i=0;i<rows.length;i++){
      const [yr,v]=rows[i];
      const isFinal=i===rows.length-1;
      const r=res.rates[i]; // actual YoY growth used for this year (0 for year 1)
      const rateLabel=i===0?"base":`${r>=0?"+":""}${(r*100).toFixed(1)}%/yr`;
      const label=`$${(v/1e6).toFixed(2)}M (${actualTotal.toFixed(1)}M total, ${rateLabel})`;
      const asOption=isFinal && totalExtAtCommit>1 && extState.isOpt;
      ST.addExtension(name,yr,v,asOption,label);
    }
    inlineForm=null; extState=null; previewContract=null;
    rebuildYearSlider(); rebuildSidebar(); redrawChart();
  };
  btns.appendChild(cancel); btns.appendChild(apply); wrap.appendChild(btns);
  return wrap;
}

/* options collapse toggle */
$("optHeader").onclick=()=>{optionsCollapsed=!optionsCollapsed; rebuildSidebar();};

/* ── Year-range slider (custom) ──
   The track is divided into one segment per season. The selection spans segments
   [displayStart..displayEnd] inclusive. Two handles drag the edges (snapping to
   segment boundaries); the highlighted middle can be dragged to shift the whole
   window left/right while keeping its width. Also supports keyboard (arrows) and
   clicking a tick to jump an edge. */
const yslEl=$("yearSlider");
// Number of seasons shown on the slider = up to and including the last season
// that has data. Trailing empty seasons are excluded. Always at least 1.
function yslCount(){ return Math.max(1, ST.lastDataYearIdx()+1); }
function yslMax(){ return yslCount()-1; }   // last selectable season index
function yslSegW(){ return yslEl.clientWidth / yslCount(); }
// Pixel position of a segment boundary (0 = left of first season,
// n = right of last season).
function yslBoundaryX(i){ return i * yslSegW(); }
// Nearest boundary index (0..n) for a pixel x within the track.
function yslXToBoundary(x){
  const n=yslCount();
  let b=Math.round(x / yslSegW());
  return Math.max(0, Math.min(n, b));
}
function rebuildYearSlider(){
  const max=yslMax();
  if(ST.displayStart>max) ST.displayStart=0;
  if(ST.displayEnd==null||ST.displayEnd>max) ST.displayEnd=max;
  if(ST.displayEnd<ST.displayStart) ST.displayEnd=ST.displayStart;
  // (Re)build the per-season ticks — only seasons with data are shown.
  const ticks=$("yslTicks"); ticks.innerHTML="";
  const n=yslCount();
  for(let i=0;i<n;i++){
    const yc=ST.yearCols[i];
    const t=document.createElement("div"); t.className="ysl-tick";
    if(i>=ST.displayStart && i<=ST.displayEnd) t.classList.add("in-range");
    t.style.left=(i/n*100)+"%"; t.style.width=(1/n*100)+"%";
    // Compact label: drop the leading "20" so "2027-28" → "27-28".
    t.textContent=yc.replace(/^20/,"");
    t.title=yc;
    t.onclick=()=>{
      // Click a tick to move the nearer edge to it.
      const distLo=Math.abs(i-ST.displayStart), distHi=Math.abs(i-ST.displayEnd);
      if(distLo<=distHi) ST.displayStart=Math.min(i,ST.displayEnd);
      else ST.displayEnd=Math.max(i,ST.displayStart);
      paintYearSlider(); refreshTotals(); redrawChart();
    };
    ticks.appendChild(t);
  }
  paintYearSlider();
}
function paintYearSlider(){
  const n=yslCount();
  const a=ST.displayStart, b=Math.min(ST.displayEnd, yslMax());
  const leftPct=(a/n)*100, rightPct=((b+1)/n)*100;
  const fill=$("yslFill");
  fill.style.left=leftPct+"%";
  fill.style.width=(rightPct-leftPct)+"%";
  $("yslHandleLo").style.left=leftPct+"%";
  $("yslHandleHi").style.left=rightPct+"%";
  // keep the in-range tick styling in sync without a full rebuild
  const tk=$("yslTicks").children;
  for(let i=0;i<tk.length;i++) tk[i].classList.toggle("in-range", i>=a && i<=b);
}
function commitYearWindow(a,b){
  const max=yslMax();
  a=Math.max(0,Math.min(a,max));
  b=Math.max(0,Math.min(b,max));
  if(a>b){const t=a;a=b;b=t;}
  if(a===ST.displayStart && b===ST.displayEnd){ paintYearSlider(); return; }
  ST.displayStart=a; ST.displayEnd=b;
  paintYearSlider(); refreshTotals(); redrawChart();
}

// ── Pointer dragging ──
let yslDrag=null;  // {mode:"lo"|"hi"|"fill", startX, origA, origB, width}
function yslPointerX(e){
  const r=yslEl.getBoundingClientRect();
  return Math.max(0, Math.min(r.width, (e.clientX!=null?e.clientX:e.touches[0].clientX) - r.left));
}
function yslStart(mode,e){
  e.preventDefault();
  yslDrag={mode, startX:yslPointerX(e), origA:ST.displayStart, origB:ST.displayEnd,
           width:ST.displayEnd-ST.displayStart};
  if(mode==="fill") yslEl.classList.add("dragging-fill");
  window.addEventListener("pointermove",yslMove);
  window.addEventListener("pointerup",yslEnd,{once:true});
}
function yslMove(e){
  if(!yslDrag) return;
  const x=yslPointerX(e);
  if(yslDrag.mode==="lo"){
    const bnd=yslXToBoundary(x);                 // boundary 0..n
    commitYearWindow(Math.min(bnd, ST.displayEnd), ST.displayEnd);
  }else if(yslDrag.mode==="hi"){
    const bnd=yslXToBoundary(x)-1;               // right boundary → last included segment
    commitYearWindow(ST.displayStart, Math.max(bnd, ST.displayStart));
  }else{ // fill: shift whole window by whole segments
    const deltaSeg=Math.round((x - yslDrag.startX)/yslSegW());
    const n=yslCount();
    let a=yslDrag.origA+deltaSeg, b=yslDrag.origB+deltaSeg;
    if(a<0){ b-=a; a=0; }
    if(b>n-1){ a-=(b-(n-1)); b=n-1; }
    commitYearWindow(a,b);
  }
}
function yslEnd(){
  yslDrag=null; yslEl.classList.remove("dragging-fill");
  window.removeEventListener("pointermove",yslMove);
}
$("yslHandleLo").addEventListener("pointerdown",e=>yslStart("lo",e));
$("yslHandleHi").addEventListener("pointerdown",e=>yslStart("hi",e));
$("yslFill").addEventListener("pointerdown",e=>yslStart("fill",e));

// ── Keyboard support on handles ──
function yslKey(which,e){
  const d=(e.key==="ArrowLeft"||e.key==="ArrowDown")?-1:
          (e.key==="ArrowRight"||e.key==="ArrowUp")?1:0;
  if(!d) return;
  e.preventDefault();
  if(which==="lo") commitYearWindow(ST.displayStart+d, ST.displayEnd);
  else commitYearWindow(ST.displayStart, ST.displayEnd+d);
}
$("yslHandleLo").addEventListener("keydown",e=>yslKey("lo",e));
$("yslHandleHi").addEventListener("keydown",e=>yslKey("hi",e));

// Keep handle/fill geometry correct when the window is resized.
window.addEventListener("resize",()=>{ if(ST) paintYearSlider(); });

function loadTeam(name, csvText){
  let st;
  try{ st=new RosterState(csvText??TEAMS[name].csv, name); }
  catch(err){ alert("Could not parse CSV:\n"+err.message); return; }
  ST=st; optionsCollapsed=false;
  expandedPlayers.clear(); expandedYears=new Set(); removeMode=new Set(); inlineForm=null; addPlayerOpen=false;
  _yslLastCount=-1;
  rebuildYearSlider(); rebuildSidebar(); redrawChart();
}
function rebuildTeamSelector(selected){
  const sel=$("teamSelect"); sel.innerHTML="";
  for(const name of Object.keys(TEAMS)){
    const o=document.createElement("option"); o.value=name; o.textContent=name; sel.appendChild(o);}
  sel.value=selected;
}
$("teamSelect").onchange=e=>loadTeam(e.target.value);

$("exportBtn").onclick=()=>{if(ST) exportPNG(ST);};

/* ── Save / load current team state ── */
$("saveStateBtn").onclick=()=>{
  if(!ST) return;
  const blob=new Blob([JSON.stringify(ST.serialize(),null,2)],{type:"application/json"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download=`${ST.teamName}_state.json`;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),5000);
};
$("loadStateBtn").onclick=()=>$("loadStateInput").click();
$("loadStateInput").onchange=e=>{
  const file=e.target.files&&e.target.files[0]; if(!file) return;
  const reader=new FileReader();
  reader.onload=()=>{
    let obj;
    try{ obj=JSON.parse(reader.result); }
    catch(err){ alert("That file isn't valid JSON."); return; }
    if(!obj || obj._fmt!=="nba-salary-state"){ alert("That doesn't look like a saved team state."); return; }
    const csv = TEAMS[obj.teamName] ? TEAMS[obj.teamName].csv : null;
    if(!csv){ alert(`The saved team "${obj.teamName}" isn't in this build. Re-generate the app with that team's CSV, then load again.`); return; }
    let st;
    try{ st=RosterState.restore(obj, csv); }
    catch(err){ alert("Could not load that state:\n"+err.message); return; }
    // Restore global cap-growth overrides, then rebuild the threshold table.
    for(const k of Object.keys(GROWTH)) delete GROWTH[k];
    if(Array.isArray(obj.growth)) for(const [y,v] of obj.growth) GROWTH[y]=v;
    recomputeThresholds();
    ST=st; optionsCollapsed=false;
    expandedPlayers.clear(); expandedYears=new Set(); removeMode=new Set(); inlineForm=null; addPlayerOpen=false;
    _yslLastCount=-1;
    rebuildTeamSelector(obj.teamName);
    rebuildYearSlider(); rebuildSidebar(); redrawChart();
  };
  reader.readAsText(file);
  e.target.value="";   // allow re-loading the same file later
};

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
          for (const seg of data.get(yc)) {
              const name = seg[0], sal = seg[1], isPrev = seg[3] === true;
              const top = Y((bottom + sal) / 1e6);
              const base = Y(bottom / 1e6);
              if (my >= top && my <= base) {
                  if (!isPrev) found = { name, salary: sal, year: yc, mx, my, s };
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
      for(const seg of data.get(yc)){
        const name=seg[0], sal=seg[1], isPrev=seg[3]===true;
        const top=Y((bottom+sal)/1e6), base=Y(bottom/1e6);
        if(my>=top && my<=base) return isPrev?null:name;   // preview isn't clickable
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
let addPlayerMode="league";   // "league" (search the league) or "draft" (rookie scale)
// When a league player has no existing salary at the chosen join season, the user
// authors a contract here with one set of terms: a total ($M) spread across a
// chosen number of consecutive years (1–5) with a fixed year-over-year percent
// change, either increasing or decreasing. Year 1 is clamped to 35% of that
// season's cap. Per-year figures are derived (not individually edited).
// addContract: {startYr, total:Number, years:Number, pct:Number(signed), isOpt:Bool}
let addContract=null;
// Consecutive season strings starting at startYr, length = years. Built via
// season-string math so it can run past the charted range (the form extends the
// chart to fit during preview/commit).
function manualYearList(startYr, years){
  if(!startYr) return [];
  const out=[]; let y=startYr;
  for(let i=0;i<years && y;i++){ out.push(y); y=nextSeason(y); }
  return out;
}
// Split addContract.total across its years via the shared splitContract.
function manualPerYear(){
  if(!addContract) return null;
  return splitContract(addContract.total,
    manualYearList(addContract.startYr, addContract.years),
    addContract.pct, addContract.yearPcts);
}

// ── League candidate model ──
// Candidates come from the league-wide players.csv (PLAYERS), filterable by team
// and name. Each candidate carries its bio info plus — when their original team's
// salary CSV lists them — the source contract dict used for carry-over. Players
// already on MY roster are excluded entirely (including my own two-way players
// who are already rostered).
let leagueCandidates=[];      // [{name, team, info, src|null}]
let addPlayerFilterTeam="*";  // "*" = all teams, else a team code
let addPlayerSearch="";       // current search text (lower-cased)
let addPlayerSel=null;        // name of the currently-selected candidate

// ── Live chart preview ──
// The staged contract shown on the chart (blue) before "Add to roster" is
// clicked. {name, dict} or null. It feeds chartData()/yearTotals so thresholds
// and totals reflect it, but it is NOT a roster player — it can't be clicked or
// deselected on the chart, only cleared from the add-player dialog.
let previewContract=null;
function clearPreview(){ if(previewContract){ previewContract=null; redrawChart(); } }

// User-entered bio overrides for the player being added (all optional). Applied
// to the preview strip and saved with the player on submit.
// Draft mode: selected pick (1–30), chosen from a grid of boxes.
let draftPickNum=1;
let draftNameVal="";   // player name (input now lives inside the preview card)

// Index every team's salary CSV once so candidates can be matched to a real
// contract by (team,name) with a name-only fallback.
let _contractIndex=null;
function contractIndex(){
  if(_contractIndex) return _contractIndex;
  _contractIndex={byTeamName:new Map(), byName:new Map()};
  for(const team of Object.keys(TEAMS)){
    let players=[];
    try{ players=teamPlayers(TEAMS[team].csv).players; }catch(e){ continue; }
    for(const p of players){
      const nm=p["Player"];
      _contractIndex.byTeamName.set(team+"|"+nm, p);
      if(!_contractIndex.byName.has(nm)) _contractIndex.byName.set(nm, p);
    }
  }
  return _contractIndex;
}
function contractFor(team, name){
  const idx=contractIndex();
  return idx.byTeamName.get(team+"|"+name) || idx.byName.get(name) || null;
}

// Build the full candidate list from players.csv, excluding my current roster.
function buildLeagueCandidates(){
  const onRoster=new Set(ST.active.map(p=>p["Player"]));
  const seen=new Set();
  const out=[];
  for(const [key,info] of Object.entries(PLAYERS)){
    if(key.includes("|")) continue;          // skip the team-qualified duplicate keys
    const name=key;
    if(onRoster.has(name)) continue;         // already on my roster
    if(seen.has(name)) continue; seen.add(name);
    out.push({name, team:info.team||"", info, src:contractFor(info.team||"", name)});
  }
  out.sort((a,b)=>a.name.localeCompare(b.name));
  return out;
}

function leagueTeamCodes(){
  const s=new Set();
  for(const c of leagueCandidates) if(c.team) s.add(c.team);
  return [...s].sort();
}
function filteredCandidates(){
  return leagueCandidates.filter(c=>{
    if(addPlayerFilterTeam!=="*" && c.team!==addPlayerFilterTeam) return false;
    if(addPlayerSearch && !c.name.toLowerCase().includes(addPlayerSearch)) return false;
    return true;
  });
}
function selectedCandidate(){
  return leagueCandidates.find(c=>c.name===addPlayerSel)||null;
}

function openAddPlayerPanel(){
  if(!ST) return;
  leagueCandidates=buildLeagueCandidates();
  // League mode needs candidates; fall back to draft only if there are none.
  if(!leagueCandidates.length) addPlayerMode="draft";
  addPlayerFilterTeam="*"; addPlayerSearch=""; addPlayerSel=null; addContract=null;
  previewContract=null; draftPickNum=1; draftNameVal="";
  addPlayerOpen=true;
  rebuildSidebar();
  const panel=document.querySelector(".add-panel");
  if(panel && panel.scrollIntoView) panel.scrollIntoView({block:"nearest"});
}
function closeAddPlayer(){
  if(!addPlayerOpen) return;
  addPlayerOpen=false;
  clearPreview();
  // Undo any chart extension left by a previewed-but-not-added future pick.
  if(ST){ ST.trimEmptyTrailingYears(); rebuildYearSlider(); }
  rebuildSidebar();
  redrawChart();
}

// Default join season for a candidate: their first contracted season if they
// have a carry-over contract, else the first charted season.
function defaultJoinIdx(cand){
  if(cand && cand.src){
    for(let i=0;i<ST.yearCols.length;i++) if(parseSalary(cand.src[ST.yearCols[i]])!=null) return i;
  }
  return 0;
}
// (Re)render the team filter, search box, and candidate list.
function rebuildLeagueControls(){
  const tsel=$("addPlayerTeam");
  if(tsel){
    tsel.innerHTML="";
    const all=document.createElement("option"); all.value="*"; all.textContent="All teams"; tsel.appendChild(all);
    for(const t of leagueTeamCodes()){const o=document.createElement("option"); o.value=t; o.textContent=t; tsel.appendChild(o);}
    tsel.value=addPlayerFilterTeam;
  }
  rebuildCandidateList();
  updateAddPlayerPreview();
}
function rebuildCandidateList(){
  const box=$("apList"); if(!box) return;
  box.innerHTML="";
  const list=filteredCandidates();
  if(!list.length){
    const e=document.createElement("div"); e.className="apl-empty"; e.textContent="No players match.";
    box.appendChild(e); return;
  }
  for(const c of list){
    const row=document.createElement("div");
    row.className="apl-row"+(c.name===addPlayerSel?" sel":"");
    const tag=c.team?`<span class="apl-team">${c.team}</span>`:"";
    const pos=c.info&&c.info.position?`<span class="apl-pos">${c.info.position}</span>`:"";
    row.innerHTML=`<span class="apl-name">${c.name}</span>${pos}${tag}`;
    row.onclick=()=>{
      addPlayerSel=c.name; addContract=null;
      rebuildCandidateList();      // repaint selection highlight
      updateAddPlayerPreview();
    };
    box.appendChild(row);
  }
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
// True when the selected player already has salary in the chosen join season or
// any season after it (carry-over path). False → user must author a contract.
function addHasExistingContract(src, startIdx){
  return ST.yearCols.some((yc,idx)=>idx>=startIdx && parseSalary(src[yc])!=null);
}
// Build the staged contract dict for the current league selection at the chosen
// start year. Carry-over when a source contract exists at/after that season,
// otherwise the manually-authored rows. Returns null if nothing usable yet.
function leaguePreviewDict(){
  const cand=selectedCandidate(); if(!cand) return null;
  const ysel=$("addPlayerYear");
  const startIdx=ysel?(parseInt(ysel.value)||0):defaultJoinIdx(cand);
  const src=cand.src;
  if(src && addHasExistingContract(src,startIdx)){
    return buildShiftedContract(src,startIdx).dict;
  }
  // manual: only if terms produce at least one usable season
  if(manualPerYear()){
    return buildManualContract(cand.name, (src&&src["Age"])||"");
  }
  return null;
}
// Apply the staged contract to the live chart preview (blue) and redraw. If the
// staged manual contract runs past the charted range, grow yearCols to fit (and
// trim back when it shrinks), mirroring the draft-pick preview behavior.
function refreshPreviewOnChart(){
  const cand=selectedCandidate();
  previewContract=null;
  ST.trimEmptyTrailingYears();
  const dict=cand?leaguePreviewDict():null;
  if(cand && dict){
    // Ensure every season the staged contract touches exists on the chart.
    let lastYr=null;
    for(const k of Object.keys(dict)){ if(/^\d{4}-\d{2}$/.test(k) && parseSalary(dict[k])!=null){
      if(lastYr===null || seasonStartYear(k)>seasonStartYear(lastYr)) lastYr=k; } }
    if(lastYr) ST.ensureYearTo(lastYr);
    // For a manually-authored deal, flag the final year as an option when chosen
    // so the blue preview segment paints as an option (matching committed rows).
    const optYears=new Set();
    if(addContract && addContract.isOpt && addContract.years>1){
      const yrs=manualYearList(addContract.startYr, addContract.years);
      if(yrs.length) optYears.add(yrs[yrs.length-1]);
    }
    previewContract = ST.yearCols.some(yc=>parseSalary(dict[yc])) ? {name:cand.name, dict, optYears} : null;
  }
  ST.displayEnd=ST.lastDataYearIdx();
  if(ST.displayEnd<ST.displayStart) ST.displayStart=0;
  rebuildYearSlider();
  redrawChart();
}
function updateAddPlayerPreview(){
  const box=$("addPlayerPreview"); if(!box) return;
  const cand=selectedCandidate();
  if(!cand){
    box.innerHTML='<div class="ap-hint">Select a player to preview their contract.</div>';
    addContract=null; clearPreview(); return;
  }
  const src=cand.src;

  // Year <select> (no label). Preserve prior value across rebuilds; default to
  // the player's natural start season.
  const prevYsel=$("addPlayerYear");
  let startIdx = prevYsel ? (parseInt(prevYsel.value)||0) : defaultJoinIdx(cand);
  if(startIdx>=ST.yearCols.length) startIdx=0;

  // Build the preview card shell with name, total, year select, and stat inputs.
  const wrap=document.createElement("div"); wrap.className="ap-card-prev";
  const head=document.createElement("div"); head.className="apc-head";
  head.innerHTML=`<span class="apc-name">${cand.name}</span><span class="apc-total" id="apcTotal"></span>`;
  wrap.appendChild(head);

  // Year selector row
  const yrow=document.createElement("div"); yrow.className="apc-yearrow";
  const ysel=document.createElement("select"); ysel.id="addPlayerYear";
  ST.yearCols.forEach((yc,idx)=>{const o=document.createElement("option"); o.value=idx; o.textContent=yc; ysel.appendChild(o);});
  if(!ST.yearCols.length){const o=document.createElement("option"); o.value="0"; o.textContent="(no seasons)"; ysel.appendChild(o);}
  ysel.value=startIdx;
  ysel.onchange=()=>{ addContract=null; updateAddPlayerPreview(); };
  yrow.appendChild(ysel);
  wrap.appendChild(yrow);

  // Bio strip (read-only) from players.csv — league players already have stats.
  const info=cand.info;
  if(info){
    const bits=[];
    if(info.position) bits.push(`<span class="pi-item"><span class="pi-k">POS</span><span class="pi-v">${info.position}</span></span>`);
    if(info.height)   bits.push(`<span class="pi-item"><span class="pi-k">HT</span><span class="pi-v">${info.height}</span></span>`);
    if(info.weight)   bits.push(`<span class="pi-item"><span class="pi-k">WT</span><span class="pi-v">${info.weight} lb</span></span>`);
    const age=ageFromBday(info.bday);
    if(age!=null)     bits.push(`<span class="pi-item"><span class="pi-k">AGE</span><span class="pi-v">${age.toFixed(1)}</span></span>`);
    if(bits.length){
      const strip=document.createElement("div"); strip.className="rc-pinfo";
      strip.innerHTML=bits.join('<span class="pi-sep">·</span>');
      wrap.appendChild(strip);
    }
  }

  // Contract body host
  const cbody=document.createElement("div"); cbody.className="apc-cbody";
  wrap.appendChild(cbody);

  box.innerHTML=""; box.appendChild(wrap);

  if(src && addHasExistingContract(src,startIdx)){
    // ── Carry-over: keep the player's real figures from the join year onward ──
    addContract=null;
    const {dict,optionYears}=buildShiftedContract(src,startIdx);
    const optSet=new Set(optionYears);
    let guar=0;
    const rowsHTML=ST.yearCols.map(yc=>{
      const s=parseSalary(dict[yc]); if(!s) return null;
      const isOpt=optSet.has(yc);
      if(!isOpt) guar+=s;
      const cap=THRESHOLDS[parseInt(yc)]?THRESHOLDS[parseInt(yc)][0]:null;
      const pct=cap?`${((s/1e6)/cap*100).toFixed(1)}%`:"";
      return `<div class="rc-year"><span class="rcy-yr">${yc}</span>`+
             `<span class="rcy-sal">${fmtM(s)}</span>`+
             `<span class="rcy-pct">${pct}</span>`+
             `<span class="rcy-tag ${isOpt?"t-opt":""}">${isOpt?"opt":""}</span></div>`;
    }).filter(Boolean).join("");
    const dropped=ST.yearCols.filter((yc,idx)=>idx<startIdx && parseSalary(src[yc])!=null).length;
    cbody.innerHTML=(rowsHTML||`<div class="ap-hint">No seasons at this start year.</div>`)+
      (dropped>0?`<div class="apc-note">${dropped} earlier season(s) dropped — joining mid-contract</div>`:"");
    const tot=wrap.querySelector("#apcTotal"); if(tot) tot.textContent=fmtM(guar);
  }else{
    // ── Manual entry: author a contract (e.g. a two-way player) ──
    renderAddContractForm(cbody, startIdx);
    // total updates as values are entered (renderAddContractForm calls back)
  }
  // Push the staged contract to the chart in blue.
  refreshPreviewOnChart();
}
/* Render the inline contract-authoring form using the SAME shared terms block as
   the extension form: one control row (Years · Total · Change %) plus a read-only
   per-year preview. Terms live in the single addContract object. */
function renderAddContractForm(box, startIdx){
  const startYr=ST.yearCols[startIdx];
  if(!startYr){box.textContent=""; addContract=null; return;}
  // Seed (or re-seed) terms when the form first appears or the start season moves.
  if(!addContract || addContract.startYr!==startYr){
    addContract={startYr, total:NaN, years:1, pct:0, isOpt:false, yearPcts:[]};
  }
  if(!Array.isArray(addContract.yearPcts)) addContract.yearPcts=[];
  // Up to a 5-year deal; seasons past the charted range are added on preview.
  const maxYears=5;
  if(addContract.years>maxYears) addContract.years=Math.max(1,maxYears);

  box.innerHTML="";
  const form=document.createElement("div"); form.className="inline-form ap-contract";
  const title=document.createElement("div"); title.className="if-title";
  title.textContent="No contract on file — enter one:";
  form.appendChild(title);

  // Toggling the option flag changes the guaranteed total, so refresh the chart
  // preview and the displayed total when it flips.
  function optEnabled(){ return addContract.years>1; }

  const terms=buildTermsBlock(addContract, y=>manualYearList(startYr,y), {
    maxYears,
    onYears: ()=>{ if(!optEnabled()) addContract.isOpt=false; },
    onChange: refreshManualPreview,
    opt: { enabled:optEnabled, get:()=>addContract.isOpt,
           set:v=>{ addContract.isOpt=v; refreshManualPreview(); } },
    perYearPct: true,
  });
  form.appendChild(terms.el);
  box.appendChild(form);
}
// While authoring a manual contract, keep the preview total and the blue chart
// preview in sync with the entered values.
function refreshManualPreview(){
  const cand=selectedCandidate(); if(!cand) return;
  const tot=$("apcTotal");
  if(tot){
    const res=manualPerYear();
    if(res){
      const dict=buildManualContract(cand.name,"");
      const guar=parseSalary(dict[ST.guaranteedCol])||0;
      tot.textContent=fmtM(guar);
    }else tot.textContent="";
  }
  refreshPreviewOnChart();
}
// Convert staged manual rows into a player dict the roster understands. Years 1..n
// are guaranteed except a flagged final-year option, so Guaranteed = sum of
// non-option salaries (this makes determineOption flag the option year).
function buildManualContract(name, age){
  const dict={"Player":name,"Age":age||""};
  for(const yc of ST.yearCols) dict[yc]="";
  const res=manualPerYear();
  let guaranteed=0;
  if(res){
    const rows=res.rows;
    rows.forEach(([yr,v],i)=>{
      dict[yr]="$"+Math.round(v).toLocaleString("en-US");
      const isLast=i===rows.length-1;
      const asOption=isLast && rows.length>1 && addContract.isOpt;
      if(!asOption) guaranteed+=Math.round(v);
    });
  }
  dict[ST.guaranteedCol]="$"+guaranteed.toLocaleString("en-US");
  return dict;
}
// Handlers are bound inside buildAddPlayerPanel (the panel is rebuilt on each
// rebuildSidebar). submitAddPlayer adds the player and closes the panel.

/* ── Draft pick mode ──
   Pick (1–30) is chosen from a grid of 30 boxes laid out in 3 rows of 10. The
   "draft year" dropdown lists draft years (e.g. 2026, 2027, 2028) — not season
   strings, and never 2025 (that draft has already happened). A draft year Y maps
   to rookie season Y-(Y+1): e.g. the 2026 draft → rookie season 2026-27, which
   is the yearCol whose start year is Y. The rookie-scale contract runs four
   consecutive seasons from there, years 1–2 guaranteed and years 3–4 options. */
// Render the 1–30 pick selector as a grid of clickable boxes (3×10).
function buildPickGrid(host){
  if(!host) return;
  host.innerHTML="";
  const max=Math.min(30, ROOKIE_SCALE.length);
  for(let n=1;n<=max;n++){
    const cell=document.createElement("button");
    cell.type="button";
    cell.className="ap-pickcell"+(n===draftPickNum?" on":"");
    cell.textContent=n;
    cell.onclick=()=>{ draftPickNum=n; buildPickGrid(host); updateDraftPreview(); };
    host.appendChild(cell);
  }
}
// Draft years available: the current calendar year through 7 years out (e.g.
// 2026–2033 as of 2026). A draft year Y's rookie season is Y-(Y+1) (e.g. 2030 →
// "2030-31"). Returns [{year:2030, season:"2030-31"}]. The season need not exist
// in yearCols yet — buildRookieContract extends the chart to fit it.
function DRAFT_CURRENT_YEAR(){ return new Date().getFullYear(); }
function draftYearOptions(){
  const cur=DRAFT_CURRENT_YEAR();
  const out=[];
  for(let y=cur; y<=cur+7; y++){
    out.push({year:y, season:seasonLabel(y)});
  }
  return out;
}
// Populate the (static) draft-year select with draft years (2026, 2027, …).
// Option value is the rookie-season label (e.g. "2030-31").
function populateDraftYears(ysel){
  if(!ysel) return;
  const prev=ysel.value;
  ysel.innerHTML="";
  const dopts=draftYearOptions();
  for(const o of dopts){const op=document.createElement("option"); op.value=o.season; op.textContent=o.year; ysel.appendChild(op);}
  if(!dopts.length){const op=document.createElement("option"); op.value=""; op.textContent="(no draft years)"; ysel.appendChild(op);}
  if(prev!=null && prev!=="") ysel.value=prev;
  else ysel.value=dopts.length?dopts[0].season:"";
}
function rebuildDraftControls(){
  const ysel=$("draftYear");
  if(ysel && !ysel.options.length) populateDraftYears(ysel);
  updateDraftPreview();
}
/* Build a rookie contract dict ({Player, Age, <year>…, Guaranteed}) for a pick
   entering at rookie season `startSeason` (e.g. "2030-31"). Years 1–2 are
   guaranteed; years 3–4 are options, so Guaranteed is the sum of the first two
   seasons — which makes RosterState.determineOption flag years 3 & 4 as options.
   The chart's yearCols are extended as needed so all four seasons are kept (a
   future pick is never cut off). Returns null on bad input. */
function buildRookieContract(name, pick, startSeason){
  const enterYear=seasonStartYear(startSeason);   // e.g. 2030
  if(isNaN(enterYear)) return null;
  const sals=rookieSalaries(pick, enterYear);     // [Y1,Y2,Y3opt,Y4opt]
  if(!sals) return null;
  // Compute the four consecutive season labels and make sure the chart spans them.
  const seasons=[startSeason];
  for(let k=1;k<4;k++) seasons.push(seasonLabel(enterYear+k));
  ST.ensureYearTo(seasons[3]);                    // extend yearCols to the last rookie year
  const dict={"Player":name||("Pick #"+pick),"Age":""};
  for(const yc of ST.yearCols) dict[yc]="";
  let guaranteed=0;
  for(let k=0;k<4;k++){
    const yc=seasons[k];
    dict[yc]="$"+Math.round(sals[k]).toLocaleString("en-US");
    if(k<2) guaranteed+=Math.round(sals[k]);      // first two years guaranteed
  }
  dict[ST.guaranteedCol]="$"+guaranteed.toLocaleString("en-US");
  return dict;
}
function updateDraftPreview(){
  const box=$("addPlayerPreview"); if(!box) return;
  const pick=draftPickNum;

  // Build the preview card. The name input lives INSIDE the dashed preview box,
  // in the head alongside the running total. (Year + pick controls are above,
  // outside the card.)
  const wrap=document.createElement("div"); wrap.className="ap-card-prev";
  const head=document.createElement("div"); head.className="apc-head";
  const nameInp=document.createElement("input");
  nameInp.type="text"; nameInp.id="draftName"; nameInp.className="apc-nameinp";
  nameInp.placeholder="Player name"; nameInp.autocomplete="off"; nameInp.value=draftNameVal;
  const total=document.createElement("span"); total.className="apc-total"; total.id="apcTotal";
  head.appendChild(nameInp); head.appendChild(total);
  wrap.appendChild(head);
  // Typing the name updates the chart label/total without rebuilding the card
  // (which would steal focus mid-type).
  nameInp.oninput=()=>{ draftNameVal=nameInp.value; refreshDraftContract(); };

  // Contract body
  const cbody=document.createElement("div"); cbody.className="apc-cbody"; cbody.id="apcCbody";
  wrap.appendChild(cbody);
  box.innerHTML=""; box.appendChild(wrap);

  refreshDraftContract();
}
// Recompute the rookie contract for the current pick/year/name and update the
// preview body, total, and blue chart preview — WITHOUT rebuilding the inputs.
function refreshDraftContract(){
  const cbody=$("apcCbody"); if(!cbody) return;
  const pick=draftPickNum;
  const name=draftNameVal.trim();
  if(isNaN(pick)||pick<1||pick>ROOKIE_SCALE.length){
    cbody.innerHTML=`<div class="apc-note">Enter a pick from 1 to ${ROOKIE_SCALE.length}.</div>`;
    const t=$("apcTotal"); if(t) t.textContent="";
    previewContract=null; redrawChart(); return;
  }
  const ysel=$("draftYear");
  const startSeason=ysel?ysel.value:null;
  // Clear the prior preview and trim any years it left behind, so switching to a
  // nearer draft year shrinks the window back down.
  previewContract=null;
  ST.trimEmptyTrailingYears();
  const dict=buildRookieContract(name,pick,startSeason);   // extends yearCols if needed
  if(!dict){cbody.textContent=""; previewContract=null; redrawChart(); return;}
  const guar=parseSalary(dict[ST.guaranteedCol]);
  const rowsHTML=ST.yearCols.map(yc=>{
    const s=parseSalary(dict[yc]); if(!s) return null;
    let run=0,opt=false;
    for(const y of ST.yearCols){const v=parseSalary(dict[y]); if(v==null)continue; run+=v; if(y===yc){opt=run>guar+1; break;}}
    const cap=THRESHOLDS[parseInt(yc)]?THRESHOLDS[parseInt(yc)][0]:null;
    const pct=cap?`${((s/1e6)/cap*100).toFixed(1)}%`:"";
    return `<div class="rc-year"><span class="rcy-yr">${yc}</span>`+
           `<span class="rcy-sal">${fmtM(s)}</span>`+
           `<span class="rcy-pct">${pct}</span>`+
           `<span class="rcy-tag ${opt?"t-opt":""}">${opt?"opt":""}</span></div>`;
  }).filter(Boolean).join("");
  cbody.innerHTML=rowsHTML;
  const tot=$("apcTotal"); if(tot) tot.textContent=fmtM(guar);

  // Set the live chart preview (blue) FIRST so yearHasData sees it, then widen
  // the display window to cover the (possibly future) seasons and rebuild slider.
  previewContract = ST.yearCols.some(yc=>parseSalary(dict[yc])) ? {name:name||("Pick #"+pick), dict} : null;
  ST.displayEnd=ST.lastDataYearIdx();
  if(ST.displayEnd<ST.displayStart) ST.displayStart=0;
  rebuildYearSlider();
  redrawChart();
}

function submitAddPlayer(){
  const err=$("addPlayerErr"); err.textContent="";
  if(addPlayerMode==="draft"){
    const name=draftNameVal.trim();
    if(!name){err.textContent="Enter the player's name."; return;}
    if(ST.active.some(p=>p["Player"]===name)){err.textContent="A player with that name is already on the roster."; return;}
    const pick=draftPickNum;
    if(isNaN(pick)||pick<1||pick>ROOKIE_SCALE.length){err.textContent="Enter a pick from 1 to "+ROOKIE_SCALE.length+"."; return;}
    const startSeason=$("draftYear").value;
    const dict=buildRookieContract(name,pick,startSeason);   // extends yearCols if needed
    if(!dict || !ST.yearCols.some(yc=>parseSalary(dict[yc]))){
      err.textContent="Couldn't build that rookie contract. Check the pick and draft year."; return;
    }
    ST.addPlayer(dict, "Draft");
    // Keep any newly-added future seasons visible.
    ST.displayEnd=ST.lastDataYearIdx();
    addPlayerOpen=false; previewContract=null; rebuildSidebar(); rebuildYearSlider(); redrawChart();
    return;
  }
  const cand=selectedCandidate();
  if(!cand){err.textContent="Pick a player."; return;}
  const startIdx=parseInt($("addPlayerYear").value)||0;
  const src=cand.src;
  const fromLabel=cand.team||"League";

  if(!src || !addHasExistingContract(src,startIdx)){
    // Manual contract authored via the inline total/years/% controls (no contract
    // on file, or none at/after the chosen season — e.g. a two-way player).
    if(!addContract || isNaN(addContract.total) || addContract.total<=0){
      err.textContent="Enter a total salary greater than 0."; return;
    }
    const dict=buildManualContract(cand.name, (src&&src["Age"])||"");
    if(!ST.yearCols.some(yc=>parseSalary(dict[yc]))){
      err.textContent="That contract leaves no seasons on the chart."; return;
    }
    ST.addPlayer(dict, fromLabel);
    addPlayerOpen=false; addContract=null; previewContract=null; rebuildSidebar(); redrawChart();
    return;
  }

  const {dict}=buildShiftedContract(src,startIdx);
  // Guard: at least one season must land within the chart.
  if(!ST.yearCols.some(yc=>parseSalary(dict[yc]))){
    err.textContent="That start year leaves no seasons on the chart. Pick an earlier season.";
    return;
  }
  ST.addPlayer(dict, fromLabel);
  addPlayerOpen=false; addContract=null; previewContract=null; rebuildSidebar(); redrawChart();
}

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
    players = load_players(csv_folder)
    html = build_html(teams, players)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {out_html}  ({len(teams)} team(s), {len(html) // 1024} KB)")
    print("Open it by double-clicking — no install needed. Re-run after editing CSVs.")


if __name__ == "__main__":
    main()