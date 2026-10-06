# Trick Room Six sims: handoff

This folder is the machinery behind the **Trick Room Six** sheet (Pokémon Champions VGC doubles, Reg M-C), moved out of a Claude Cowork session so it can run on all cores of a Mac. Read this file first.

- **Threads (since 2026-10-05):** the work is split across four Claude sessions. "TR sheet" owns the sheets and the sheet kit (start at
  `trsheet/HANDOFF.md`), "Battle sim" owns the full-battle simulator and planner (`native/champ/`, the position value, replay analysis;
  sections "Full 4v4 battle sim" and "Double Protect, real-game value weights" below), "Team search" owns `teamsearch/`, and "Eval bar"
  owns `evalbar/` (a chess-style evaluation bar for games; start at `evalbar/HANDOFF.md`). They coordinate by SendMessage.
- **Git (since 2026-10-05):** the folder is a git repo (branch `main`) with a private GitHub remote, `abnew123/champions-sims`; the user
  reviews it before it goes public. Each thread commits its own area with explicit paths (no `git add -A`) and pushes only when the user
  asks. Keep names out of everything tracked: write "the user" or "the player", never a real name, the Mac username, absolute `/Users/`
  paths or an email, and no other people's names either (opponents, Showdown usernames, tournament players). `.gitignore` keeps out
  dependencies, build output, results and other large generated files, local binaries, and data with names (game recordings, replay logs,
  scraped tournament pages). Commits use the no-reply email in the repo's git config. License: MIT (`LICENSE`); Showdown's notice, data
  sources and the trademark line are in `NOTICE.md`.
  **Privacy hooks (since 2026-10-05, 6:50 pm):** `.githooks/pre-commit` and `commit-msg` run `tools/privacy_scan.py`, which refuses a
  commit whose added lines, file names or message carry an email, an absolute `/Users/` path, an IP or EC2 address, a key, a Showdown
  replay line with a username, or any string in the private list `.git/private-patterns.txt` (one case-insensitive regex per line; the
  user's names, opponents' names, key-pair names; it is in the git directory, never tracked, shared by every worktree). Installed with
  `python3 tools/privacy_scan.py install` (sets `core.hooksPath` to the absolute `.githooks` path, so the Eval bar worktree runs the
  same hooks); a refusal lists `file:line: what: the line`; fix the text, never `--no-verify`. Add a new private string by appending a
  line to that file. Pre-public checks: `python3 tools/privacy_scan.py tree` (every tracked file) and `history origin/main` (every
  pushed commit, added lines and messages); on 2026-10-05 the latter finds one thing to purge, an AWS key-pair name in `cc65069`.
- **Current battle-sim setup (final as of 2026-10-05, for every team; amended the same day: v13 and `RACE_TIES=avg`).** From `pssim/`:
  `RACE_TIES=avg DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_ANTICIPATE=1 EG_VALUE=egvalue9.json GRID_DIR=<the team's
  generic grid> ../native/champ/bin/champ-battle-v16 battle ../native/engine_data_spot.json <starts.jsonl> <outdir> <threads>`
  (source of the binary: `native/champ/src_battle_v16.tar.gz`; v13, v14, v15 and v16 play identical games, v16 about 2.3x faster than
  v13; without `RACE_TIES` they play v12's games). Perish matchups: use
  real-data rates, not the sim. Why and how it was tested: the last bullets of "Double Protect, real-game value weights" below. Version 16
  of the sheet still shows numbers from the old setup (champ-battle-v4 + egvalue5).
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
  native/engine_data_spot.json = engine data + EXTRA_MOVES=megahorn, since 2026-10-05 also EXTRA_SPECIES=barbaracle,houndstone EXTRA_ITEMS=barbaracite for the Eval bar's recorded games; additive only) plays every kept cell to the end with the planner (switches allowed on
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
- **Planner work after the split (2026-10-05, Battle sim thread).** The user settled Torkoal at 32 HP / 2 SpD (sets: `sheets/trick-room-six/team.json`
  = `pssim/myteam_real_tork32.json`), and the TR six now reads the sheet kit's generic grid (`GRID_DIR=../sheets/trick-room-six/work/grid`).
  - `champ-battle-v10` = v9 + `DP2_LOG=1` (logging only). `champ-battle-v11` = v10 + `PERISH2=1` (a Perish count dooms only a Pokemon that
    cannot leave: trapped, or no bench; scaled by turns left and the trapper's HP) + `TRSYM=1` (the slower side, either one, refuses to
    click Trick Room while it is up; before: side 0 only). Both off by default; unset, v11 plays v8's games.
  - Perish: `perish_test_run.sh`, `perish_report.py` (results/perish_base vs perish_p2, 96 games): PERISH2 does not make the sim's Perish
    teams trap and sing against the TR six (Perish Song in ~40% of games either way; our lead KOs Gengar early); our win share 95.8 -> 91.7
    (-4.1 +- 3.7). The user's call: Perish is too long-horizon for this sim and small in the meta, so use a stock real-data rate for Perish
    matchups (Team search: `TS_PERISH=real`). PERISH2 stays off.
  - Refit in progress: `refit8_run.sh` -> results/refit8 (3,600 self-play games on the settled sets and generic grid, v8 DP2 RACE, played
    with egvalue7), `build_egvalue8.py` (status / Tailwind tied to the HP weight at real-game ratios; calibration by bucket on held-out games).
  - Bar for calling a setup final: Team search's 10-team comparison against real regional results, RMS matchup error over the nine
    non-Perish archetypes (v3 + egvalue5: 0.26 log-odds; v8 + DP2 + RACE + egvalue7: 0.25; sim noise ~0.14).
  - `egvalue8.json` (`build_egvalue8.py` on results/refit8, 3,556 games): held-out log loss 0.384 (0.406 without race); calibration on
    held-out games is on the diagonal in every bucket, so egvalue7's mid-range over-confidence was a mismatch between weights and the
    games they were used on. `egvalue8_norace.json` = the same fit without the race weights (`NORACE=1`).
  - `champ-battle-v12` = v11 + `EG_VALUE_B=<file>` (side 1 plans with its own weights; each side solves its own matrix, replacement
    choices too) + `DP2_SIDE=0|1`. Unset: v8's games; the same file on both sides through the new path: identical games.
  - Head-to-head on the TR six (`h2h_run.sh`, `h2h_arms.txt`, `h2h_report.py`, results/h2h_*, 480 games per arm, my win share):
    old/old 71.7; new mine only 76.5 (+4.8 +- 3.2); new theirs only 65.1 (-6.7 +- 3.3); new/new 70.4. Race only (egvalue8 vs
    egvalue8_norace): neither 74.1; mine only 76.2 (+2.1 +- 3.0); theirs only 65.8 (-8.3 +- 2.8). The new value is a stronger player
    (~5 points to its user); the race helps the opponents more than the TR six.
  - Team search's decomposition on its 10 teams (teamsearch/decomp.py): the drop vs Sun / Indeedee TR / Snow arrives with the race
    (-9 / -12 / -7), not with the Protect check (0) or the status weights (Sun -6 only). Pending: its one-side-only arms with v12 and a
    multi-team self-play run with features, for a value fitted on more than the TR six.
  - **The value is team-specific in its baseline** (`value_xcheck.py`): egvalue8 rates side 0 at 36.8% on the TR six's games (actual 36.8%)
    but at 45.5% on Team search's ten teams' games (actual 59.8%). `build_egvalue9.py <TR six dir> <@list of other teams' dirs> [out]`
    fits shared slopes with one intercept per team: held-out log loss matches each group's own fit (TR six 0.386; the ten teams 0.438 vs
    0.522 for egvalue8). Intercepts: TR six self-play (all 15 leads, default backs) -0.41; the ten teams -0.04 to +0.90 (their best
    fours), so the intercept is partly the quality of the four brought.
  - `egvalue9.json` (general intercept +0.544 = the ten teams' mean), `egvalue9_tr6.json` (-0.41), `egvalue9_teams/<team key>.json`
    (Team search's ten): the same slopes (HP 1.18, alive 0.89, boosts 0.25, Trick Room 0.26, grid 0.43 / 1.07, Protected -0.52, type edge
    0.27, screens 0.13, race KO 0.49, race HP -0.01), fitted on results/refit8 + Team search's v12 features pass (played with egvalue8).
  - Head-to-head on the TR six, egvalue9 vs egvalue8 (`ARMS=h2h_arms9.txt LOG=h2h9.log ./h2h_run.sh`, results/h2h9_report.txt; baseline
    egvalue8 both sides 70.4): egvalue9 mine 72.9 (+2.5 +- 1.7); egvalue9 theirs 72.3 (+1.9 +- 1.9); both 72.9; general intercept on both
    72.6 (-0.3 +- 2.5 vs the TR-six intercept). The pooled slopes play as well on the TR six, and the intercept does not matter there.
  - Team search's checks of egvalue9 (teamsearch/intercept_test.py, simreal.py; 2,400 games per arm on its ten teams): each team's own
    intercept vs the general one changes scores by 2.1 points on average with no pattern (rank correlation 0.90), so one general file;
    matchup error against real regional results over the nine non-Perish archetypes is 0.26 log-odds (v3 0.26, v8 0.25): unchanged.
    The remaining error has the same shape in every setup (Rain, the Trick Room archetypes and Rain + Sun 0.3-0.4 too hard as opponents;
    Tailwind and Balance 0.25-0.33 too easy) and probably lives in the replay archetype models (leads, brings), not in the value.
  - **Final setup: champ-battle-v12 + egvalue9.json + RACE=1 + DP2=1 + anticipation** (see the top of this file). What it is: status and
    Tailwind weights from real games; a damage-race feature; a two-turn check on second Protects; slopes fitted on eleven teams. What it
    is not: it cannot play Perish trap, and absolute matchup win rates carry about 6 points of error per archetype.
  - **For the Eval bar thread:** `pssim/egvalue9_sym.json` (`SYM=1 build_egvalue9.py ... egvalue9_sym.json`): the same model fitted on the
    same eleven teams' games with every position also mirrored, so the intercept is 0, and without the two grid features; use with
    `TRSYM=1` and an empty `GRID_DIR`. Held-out log loss 0.415 on the TR six's games and 0.447 on the ten teams' (the side-0 version:
    0.386 / 0.438). Note: under this symmetric constraint the Trick Room weight falls to 0.07 (0.26 in egvalue9), so in the side-0 fits
    the Trick Room weight and the team intercept are partly entangled. **Since 2026-10-05, 8:45 pm the bar's value is
    `pssim/egvalue9_sym2.json`** (`SYM=1 TIE_TR=1 build_egvalue9.py ...`): the same fit with Trick Room turns x speed edge tied to
    the HP weight at the real-game ratio (0.201 instead of 0.073; the real-game model gives 0.183, egvalue9 0.258). Self-play held-out
    log loss is slightly worse (TR six 0.4154 -> 0.4198) but the Eval bar's 560 real held-out games decide: overall 0.5245 -> 0.5240
    (no worse), with Trick Room up (321 positions) 0.5199 -> 0.5141 (better, within noise); on the user's recorded Trick Room games the
    turn-1 values rose 3-8 points. Numbers: `evalbar/results/compare_sym_sym2.json` on the Eval bar's branch.
  - History was rewritten on 2026-10-05 to remove three opponents' in-game names from the recording spot notes (all commit hashes
    changed; any hash quoted above from before that date is stale: find commits by message).
  - **champ-battle-v13** = v12 + `champ evalpos` (evalpos.rs: per position, the turn solved as in battles with every cell averaged over
    `EVAL_SEEDS` seeds; value, static value, features, and every option of both sides with its mix weight, value and whether it was the
    choice made; for the Eval bar thread) + `RACE_TIES=avg` + an empty grid now gives grid features of exactly 0.
  - **Speed ties in the race (found through the eval bar's swap-sides check):** the race feature let side 0 move first on every Speed tie
    between opposing Pokemon, so side 0 was favoured in mirrors (a Garchomp mirror read 0.46 from one side and 0.34 from the other).
    `RACE_TIES=avg` runs the race with each side winning the ties and averages; features are then exact mirror images under a side swap.
    Effect on the TR six in the final setup (`ties_test_run.sh`, results/h2h_ties_avg vs h2h_g9_g9, 480 games): overall -0.4 +- 0.8,
    393 games identical; all of the change is against opposing Farigiraf leads (Trick Room tab -13 +- 10, Indeedee TR +4 +- 3). It is a
    correctness fix, so it is part of the final setup from here on.
  - Luck in `evalpos`: the same position from the two sides differed by up to 0.14 with 8 seeds, 0.05 with 32, 0.03 with 96.
  - **champ-battle-v14 = v13, faster, same games** (2026-10-05). A profile of v13 showed the value function at a third of run time (a
    tenth of all time building strings for matchup-grid lookups, 8% recomputing the type-edge feature) and 37% in the system allocator.
    Changes: grid names and cells memoised per thread (no strings on the hot path); type edge computes the attackers' move types once
    per call and memoises type-vs-types effectiveness; the mimalloc allocator (Cargo feature `fast-alloc`, on by default; needs a C
    compiler and crates.io at build time; `cargo build --release --no-default-features` builds without it); `codegen-units = 1`.
    Checked identical to v13: 120 battles across all ten archetypes (results, per-turn states, Protect-check counters) and 20 evalpos
    positions (every output field). Speed, one thread on the Mac: 20 battles 150 s -> 92 s (-39%); 20 evalpos positions 74 s -> 54 s
    (-27%). Flags and the final setup are unchanged; only the binary name changes. What is left is the engine itself: simulating turns
    is now 69% of run time, nearly all of it in event dispatch (handler lookups by string key; `get_stat` alone triggers a fifth of all
    events). Speeding that up means restructuring handler lookup and would need the Showdown differential tests (`champ turn`) rerun.
  - **champ-battle-v15 = v14 + staged luck sampling in `evalpos`** (`EVAL_ADAPT=1`; battles and the default evalpos mode are unchanged
    and identical to v14). Every cell gets 2 seeds; options still in contention (in a side's mix, or within 0.15 of that side's best
    option, plus the joint actions actually played) get their cells against the other side's contenders raised to 8 seeds, then those
    within 0.06 to `EVAL_SEEDS`; the turn is re-solved after each stage (`EVAL_STAGES`, `EVAL_MARGINS` override). On 20 positions at
    32 seeds, one thread: flat 216 s, staged 45 s (4.8x; flat 8 seeds took 55 s). Against flat 32: position value within 0.0003,
    values of options in the mix within 0.002, the value of the move actually played within 0.0013, the same top option for every side
    (flat 8 agreed on 30 of 40 and was off by up to 0.07). Options outside the contention band keep their 2-seed values (noisy, by design).
  - **champ-battle-v16 = v15 with a faster engine, same games** (2026-10-05, 7:20 pm). Profile of v15: handler discovery
    (`find_event_handlers`) was 57% of all time, nearly all of it hashing and comparing strings: `cb_names.contains` on every
    prefixed callback name (27%), `Dex::eff` lookups by id, `cbs.get` per effect, plus serde_json flag reads in the suppression checks.
    Changes, all in `native/champ/src` (dex.rs, battle.rs, state.rs, plan.rs, sim.rs): every callback name gets a dense index at load
    (123 names) and each effect a 128-bit mask plus an indexed table, so a scan is a bit test and discovery for a name no effect defines
    (most prefixed variants) costs nothing; `EvNames` carries the indexed names; `Dex::eff` and `Dex::mv` are cached per thread by the
    id's address (ids are interned, a `&'static str` never changes); each Pokemon caches the effect data of its ability, item and status,
    validated against the current id on every read so it cannot go stale (`DCache`, an atomic pointer so the planner's threads may
    share a start position); the breakable / cantsuppress / notransform / ignoreKlutz / suppressWeather flags are precomputed; an event
    that finds no handler returns before building its context; the ally/foe loops are skipped when no effect defines those names; the
    planner's memo keys (damage race, type effectiveness, grid cells) hash ids by address (`PId`: a different address only misses the
    memo), and the race reads each side's screens once instead of allocating a string list per target. Checked: `champ turn` on all
    6,900 Showdown positions in all four RNG modes still exact; 120 battles across the ten archetypes (results, per-turn states,
    features, Protect counters, logs) identical to v15; 20 replay positions through `evalpos` (EVAL_ADAPT, 32 seeds, the Eval bar's
    settings) identical in every field. Speed: engine benchmark 77.5 -> 27.2 us/turn (-65%); 20 battles on one Mac thread 64.5 s ->
    29.6 s (-54%); the 120-battle set on three threads 145 s -> 59 s (-60%); evalpos -61%. What is left: the remaining event overhead
    (`run_event` bookkeeping, `evn` lookups, the Boosts/Types vectors in `get_stat`/`get_types`) is about a quarter of run time, the
    value function (race, type edge, grid) about a fifth, allocation about 7%.
  - **champ-battle-v17 = v16 with a 256-bit callback mask, same games** (2026-10-05, 8:20 pm), needed for
    `native/engine_data_full.json`: everything Showdown's data knows (1,469 species incl. formes, 936 moves, 581 items, 317 abilities,
    162 callback names; `ALL=1 node ../native/export_engine.js ../native/champions_data.json ../native/engine_data_full.json`), so the
    Eval bar's live spectator mode can build any position; effects whose code has no Rust port are reported as `unsupported` when they
    fire, as before. v16 cannot load it (its mask holds 128 names); the spot file works on both. Checked: `champ turn` exact on both
    data files; 120 battles under the full setup identical to v15 with v16 and with v17 + full data (v15 331 s, v16 166 s, v17 127 s on
    three threads; the two earlier 120-battle comparisons in the v16 note had passed only the first flag through a zsh variable, so they
    compared reduced-planner games; the single-thread 20-battle checks and this rerun used the full flags). Speed equal to v16.
  - **champ-battle-v18 = v17 + two evalpos modes, battles unchanged** (2026-10-06, 12:50 am; 20 check battles identical to v16).
    `EVAL_HORIZON=2`: after the one-turn staged solve, every option in contention (in a side's mix, within `EVAL_H2_MARGIN` 0.06 of
    its best, or actually played) gets its cells against the other side's contenders re-valued after one more turn, solved as a small
    matrix game (`battle4::next_value`: each Pokemon's Protect plus its `EVAL_H2_HITS` 2 strongest hits, no switches, one luck seed per
    sample, `EVAL_H2_SEEDS` 2 samples), then the turn is solved again, up to 3 rounds; cells outside the set keep one-turn values
    (about 5x the one-turn cost). Built to test the Eval bar's broadcast finding (players Protect and switch more than the planner's
    mix: regional attack 49% played vs 59% planned, Protect 13% vs 8%, switch 17% vs 13%; the same on 560 Showdown games) against a
    one-turn-horizon explanation; the test run (all 19 regional games, 629 positions; 662 Showdown positions at both horizons) is
    scored by the Eval bar's `study.py`. **Result (1:00 am):** the two-turn horizon raises the planner's Protect share toward the
    players' (regional per action: planned 8.6% -> 11.0% vs 13.2% played; Showdown 8.6% -> 11.3% vs 12.7%), about half the gap, and
    switching slightly (13.5% flat regional; 14.1% -> 15.3% vs 12.6% Showdown, now overshooting); the Protects players did play cost
    less under it (regret median 1.5 -> 0.8 points). It does not raise top-pick agreement (45% -> 42% regional, 47% -> 45% Showdown) or
    lower regret. The planner's mixes came out flatter and its log score on players' choices better (regional -1.89 -> -1.73, Showdown
    -2.05 -> -1.97), but a rerun of 200 Showdown positions with 4 luck samples instead of 2 kept the shares (Protect 11.8% either way)
    while most of the log-score gain went away (per slot: h1 -2.356, 2 samples -2.308, 4 samples -2.348), so the flattening was
    mostly sampling noise. Conclusion: a longer horizon explains part of the Protect gap, not the sharper-than-expert mixes; what is
    left points at what the planner knows that players do not (exact sets and spreads: hedging under uncertainty means more Protect
    and switching and flatter mixes) rather than at depth. Not used for play; the one-turn solve stays the default. `EVAL_MATRIX=1|full`: the payoff matrix on each output line (rows / cols / labels / final mixes /
    one-turn values and seed counts per cell, two-turn values under EVAL_HORIZON=2) for reading departures from the equilibrium against
    the opponent's actual move; "1" raises the rows and columns holding a slot's actual or most-weighted option to full seeds first.
