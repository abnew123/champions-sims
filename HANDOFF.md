# Trick Room Six sims: handoff

This folder is the machinery behind the **Trick Room Six** sheet (Pokémon Champions VGC doubles, Reg M-C), moved out of a Claude Cowork session so it can run on all cores of a Mac. Read this file first.

- **Threads (since 2026-10-05):** the work is split across three Claude sessions. "TR sheet" owns the sheet (start at `trsheet/HANDOFF.md`),
  "Battle sim" owns the full-battle simulator and planner (`native/champ/`, the position value, replay analysis; sections "Full 4v4 battle
  sim" and "Double Protect, real-game value weights" below), "Team search" owns `teamsearch/`. They coordinate by SendMessage.
- **Sheet kit (since 2026-10-05):** sheets are built with `sheetkit/` (shared steps and page template, maintained by "TR sheet"), one
  folder per team in `sheets/<team>/`, one thread per team. A new sheet thread starts at `sheetkit/README.md`.
- **Git (since 2026-10-05):** the folder is a git repo (branch `main`) with a private GitHub remote, `abnew123/champions-sims`; the user
  reviews it before it goes public. Each thread commits its own area with explicit paths (no `git add -A`) and pushes only when the user
  asks. Keep names out of everything tracked: write "the user" or "the player", never a real name, the Mac username, absolute `/Users/`
  paths or an email, and no other people's names either (opponents, Showdown usernames, tournament players). `.gitignore` keeps out
  dependencies, build output, results and other large generated files, local binaries, and data with names (game recordings, replay logs,
  scraped tournament pages). Commits use the no-reply email in the repo's git config. License: MIT (`LICENSE`); Showdown's notice, data
  sources and the trademark line are in `NOTICE.md`.
- Published sheet: https://claude.ai/artifact/Qufendyuq8b42JmB56XSc6 (Version 16 as of 2026-10-04; the sections below record each version). The page source is `trsheet/tr-sheet.html`.
- Do not touch the older sheet "Low-Variance Six" (https://claude.ai/artifact/DEF8ycjXrKGXokgH26he9A).
- The player plays on mobile, prefers low downside variance, and wants accurate, battle-useful content. He has a math and poker/game-theory background, so exact reasoning is welcome. Give short status updates during long runs.

## The team (current, sheet v8)

| Pokémon | Item | Ability | Nature, SP (HP/Atk/Def/SpA/SpD/Spe) | Moves |
|---|---|---|---|---|
| Mega Blastoise | Blastoisinite | Torrent → Mega Launcher | Quiet 32/0/0/32/2/0 | Fake Out, Water Spout, Aura Sphere, Dark Pulse |
| Torkoal | Charcoal | Drought | Quiet 32/0/0/32/2/0 | Eruption, Weather Ball, Earth Power, Protect |
| Indeedee-F | Psychic Seed | Psychic Surge | Relaxed 32/0/32/0/2/0 | Follow Me, Helping Hand, Trick Room, Healing Wish |
| Farigiraf | Sitrus Berry | Armor Tail | Relaxed 30/0/21/0/15/0 | Trick Room, Protect, Psychic, Thunderbolt |
| Kingambit | Chople Berry | Defiant | Brave 32/32/0/0/2/0 (sims used Adamant) | Iron Head, Kowtow Cleave, Low Kick, Sucker Punch |
| Incineroar | White Herb | Intimidate | Brave 32/32/0/0/2/0 | Fake Out, Flare Blitz, Throat Chop, Close Combat |

Incineroar replaced Hatterene in v8 after a sixth-slot study (below). The team file for the sims is `pssim/myteam_c_incin.json`. It keeps Kingambit **Adamant** (70 Speed), as simulated; the sheet recommends Brave (63), which only changes the Kingambit mirror and slightly nudges the Trick Room speed credit. Switch the JSON to Brave for new runs if you like, but then old and new runs aren't directly comparable.

Champions stat formula: stat = floor((base + 20 + SP) × nature), HP = base + 75 + SP. Item Clause applies (one of each item).

## Setup (once)

```bash
./setup.sh            # npm install + engine patch, .venv with numpy/scipy, unpacks ../champions-sims-results.tar.xz
source .venv/bin/activate
```

- Needs Node 18+ and Python 3.
- `pssim/engine_patch/` holds four files that fix Champions data in pokemon-showdown 0.11.11: `mods/champions/{abilities,items,moves}.js` and `data/pokedex.js`. The diff is in `champions-data.diff`. `setup.sh` copies them into `node_modules`. If you ever reinstall node_modules, re-run `setup.sh`.
- The results archive holds the runs the current numbers come from, about 320 MB unpacked. `make_inc_team.py` then rebuilds `results/inc*`, which are symlink folders.

`setup.sh` was tested on Linux. The cloud results were reproduced bit for bit: same engine output per seed, same lead values, same sheet HTML.

## Layout

- **`pssim/`** holds the turn-one lead simulator (Node + Showdown engine) and the solver (Python).
  - `t1sim.js`: builds each turn-one battle (my lead + back row vs one opposing lead pair from an archetype) and runs every cell (my joint action × their joint action) for N RNG samples.
    - Opposing archetypes, lead pairs, lead shares, turn-one click rates and sets come from `opp_model_a.json` and `opp_model_b.json`, which were mined from 5,000 Showdown M-C Bo3 replays.
    - Also uses `../foes.json`.
  - `worker.js`: runs jobs. Usage: `node worker.js <jobs.json> <workerIndex> <nWorkers> <outDir> <seedStart> <nSeeds>`. It skips finished jobs, so runs resume.
  - `run_jobs.sh <jobs.json> <outdir> <samples> [workers]`: launches N workers (default: cores − 1) and waits.
  - `analyze.py`: the win model W2 (after-turn-one features → win chance, fit on 7,781 games) and the solvers.
    - **ladder** = my mix vs the replay click frequencies, with their worst-case targeting inside each click type.
    - **reader** = my mix vs their best response to it (Nash side).
    - `lp_blend` maximizes (1−λ)·ladder + λ·reader.
  - `trlib.py`: loads results and applies the **Trick Room credit**. If Trick Room is up after turn one, it scores for the slower brought-four via tanh((their mean Speed − mine)/15), whoever set it. Speeds come from `tr_speeds*.json`.
  - `tr_final.py <resultsDir> <out.json>`: merges the opposing Indeedee-F item variants (`<dir>_colburberry`, `<dir>_psychicseed`, mixed Rocky Helmet 47 / Colbur 31 / Psychic Seed 20), then solves each cell.
    - It simplifies each plan to a few lines, rounds to 5%, re-scores, and values every lead per archetype and per "tell" (`cond_shares.txt`: e.g. "Raichu in their six").
  - Job makers:
    - `jobs_team.js`: a whole six, all 15 pairs.
    - `jobs_cand.js`: one candidate's five pairs.
    - `jobs_tr.js`: historical, the Hatterene six.
    - `tr_speeds.js <jobs.json> <out.json>`: the Speed file for those jobs.
  - Selection:
    - `tr_select.py`: stage one → contenders for refinement, with the rows to keep.
    - `make_cand_refine.py`: the same for a candidate.
  - Comparison and diagnostics:
    - `stage1_cmp.py`, `cmp_cand.py`: candidate vs team.
    - `halfnoise.py`: split-half noise, about ±0.3–0.4 points per refined lead value.
    - `explain_gap.py`: why a plan's ladder and reader numbers differ.
    - `screen_inc.py`: unrefined leads that might top an archetype.
    - `est_refine.py`: refinement cost estimate.
- **`mxtr/`** holds the one-on-one engine (pure Python) behind the sheet's Coverage and Matchups sections.
  - `matchup.py`: exact damage following Showdown's formula (checked against the Smogon calc). It holds our sets (`MINE`), the sixth-slot candidates (`CANDS`, merged into MINE) and threat sets (`F`).
  - `tr_grid.py`: the matchup grid (stages A–E, Monte Carlo rolls). Env vars: `TR=1/0`, `GRID_MONS`, `GRID_TAG`, `NPROC`, and item overrides `KG_ITEM` `KG_NAT` `FG_ITEM` `TK_ITEM` `HT_ITEM`.
  - `tr_cov.py`: the best-hit table. Env var: `GRID_MONS` for the five attackers.
  - `cmp_cands.py`: team coverage for sixth-slot candidates.
  - Current files for the Incineroar six: `gx_cells_{tr,notr}_inc.json`, `tr_cov_inc.json`. The Hatterene-six versions have no suffix.
- **`trsheet/`** builds the sheet.
  - `add_charts.py`: builds Coverage and Matchups. Env vars: `SIX`, `COV`, `GX_TR`, `GX_NOTR`.
  - `trim_v6.py`: the speed table (the `R` array) and speed notes.
  - `patch_v8.py`: the Incineroar card, subtitle, speed rows and sources. It is idempotent.
  - `verify2.js`: Playwright render check at 1200/390/340 px. It needs `npm i -g playwright` and `npx playwright install chromium`. Run it with `NODE_PATH=$(npm root -g) node verify2.js tr-sheet.html`.
- **Root:**
  - `tr_leads.py <tr_final.json> <page.html> <out.html>`: builds the Leads section.
    - Env vars: `READER_W`, `TEAM_NOTE`.
    - Rule: Farigiraf + Blastoise is the main lead when within 3 points of the top (`FB_WITHIN`).
    - The "If Trick Room counts double" lead appears only vs archetypes that set turn-one Trick Room under 5% of the time.
  - `tr_rules.py` → `tr_rules.json`: the hand-written rule under each lead, keyed `arch|tag|lead[|x2]`. The v8 rewrites are in the `R.update` block at the bottom.
  - `tr_digest.py`: readable plans (from `tr_leads_data.json`) to write rules from. `digest_v8.txt` is the current one.
  - `team-sheet.html.usage.json`: threat usage numbers.

## Settings that matter

| Env var | Meaning |
|---|---|
| `MYTEAM` | our team JSON for the sim (`myteam_c_incin.json` now) |
| `TW_UNDER_TR=zero` | a Tailwind set the same turn as Trick Room scores nothing (always used) |
| `ITEM_OVERRIDE=Indeedee-F=colburberry` | opposing Indeedee-F item variant runs (also `psychicseed`); default is Rocky Helmet |
| `READER_W` | weight on the reader number in the lead score. **0.75 is the current choice** (he asked to weight toward the reader: ladder click rates aren't conditioned on our lead). 0.5 was used through v7 |
| `TRMULT=2` | the "If Trick Room counts double" variant (the fitted TR bonus is about 15 points from an even spot) |
| `TR_SPEEDS` | which Speed file trlib loads (`tr_speeds_inc.json` for the current six) |
| `EXCLUDE_MOVES` | drop my actions containing ": <text>", comma-separated (v8 uses `switch -> Hatterene`, see below) |

Stage one uses 1 sample per cell (`run_jobs.sh ... 1`). Refinement uses 12 (`... 12`) on the rows `tr_select.py` keeps.

## Where things stand (sheet v8.1)

- Leads are scored at `READER_W=0.75`. The main leads are:
  - Incineroar + Farigiraf vs Tailwind, Balance and Rain + Sun.
  - Incineroar + Blastoise vs Indeedee TR and Sand.
  - Farigiraf + Kingambit vs Trick Room teams with a Farigiraf.
  - Farigiraf + Blastoise everywhere else.
- **Shortcut to remove first:** the ten non-Incineroar leads reuse the Hatterene-six runs (`results/v7*`), via `pssim/make_inc_team.py`:
  - Six of those leads had Hatterene in the back. It's replaced by Farigiraf, with Farigiraf's 72 Speed in the Trick Room credit.
  - Turn-one switches into Hatterene are dropped (`EXCLUDE_MOVES`).
  - Values moved 0–1 point. Re-running properly is cheap here (next section). Then rebuild the sheet with `TEAM_NOTE=""`, which drops the sentence about the shortcut.
- Sixth-slot study (vs Hatterene; lead value = archetype-weighted gain in best-lead score):
  - Incineroar: +2.5 at 75% reader (+1.7 at 50%, +3.1 pure reader).
  - Sylveon: +0.4.
  - Armarouge: first pass only, behind in 8 of 10 archetypes.
  - One-on-one coverage gain over the other four attackers, TR up / no TR: Incineroar +2.0/+10.7, Hatterene +0.3/+1.3, Sylveon +1.1/+6.0, Armarouge +0.1/+10.7, Milotic +2.2/+1.2, Archaludon +0.5/+7.8.
  - Losses from dropping Hatterene: the only guaranteed one-hit KOs on Garchomp, Mega Garchomp Z and Dragapult (Dazzling Gleam), a third setter, and Magic Bounce.
- Archetype shares of M-C teams, used for weighting: Tailwind 26.2, Sun 12.0, Indeedee TR 11.9, Rain 10.5, Balance 9.3, Sand 9.0, Snow 7.8, TR without Indeedee 6.7, Rain + sun 3.3, Perish 3.3.

## Recipes

Long runs: Claude Code's shell calls time out at about 10 minutes. Start runs with `nohup ... &`, then poll `ls <outdir> | wc -l`. Workers resume if stopped. On 13 workers expect roughly: a 900-job stage one in about 10–15 min, and a refinement in about 10 min.

Environment variables don't persist between shell calls in Claude Code, so every command below carries its own. Run them from `pssim/` unless noted. `trlib` loads one Speed file (`TR_SPEEDS`), and every result it loads needs an entry there. A KeyError on a lead key means the Speed file is missing that team's jobs.

**1. Proper re-run of the current six** (replaces the v8 shortcut):

```bash
MYTEAM=myteam_c_incin.json node jobs_team.js Indeedee-F,Farigiraf jobs_inc1.json     # 900 jobs: 15 pairs x 10 archetypes x 6 opposing leads
MYTEAM=myteam_c_incin.json node tr_speeds.js jobs_inc1.json tr_speeds_inc2.json
MYTEAM=myteam_c_incin.json TW_UNDER_TR=zero nohup ./run_jobs.sh jobs_inc1.json results/inc1 1 > inc1.log 2>&1 &
# when results/inc1 has 900 files:
TR_SPEEDS=tr_speeds_inc2.json READER_W=0.75 python3 tr_select.py 0.05 5 --write --res results/inc1 --jobs jobs_inc1.json --out jobs_inc2
nohup sh -c 'export MYTEAM=myteam_c_incin.json TW_UNDER_TR=zero; ./run_jobs.sh jobs_inc2.json results/inc2 12 &&
  ITEM_OVERRIDE=Indeedee-F=colburberry ./run_jobs.sh jobs_inc2_items.json results/inc2_colburberry 12 &&
  ITEM_OVERRIDE=Indeedee-F=psychicseed ./run_jobs.sh jobs_inc2_items.json results/inc2_psychicseed 12' > inc2.log 2>&1 &
# when inc2.log says done three times:
TR_SPEEDS=tr_speeds_inc2.json READER_W=0.75 python3 tr_final.py results/inc2 tr_final_inc2_r75.json
TR_SPEEDS=tr_speeds_inc2.json READER_W=0.75 TRMULT=2 python3 tr_final.py results/inc2 tr_final_inc2_r75_x2.json
# from the root folder:
TEAM_NOTE="" READER_W=0.75 python3 tr_leads.py pssim/tr_final_inc2_r75.json trsheet/tr-sheet.html trsheet/tr-sheet.html
python3 tr_digest.py > digest_new.txt      # compare with digest_v8.txt; rewrite the rules whose plans changed in tr_rules.py, then:
python3 tr_rules.py && TEAM_NOTE="" READER_W=0.75 python3 tr_leads.py pssim/tr_final_inc2_r75.json trsheet/tr-sheet.html trsheet/tr-sheet.html
```

Rules must describe the plan in `digest_new.txt` accurately. Name the main line and its rough frequency per opposing lead, and put mechanics in plain words: Armor Tail blocks their priority; their Psychic Terrain blocks our Fake Out on grounded targets. A missing rule shows as "Draft:" on the page. `screen_inc.py` shows whether an unrefined lead could top an archetype. It is written for the v8 folders; point it at `results/inc1` and the new `tr_final` file.

**2. Test another sixth against the current six** (after recipe 1):

1. Add its set to `CANDS` in `mxtr/matchup.py`.
2. Write `pssim/myteam_c_<tag>.json` (the six with it in).
3. Run these commands:

```bash
MYTEAM=myteam_c_<tag>.json node jobs_cand.js <Name> <isSetter 0/1> jobs_c_<tag>.json
MYTEAM=myteam_c_<tag>.json node tr_speeds.js jobs_c_<tag>.json tr_speeds_c_<tag>.json
python3 -c "import json; a=json.load(open('tr_speeds_inc2.json')); a.update(json.load(open('tr_speeds_c_<tag>.json'))); json.dump(a, open('tr_speeds_cmp.json','w'))"
MYTEAM=myteam_c_<tag>.json TW_UNDER_TR=zero ./run_jobs.sh jobs_c_<tag>.json results/c_<tag> 1
TR_SPEEDS=tr_speeds_cmp.json READER_W=0.75 BASE1=results/inc1 DROP=<member it replaces> python3 stage1_cmp.py <tag>
TR_SPEEDS=tr_speeds_cmp.json READER_W=0.75 BASE1=results/inc1 python3 make_cand_refine.py <tag> 0.03    # -> jobs_r_<tag>.json (+ _items)
# refine: run_jobs.sh jobs_r_<tag>.json results/r_<tag> 12, plus the two ITEM_OVERRIDE runs of jobs_r_<tag>_items.json (MYTEAM=myteam_c_<tag>.json)
TR_SPEEDS=tr_speeds_cmp.json READER_W=0.75 python3 tr_final.py results/r_<tag> tr_final_c_<tag>_r75.json   # and TRMULT=2 -> ..._r75_x2.json
RW=_r75 BASE_FINAL=tr_final_inc2 DROP=<member> python3 cmp_cand.py <tag>
cd ../mxtr && GRID_MONS=<Name> GRID_TAG=_cand_<Name> TR=1 python3 tr_grid.py && GRID_MONS=<Name> GRID_TAG=_cand_<Name> TR=0 python3 tr_grid.py
python3 cmp_cands.py      # edit the FOUR / CANDS lists inside for the current team
```

`jobs_cand.js` assumes the setters are Indeedee-F and Farigiraf, plus the candidate if you pass 1.

**3. Rebuild Coverage/Matchups** after changing a set:

- Re-run `tr_grid.py` for the affected mon (TR=1 and 0).
- Re-run `tr_cov.py` with `GRID_MONS` = the five attackers.
- Merge that mon's cells into `gx_cells_{tr,notr}_inc.json`.
- Then:

```bash
cd trsheet && SIX="Blastoise,Torkoal,Farigiraf,Kingambit,Incineroar" COV=../mxtr/tr_cov_inc.json \
  GX_TR=../mxtr/gx_cells_tr_inc_t22.json GX_NOTR=../mxtr/gx_cells_notr_inc_t22.json python3 add_charts.py tr-sheet.html
```

**4. Publishing.** Artifacts live on claude.ai. If this session has no tool that can update that artifact, bring `trsheet/tr-sheet.html` back to the Cowork conversation and ask Claude there to publish it to the same link. Keep the page self-contained (inline CSS/JS; Google Fonts only), and check phone widths with `verify2.js`.

## Gotchas

- Lead names are ordered: newcomers first, then Indeedee-F, Hatterene, Farigiraf, Torkoal, Kingambit, Blastoise (e.g. `Incineroar+Farigiraf`, `Farigiraf+Blastoise`). Rules, Speed keys and `FB` depend on it; `jobs_team.js` keeps it.
- The back row is a default (fill to both setters, then attackers by archetype preference). The sim doesn't choose it. It matters for turn-one switches and the Trick Room credit.
- First-pass (1-sample) values run about 0.5 higher than refined ones for the leads that get picked (selection bias). Compare refined to refined.
- `tr_final.py` asserts that item-variant files have the same action rows as the base run. Always run variants from the same jobs file.
- Showdown replays don't show EVs. Opposing spreads come from Smogon's August 2026 Reg M-B Bo3 1500 moveset stats (top spreads) and MetaVGC. `curl` to smogon.com was blocked from the cloud session. From a Mac there's no such restriction, but fetch politely.

## v10 (sheet Version 10, 2026-09-30)

- **Full re-run of the Incineroar six** (Recipe 1 done): `results/inc1` (stage one), refined in `results/inc3*` under the new Trick Room weights. The Hatterene-six shortcut is gone.
- **2v2 endgame sim** (`pssim/endgame.js`): my two vs their two, both fresh, Trick Room up for K turns or not. Each turn both sides play the Nash mix of a one-turn matrix game (every joint action in Showdown's engine, scored by HP share + Trick Room turns for the slower side), then play on to the end.
  - Jobs: `MYTEAM=... node eg_jobs.js <out.json> [topPairs=5] [K=3]` = all 15 of my pairs vs each archetype's 5 likeliest back pairs (from replay back-row rates), K=3 and K=0.
  - Run: `./eg_run.sh <jobs> <outdir> <games=6> [workers]` (resumes). The v10 run is `results/eg1` (1,470 jobs, ~25 min on 13 workers); Hatterene pairs in `results/eg_hat` (`myteam_7.json` = the six + Hatterene).
  - `python3 eg_analyze.py results/eg1 --json eg1_summary.json`: Trick Room worth per archetype and back-pair ranking per sheet lead. `eg_hat_cmp.py` compares Hatterene + X vs Incineroar + X.
- **Per-archetype Trick Room weight** replaces the "If Trick Room counts double" variant: `python3 eg_trmult.py eg1_summary.json trmult_eg.json`, then `TRMULT_FILE=trmult_eg.json` for `tr_select.py` / `tr_final.py` (trlib multiplies the TR credit). The overall size stays anchored to the replay fit; the 2v2 only redistributes it (Tailwind/Balance/Sand ~1.4-1.5x, TR teams 0x).
- **Back row on the sheet** = best 2v2 pair from the four not leading, mixing TR up/down by the lead's turn-one TR rate (`BACK_FILE=pssim/eg1_summary.json` for `tr_leads.py`). The turn-one sims still used the default back row.
- Rebuild: `TEAM_NOTE="" READER_W=0.75 BACK_FILE=pssim/eg1_summary.json TRMULT_FILE=pssim/trmult_eg.json python3 tr_leads.py pssim/tr_final_v9.json trsheet/tr-sheet.html trsheet/tr-sheet.html`. Rules for v10 are in the last `R.update` block of `tr_rules.py`. Incineroar's team card has a hand-added sentence on Hatterene (in the HTML only).
- `bring.py` (root) is an earlier heuristic back-row scorer from the one-on-one grid; superseded by the 2v2 but kept as a cross-check. The grid now also has 11 more threats (`mxtr/gx_cells_*_inc_ext.json`).
- Ideas not done: re-run the turn-one sims with the 2v2 back rows; more 2v2 games for close back-pair calls; vary K (Trick Room turns left).

## v11 (sheet Version 11, published 2026-10-02): 2v2 rework

The v10 2v2 numbers (back rows, Trick Room weights, Hatterene comparison) came from an engine with bugs, found since:
Fake Out never offered (activeTurns is 1 on turn 1; now uses activeMoveActions), one planning seed per cell (chance fixed while
planning), Protect clicked under a Choice item, and a hand-set score. The fixed engine is `pssim/endgame2.js`:
- 2 planning seeds per cell (`EG_SEEDS=2`), no Protect while holding a Choice item, Fake Out on first turn out.
- Score fitted on 2v2 outcomes (`eg_fitvalue.py` -> `egvalue2.json`, `EG_VALUE`): HP, Pokemon left, boosts, TR turns x speed,
  matchup-grid coverage/exposure, typing from actual moves, recharge, Protect streak, status, Tailwind, screens, Encore, Choice locks
  (some weights hand-set; see the file's note). Perish Song races are hand-set (`perishAdj`: last to faint wins; speed order, reversed under TR).
- `EG_KMIX=1`: Trick Room-up matchups play their 4 games with 2/3/3/4 turns left. `EG_AUDIT=1`: move audit (`eg_audit.py`).
- Opposing pairs: sampled by how often they're on the field at the start of turn 3 in public replays (`endpair_scan.py` -> `endpairs.json`,
  `eg_jobs_t3.js`), weighted equally.
- Two-turn spot check: `eg_depth2.js` / `eg_d2_run2.sh` (one-turn planning loses ~1-2 win-% points per decision on average).
- Progress page: `python3 status_server.py` (or the "sim-progress" entry in `.claude/launch.json`), http://localhost:8766.

**To resume:** `cd pssim && nohup nice -n 15 ./final_run.sh > final_run.log 2>&1 &` (8 workers, low priority; workers skip finished jobs).
Main run `results/eg_final` was 1,195 / 1,800 when paused; then Hatterene pairs `results/eg_final_hat` (300 jobs).
Then: `eg_audit.py results/eg_final eg_jobs_final.json`; `eg_analyze.py results/eg_final --json eg_final_summary.json`;
`eg_trmult.py`; back rows mixed by the lead plan's P(Trick Room up after turn 1, whoever set it) (not yet wired into tr_leads.py);
Hatterene vs Incineroar on the paired pairs; show the user the changes vs v10 before rebuilding/publishing the sheet.
Lariat vs Throat Chop: turn-one sims show no difference (+0.03); the 2v2 comparison was cancelled as not worth the time.
- **Next after the v11 run (agreed 2026-10-02):** add "Fake Out spent" and "Protected last turn" to the turn-one lead scoring
  (t1sim.js feats / the W2 win model), so leads like Perish's Gengar Protect + Rillaboom Fake Out -> Incineroar pay for the bad turn 2.
  Options: refit W2 on the replays with the two extra features, or score the post-turn-1 position with the fitted 2v2 score.
  Also: Perish rule -> Flare Blitz the Rillaboom (OHKO; stops the Eject Button / Fake Out loop), Close Combat only into an expected switch.

**v11 done.** Final 2v2 run `pssim/results/eg_final` (1,800 jobs) + `eg_final_hat`; summary `eg_final_summary.json`, Trick Room weights
`trmult_final.json`, P(TR up after turn 1) per plan `trup_v11.json` (`tr_up.py`); leads re-solved from both refinement rounds merged
(`results/v11*`) -> `tr_final_v11.json`. Rebuild the sheet from the published page (the page source is `trsheet/tr-sheet.html`):

```bash
SHOW_PLAN=0 TEAM_NOTE="" READER_W=0.75 BACK_FILE=pssim/eg_final_summary.json TRMULT_FILE=pssim/trmult_final.json TRUP_FILE=pssim/trup_v11.json \
  python3 tr_leads.py pssim/tr_final_v11.json trsheet/tr-sheet.html trsheet/tr-sheet.html
```

`SHOW_PLAN=0` drops the plan paragraph; cards keep mechanics notes (`MECH` in tr_rules.py, else extracted) and judgment notes.
Decisions: Incineroar is the sixth (Hatterene dropped for good); Throat Chop stays; no "bring both setters" advice.
Progress page now on port 8766 (8765 is the user's DeskBooks backend).

## Native engine, stage 2: Rust turn engine (2026-10-02)
`native/champ` (Rust; build: `CARGO_BUILD_JOBS=2 nice -n 10 ~/.cargo/bin/cargo build --release`). A port of Showdown's doubles turn
(event system with identical handler ordering and tie shuffles, action queue, runMove/useMove/hit steps, Champions getDamage/modifyDamage,
residuals) with Rust ports of the in-scope move/ability/item/condition handlers (`src/handlers/*.rs`, each following the JS in `native/handlers_all.js`).
- Data: `node ../native/export_engine.js ../native/champions_data.json ../native/engine_data.json` (from pssim/); handler sources: `dump_all_handlers.js`.
- Test cases: `TEAM=2 node ../native/gen_turn_cases.js <n> <out.jsonl> <seed>` (random positions from real sets; Showdown plays one turn in
  RNG modes lo/hi/mid plus real Gen5 RNG with the exported seed). Check: `./target/release/champ turn ../engine_data.json <cases> lo,hi,mid,real`
  (CASE=<id> LOG=1 for one case with logs). Speed: `champ bench ../engine_data.json <cases> <reps>`.
- Status: exact match with Showdown (every checked field, all four RNG modes incl. real-RNG draw order) on 3,300 2v2 positions (TEAM=2)
  and 3,600 positions with full four-Pokemon teams (TEAM=4: voluntary switches, U-turn/Parting Shot/Eject Button switches, Roar-style
  drag-outs, faint replacements, hazards, switch-in abilities/items). Harness: `play()` in turntest.rs replays the switch choices Showdown got.
  Not ported (flagged unsupported, ~0.4% of random turns): slot conditions (Revival Blessing, Healing Wish), Baton Pass, Ally Switch,
  Beat Up, Magician, Wandering Spirit.
- API: `run_turn([[PChoice; 2]; 2])` (PChoice::Move(request index, target loc, mega) / Switch(team position) / Pass); if
  `request_switch` is set afterwards, `switch_request()` says which slots must switch and `choose_switches(..)` continues the turn.
- Speed: ~150 us (2v2) / ~260 us (4v4) per clone + turn vs ~1.4 ms for Showdown's fromJSON + turn. Not yet optimized
  (Fx hashing and a no-handler fast path are in; remaining cost is spread over handler discovery, allocation and cloning).
- Planner (stage 3): `src/plan.rs` ports pssim/endgame2.js (options, value features incl. the mxtr grid, regret-matching Nash, sampling,
  autopilot). JS still builds each game's start position and seeds (`native/eg_starts.js`), Rust plays the games; results match the JS
  planner game for game (same winners and turn counts). Run with `pssim/eg_run_native.sh <jobs.json> <outdir> <games> [threads]`
  (same env vars as eg_run2.sh; writes <outdir>/<job>.json in the JS workers' format, so eg_auto_analyze.py and the progress page work).
  About 8-10x faster per core than the JS workers.
- Autopilot run (eg_auto): the 3:30 am run stopped at 389/600 (workers 1,3,5,7 crashed on a null-score log line, fixed). Resumed 2:17 pm
  with 8 workers; eg_worker_v2.js now splits only the unfinished jobs round-robin, so a resumed run keeps every worker busy.

## Spread study, game reviews, Indeedee-slot study (2026-10-02/03)
- **Spreads** (paired: same jobs and seeds as the current team): `pssim/sp_run.sh`, `blast_run.sh`; 2v2 compare `sp_compare.py <tag>`
  (results/sp_base vs results/sp_<tag>), turn-one compare `sp_lead_cmp.py <MON> <name>:<refined dir>:<speeds> ...` (leads with MON from
  the variant's refinement, the rest from results/v11). Verdicts: Torkoal Quiet 12/0/0/32/22/0 (+0.8/+1.0 in 2v2) adopted; Kingambit Brave
  (user already runs it; sim file still Adamant); Incineroar Adamant 81 neutral (63.18 both); Farigiraf 26/32/8 worse (-1.6/-2.0);
  Blastoise Modest 98 neutral, Modest 130 worse (-10 TR up, -0.8 lead score).
- **Recordings**: `recordings/compress.sh` (HEVC 1600 px 10 fps, ~50x smaller, parse-lossless), `process.sh <mov> <batch>` (compress, frames,
  Vision OCR, `parse.py` timeline). Batches in recordings/batch1, batch2.
- **Decision review**: `native/spot_starts.js` builds positions from `recordings/spots.json` (sets: MYTEAM + Smogon M-C sets with revealed
  info; HP, boosts, Mega, fainted, field; `actual` and optional `their_actual`). `champ spot` (built to native/champ/target_spot; uses
  native/engine_data_spot.json = engine data + EXTRA_MOVES=megahorn) plays every kept cell to the end with the planner (switches allowed on
  the first turn, forced replacements after), 8 games per cell. Output: recordings/review_v2.json, whatif_review.json.
- **Indeedee-slot study** (`pssim/cand_run.sh`, team files myteam_x_<tag>.json keep the key "Indeedee-F" so all job files apply):
  2v2 slot pairs (TR up / down): +Psychic +11.3/+6.8, Own Tempo -6.7/-2.5, Sinistcha -0.5/-4.6, Hatterene +17.8/+0.6, Rillaboom +16.9/+8.8.
  Team summary (`sp_team_cmp.py`, sp_team_cmp_ind.txt): weighted best-lead score / best back pair: now 63.14/68.01, +Psychic 63.14/68.77,
  Own Tempo 63.08/67.71, Sinistcha 63.13/67.42, Hatterene 63.20/68.13, **Rillaboom 64.02/71.49** (leads vs Indeedee TR 69.8 vs 63.2).
  Caveats: the sims can't value Healing Wish; non-slot leads reuse v11 turn-one results (old Indeedee in their back row).

## Full 4v4 battle sim (2026-10-03)
- `native/battle_starts.js <jobs> <out.jsonl> <games> [G0]` (from pssim/): starting positions after team preview. Jobs are either archetype
  mode `{arch, k, lead, back}` (MYTEAM; their four from t1sim.build's replay model) or explicit `{mine: [4 sets], theirs: [4 sets], meta}`.
- `champ battle <engine_data> <starts.jsonl> <outdir> [threads]` (`native/champ/src/battle4.rs`; stable builds `native/champ/bin/champ-battle-v1`,
  `-v2` with source tarballs and sha256): both sides play the 2v2 planner's one-turn matrix game every turn with mid-game switching at one
  layer (each side's own switches vs the opponent staying in); faint replacements by the replacement matrix game. Env: `EG_VALUE`,
  `GRID_DIR`, `BATTLE_ANTICIPATE=1` (v2: second pass adds the opponent's actually-played switches; recommended), `BATTLE_NOSWITCH=1` (control),
  `BATTLE_NS` (planning seeds, default 2), `BATTLE_LOG=1`, `BATTLE_FEATS=1` (per-turn features for refits). v2 plays on past 25 turns
  (to 250) when neither side can deal damage (PP runs out, Struggle). Per-game output: v, turns, Trick Room up by T1-3, switch decisions.
- Value: `pssim/egvalue4.json` refit on 7,200 self-play battles (`battle_train.sh`, `eg_fitvalue.py`; thin features hand-set as in
  egvalue2): Trick Room weight doubled, so the planner now sets Trick Room like the sheet's plans. `egvalue5.json` = second round
  (`battle_night2.sh`). About 6-7 s per game per thread.
- Results (`battle_summary.py <dir>`; the sheet's plans, 32 games per opposing lead): ladder-weighted full-battle win share 60.9% (egvalue2),
  69.0% (egvalue4), 68.2% (egvalue4 + anticipation), 68.2% (egvalue5 + anticipation; egvalue5 converged within ~0.1 of egvalue4). Weak vs Sun (~32-37) and Rain (~42); strong vs Tailwind (93), Snow, Balance, Perish.
  Voluntary switch rate about 13-15% of decisions for each side; switching moves archetype results by 15-25 points (no-switch control);
  opponents Protect 24% of the time once Trick Room has been set vs 11% before.
- `champ-battle-v3`: turn/planning seeds keyed on the line's `seedKey` (battle_starts.js: `a|arch|k` or `x|their four`) instead of the job
  index, so everything facing the same opponent in game g shares seeds (common random numbers). Same combo, different job index -> identical
  games. Under v2, reruns of one combo at another job index differed by up to ~24 points per archetype (planner randomness).
- Full-battle lead picks (`battle_leads2.sh` stage two, `battle_leads3.sh` confirmation on fresh seeds; `battle_leads_rank.py`,
  `battle_leads_confirm.py`): better than the sheet, replicated on two seed sets: Sun Blastoise+Kingambit / Farigiraf+Incineroar (36 -> 55-64),
  Rain Incineroar+Torkoal / Blastoise+Farigiraf (41 -> 51-54), Sand Incineroar+Farigiraf / Blastoise+Kingambit (72 -> 81-87), Trick Room teams
  Incineroar+Farigiraf / Blastoise+Torkoal (57 -> 68-74), Perish Blastoise+Kingambit / Torkoal+Farigiraf (77 -> 90-97). Sheet not updated yet.
- The teamsearch thread (`teamsearch/`) uses champ-battle-v2 + egvalue5 + anticipation (archetype mode, G0 seeds) as its team evaluator.

## Sheet Version 12 (published 2026-10-04): full-battle leads
Sun, Rain, Sand, Trick Room teams and Perish show one card each: the full-battle pick (lead and back row from `battle_leads2/3`),
marked "Full-battle pick", with the turn-one lines from the turn-one solver for that lead and a note with the whole-game numbers. Other tabs
are unchanged from v11. Incineroar + Farigiraf vs Trick Room teams was refined for this (`results/v11b_tr`, merged in `results/v11plus`).
Build (the page's layout is v11's; only the `const L=[...]` data, the card label and one sentence of the leads note were spliced in):
```bash
LEAD_OVERRIDE=pssim/lead_override_v12.json SHOW_PLAN=0 TEAM_NOTE="" READER_W=0.75 BACK_FILE=pssim/eg_final_summary.json TRMULT_FILE=pssim/trmult_final.json \
  TRUP_FILE=pssim/trup_v11.json python3 tr_leads.py pssim/tr_final_v11plus.json trsheet/tr-sheet.html <scratch.html>   # then splice L into the v11 page
```
tr_leads.py now carries the unpublished "Other" tab changes from the v12 draft; running it straight onto the page would also publish those.
Backups: trsheet/tr-sheet.v11.html (published v11), tr_leads_data.v12draft.json. The team card still shows Torkoal 32 HP / 2 SpD (the user
switched to 12 HP / 22 SpD) and the Matchups grid uses the old Torkoal bulk.

## Sheet Versions 13-14 (2026-10-04): strongest four per archetype; bring matrix
- v13: each tab shows the best four from the full-battle decider (`battle_pick_decide.py` -> `battle_picks_final.json`; `build_sheet_v13.py`).
- Bring matrix (AWS, `bringmx_<i>.json` jobs, one per archetype in sheet order): all 90 (lead, back) fours x the archetype's 6 opposing leads
  x 16 games (first game index 600), real sets (`myteam_real.json`: Brave Kingambit, Torkoal 12/0/0/32/22/0), champ-battle-v4 + egvalue5 +
  anticipation; 86,400 games in `results/bringmx_<i>` (+ `bringmx_<i>r`, the same jobs played from the back by `bringmx_helper.py`;
  seeds depend only on opponent and game, so the two halves are the same games). Report: `bringmx_report.py` -> `results/bringmx_report.txt`
  (top fours, where the sheet pick ranks, worth of bringing / leading each Pokemon, species tells).
- Confirmation (`bringmx_confirm.py jobs|decide`): each archetype's top 5 + the sheet pick on 48 fresh games per opposing lead (first game
  index 1000; `results/bringcf_a`, `bringcf_b`); a pick changes only if the fresh leader beats it by >= 1.5 paired SE. Result
  (`results/bringcf_report.txt`, `bringcf_picks.json`): only Indeedee TR changes (Farigiraf+Kingambit / Blastoise+Incineroar, 68% vs 60%,
  +8.2 +- 3.9). Rain's Blastoise+Farigiraf / Torkoal+Incineroar is +6.8 +- 4.5 (1.49 SE; all of it vs non-Pelipper leads) and stays off.
  Ladder-weighted on fresh games: 75.6% (v14) vs 74.7% (v13).
- v14 (`build_sheet_v14.py`): the new Indeedee TR four with turn-one lines refined with the real sets (`v14_itr_run.sh`, `v14_items_run.sh`:
  Indeedee-F item variants, `tr_speeds_v14.json`, merged `tr_final_v14plus.json` = v11plus + 6 new plans), and every tab's whole-game % from
  the fresh games. Only the page's `const L=[...]` is spliced. Backup: `trsheet/tr-sheet.v13.html`.
- v15 (`build_sheet_v15.py`, backup `trsheet/tr-sheet.v14.html`): same picks; the other nine tabs' turn-one lines re-run with the real sets
  and each tab's planned back row (`v15_run.sh`: `jobs_v15.json` -> `results/v15` + Indeedee-F item variants; `v15_merge.py` replaces those
  keys in v14plus -> `results/v15plus*`, `tr_speeds_v15.json`; `tr_final_v15plus.json`). Fixes turn-one lines that switched to a Pokemon
  outside the four (the old default back rows had Indeedee / Torkoal / Kingambit on Rain, Sand, Sun and Trick Room). Team card: Torkoal
  12 HP / 32 SpA / 22 SpD (157 HP / 112 SpD).
- v16 (`trsheet/patch_v16_tork.py`, backup `trsheet/tr-sheet.v15.html`): Matchups grid Torkoal column re-run for the new spread
  (`mxtr/matchup.py` takes `TK_ST=157,105,160,150,112,36`; `GRID_MONS=Torkoal GRID_TAG=_tork22 tr_grid.py`, TR=1 and 0; a rerun with the old
  stats reproduced all 35 published cells). Merged sheet grids: `mxtr/gx_cells_{tr,notr}_inc_t22.json` (use these for add_charts.py from now
  on); the battle sim's `gx_cells_*_inc.json` (GRID_DIR) are unchanged. Verdicts: 8 of 70 worse (TR: Sneasler, Incineroar, Basculegion,
  Garchomp; no TR: Rillaboom, Sneasler, Metagross, Corviknight: less HP, and Eruption weaker after a switch-in hit), 2 better (Volcarona,
  Indeedee-F). Coverage is offense-only, unchanged.

## Torkoal spread A/B in full battles (2026-10-04)
`pssim/tork_ab_run.sh` (10 threads on the Mac, ~42 min): the sheet's four on every tab that brings Torkoal (Tailwind, Rain, Snow, Trick Room,
Rain + Sun, Perish) x 6 opposing leads x 64 games (first game index 2000), old Torkoal (`myteam_real_tork32.json`, 32 HP / 2 SpD, grid
`mxtr/`) vs new (`myteam_real.json`, 12 HP / 22 SpD, grid `mxtr_t22/` = sheet t22 cells + new-spread `_ext` cells), same games for both.
`tork_ab_report.py` -> `results/tork_ab_report.txt`: new - old = Tailwind +0.8 +- 1.3, Rain +0.3 +- 3.4, Snow -5.4 +- 2.2, Trick Room
-5.9 +- 2.5, Rain + Sun +0.9 +- 2.6, Perish -0.2 +- 1.5; -1.0 +- 1.0 over these tabs, -0.6 +- 0.6 over the whole ladder. The losses come from
physical leads (Snow: Froslass + Sneasler -12.5 +- 5.2; Trick Room: Farigiraf + Incineroar -12.5 +- 6.1), as in the grid.
Planner caveats raised by the teamsearch thread (verified in plan.rs/battle4.rs): 2 planning seeds per turn shared by all cells
(chance events like a second Protect can look certain), no expected-value scoring of known-probability events, the type-immunity prune
also removes predict-the-switch rows in the anticipation pass, and side 0 never clicks Trick Room while it is up.

## Double Protect, real-game value weights (2026-10-04)
- Real rate (`pssim/protect_replays.py fetch|rated|stats`; logs cached in `pssim/replays_protect/`, ~5,300 replays incl. 4,496 Bo3 with
  open team sheets): after a fresh successful Protect, the same Pokemon Protects again 5.5% of the time in Bo3 (9.8% ladder Bo1) and
  switches out ~30%. Sim (`protect_sim.py` on BATTLE_TURNS logs): 31-39%, switch out 8-10%, with Trick Room up or down.
- Engine stall counter matches Showdown (1/3, x3 per repeat). Not planning noise: BATTLE_NS=8 raises the rate (`ns_test_run.sh`).
- `champ-battle-v5` (= v4 + `EG_NO_DOUBLE_PROTECT=0|1|both`, default off, games identical to v4; `src_battle_v5.tar.gz`). Ban test
  (`dp_test_run.sh`, `dp_test_report.py` -> `results/dp_test_report.txt`, 960 games per arm): banning my second Protect -0.9 +- 0.7 for
  me; banning theirs -2.2 +- 1.2 for me (their doubles are mistakes, mostly vs Tailwind -7 and Indeedee TR -4: stalling my Trick Room).
- Real-game weights (`replay_feats.py` -> `results/replay_feats.json`; `fit_real_value.py` -> `results/fit_real_value.json`): the 11
  features a replay can reproduce, on 4,496 Bo3 games. Relative to HP: asleep -0.76 (self-play -0.05), paralysed -0.33 (-0.07),
  burned/poisoned -0.25 (-0.08), Tailwind +0.19 (-0.02), Protected last turn -0.06 (-0.52), Pokemon alive 0.61 (0.34).
  `elo_check.py`: about the same in every rating band; real-fit weights predict 1340+ games better than the self-play fits.
- `egvalue6.json` (`build_egvalue6.py`: all 11 from real games) Protects far MORE (theirs 28% of actions vs 17%; real 13%) and my win
  share drops 8.8 +- 2.0: the self-play Protected-last-turn penalty is on-policy, correcting this one-turn planner's horizon effect.
  `egvalue6b.json` (`build_egvalue6b.py`): egvalue5 with only asleep/paralysed/burned/Tailwind from real games (self-play has no data
  there). Behaviour/win comparison: `value_behaviour.py <dirA> <dirB>` (results/ev6_behaviour.txt; ev6b in results/ev6b_test).
- Ideas from the teamsearch thread not done yet: role-aware status (burn x physical share, burn vs poison, paralysis sign flip under
  Trick Room), and a damage-race / turns-to-KO feature (the real fix for the horizon effect: Protect, setup, Trick Room/Tailwind timing).
- **Damage race (champ-battle-v6, 2026-10-04):** `RACE=1 CALC_DATA=../native/champions_data.json` appends two features (plan.rs
  `race_feats`): the active Pokemon trade their best expected hits (calc.rs, mid roll x accuracy x expected hits, spread 3/4) for up to 3
  turns in Speed order (Trick Room / Tailwind for the turns left, paralysis, sleep/freeze skip, burn/poison chip, Leftovers); outputs KO
  edge (foe KOs minus mine, 1/k for race turn k) and HP edge. Unset: identical to v5. `RACE_DEBUG=1` prints the first few races.
  `champ-battle-v7` = v6 + an exact per-thread damage memo (same games as v6; race overhead +14% vs +31%; `RACE_NOCACHE=1` disables).
- `egvalue7.json` (`build_egvalue7.py` on `results/race_train`: 3,548 self-play games, `race_train_run.sh`, played with egvalue6b):
  race KO edge +0.50 +- 0.03 (HP edge ~0); held-out log loss 0.419 -> 0.403. Status/Tailwind fixed from real games, hand-set as before.
  Test: `ev7_test_run.sh` -> results/ev7_test (compare with value_behaviour.py).
- **Two-turn Protect check (champ-battle-v8 = v7 + `DP2=1`, 2026-10-04):** for an active Pokemon that Protected successfully last turn
  and still has Protect weight in its side's mix, battle4.rs compares that side's best Protect-again option with its best other-move and
  best switch option (one-turn value vs the other side's mix), each played against the other side's likeliest replies (<= 4, >= 90%) and
  scored after one more turn as a small matrix game (plan.rs `reduced_options`: three strongest hits + Protect per Pokemon, one seed). If
  Protect again is worse, its options are dropped and the mix re-solved. Per-game counters `dp2` = [my checks, my drops, their checks,
  their drops]. Unset: identical to v7. About +10% time. Test: `ev7dp2_test_run.sh` -> results/ev7dp2_test (vs results/ev7_test).
- `champ-battle-v9` = v8 + `DP2_SW=1`: the check's second turn also offers each active Pokemon's switches to the bench (real players
  switch out ~30% of the time after a Protect; the sim ~10-14%). Unset: identical to v8. Test: `ev7dp2sw_test_run.sh` -> results/ev7dp2sw_test.
  v8 result (results/ev7dp2_behaviour.txt): their Protect-again 37.6% -> 26.2% (no Trick Room 29 -> 22%, last Trick Room turn 49 -> 39%),
  mine 34.9 -> 26.9%; win share +1.1 +- 0.8 (noise). The progress page (status_server.py, port 8766) needs each run's log to start with
  "HH:MM:SS <jobs.json> -> <outdir>, <games> games, <threads> threads (...)"; the ev*_test / race_train scripts now write it.
  v9 result (results/ev7dp2sw_behaviour.txt): no change vs v8 (their Protect-again 26.8% vs 26.2%; win share +0.3 +- 0.3; most games
  identical), so the check's verdicts don't depend on switches in its second turn. Recommended setup: v8, DP2=1, RACE=1, egvalue7.
- **Double Protect by win chance (2026-10-05):** `pssim/protect_decided.py real | sim <dir>` buckets the Protect-again rate by the win
  chance at the decision (real games: the real-game value model; sim: the planner's own value from BATTLE_FEATS + BATTLE_TURNS logs;
  `dpfeats_run.sh` -> results/dpfeats_a, _b = the ev7dp2 games with features). Real players slide smoothly from 28% (below 5%) to 4-5%
  (even games) to ~2% (ahead); they rarely reach lost positions (0.6% of chances below 2%; they forfeit). The sim's opponents: 31% of
  their chances are below 2% (47% Protect again there) and 71% below 20%. Bucket by bucket the sim is close to real at 2-10% (29 vs 27,
  20 vs 17), about double at 10-65%, similar above. Overall 26.2% vs 5.9%, but real behaviour in the sim's positions would give 17.2%, and
  the sim's behaviour in real positions 9.9%; in open positions (2-98%) 17.1% vs 12.6%. So most of the gap is which positions occur.
  Calibration: the real-game model is on the diagonal on real games; the planner's value is right at the extremes but too confident in
  the middle on sim games (rated 28% -> won 38%, 72% -> 62%). Decision log (`DP2_LOG=1`, champ-battle-v10, `dplog_run.sh`,
  `dplog_report.py`): 67% of the opponents' Protect-again checks have no bench left; where a switch exists in an open position the
  switch-in arrives at 70% HP and is KO'd 43% of the time, and the three options' two-turn values are within ~3 points.
- Team search's check of v3 + egvalue5 vs v8 + DP2 + RACE + egvalue7 on 10 teams (teamsearch/simcmp.json): rank correlation ~0.55, the
  Delphox / Garchomp / Incineroar / Kingambit teams stay on top; against 10k real regional matches the matchup error is about the same
  (RMS 0.37 -> 0.36 log-odds); Perish still far too easy, Sun opponents now too hard (they set Trick Room more under RACE).
