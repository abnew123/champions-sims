# Trick Room Six sims: handoff

This folder is the machinery behind the **Trick Room Six** sheet (Pokémon Champions VGC doubles, Reg M-C), moved out of a Claude Cowork session so it can run on all cores of a Mac. Read this file first.

- **Threads (since 2026-10-05):** the work is split across four Claude sessions. "TR sheet" owns the sheets and the sheet kit (start at
  `trsheet/HANDOFF.md`), "Battle sim" owns the full-battle simulator and planner (`native/champ/`, the position value, replay analysis;
  sections "Full 4v4 battle sim" and "Double Protect, real-game value weights" below), "Team search" owns `teamsearch/`, and "Eval bar"
  owns `evalbar/` (a chess-style evaluation bar for games; start at `evalbar/HANDOFF.md`). They coordinate by SendMessage.
- **Git (since 2026-10-05):** the folder is a git repo (branch `main`) with a private GitHub remote, `abnew123/champions-sims`; the user
  reviews it before it goes public. Each thread commits its own area with explicit paths (no `git add -A`) and **pushes `main` after
  each commit without asking** (the user, 2026-10-07, 11:40 pm: "let's just push continuously, don't ask me"; a push carries every
  thread's commits, the pre-commit privacy hooks are the gate). Keep names out of everything tracked: write "the user" or "the player", never a real name, the Mac username, absolute `/Users/`
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

- **The Showdown bot's engine (2026-10-12; since 6:30 pm the bot runs `battlesim-champ-bot` -> `bin/champ-bot-2026-10-12` with the learned value `bot/value/vnet_h64_search.json`, see bot/position.py; the paragraph below is the morning's freeze, still true of `battlesim-champ`):** `native/champ/bin/battlesim-champ` points to `bin/champ-bot-2026-10-11` (a byte-identical copy of the build the bot runs; sha256 file beside it), not to `target/release/champ`, so a rebuild cannot change the live bot (the user: no bot changes until they say so). Develop with `CARGO_TARGET_DIR=$PWD/target_value` (link `bin/battlesim-champ-dev`); repoint `battlesim-champ` only when the user approves a bot change.
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
  - **Proposal, not started (Team search, 2026-10-06, 2:30 am): cluster the opponent pool instead of the name-based archetype rules.**
    Evidence: mean Jaccard similarity of random pairs of sixes inside each rule archetype (regional sheets / ladder previews): Tailwind
    0.36/0.34, Sun 0.20/0.23, Indeedee TR 0.19/0.18, Rain 0.24/0.24, Balance 0.30/0.51, Sand 0.40/0.36, Snow 0.29/0.33, TR without
    Indeedee 0.22/0.26, Rain+Sun 0.51/0.63, Perish 0.37/0.37: Sun, Indeedee TR and TR are broad buckets that six lead pairs
    under-represent; ladder "Balance" is mostly one copied six (Rillaboom 96%, Incineroar 84%, Garchomp 74%, Gholdengo 73%, Raichu 67%,
    Volcarona 64%); 12-20% of "Balance" carries Dragonite or Aerodactyl with Tailwind, which the rules ignore. Sketch: k-medoids on
    Jaccard over sixes from the replay corpus; each cluster with its own lead pairs and sets, weighted by its frequency in the target
    meta; each cluster tagged with its nearest named archetype so the sheets keep nameable rules. This is the "archetype opponent
    models" lever left after race / DP2 (the regional bar stayed at 0.26). Costs: a fresh Team search climb (its weights, results,
    Perish stock rates and the sim-vs-real table are keyed by the 10 names), and the TR sheet's lead tabs depend on the names; so it
    comes after the current climb, with both threads looped in. Sources for the sixes: `teamsearch/regmatch/` (standings with round
    pairings, git-ignored, also gives real matchup outcomes per cluster pair) and `regionals/regional_teams.json` (anonymised sheets);
    `pssim/endpair_scan.py` is Battle sim's replay scan, not Team search's. Validation: Team search's `simreal.py` scores its ten teams'
    confirm games per opponent group given the model files and a setup name; it needs one edit (archmatch's classifier hook reading real
    rates by cluster instead of by name). **Done so far (2026-10-06, 3:45 am; the user said go, with the condition that a human must
    still be able to place an opponent's team in seconds, so no clustering a human cannot apply):**
    - No natural number of clusters exists (`pssim/cluster_opps.py scan`, results/cluster_scan_*.txt): weighted k-medoids on Jaccard
      over 8,651 real sixes (2,531 regional sheets + 6,120 ladder previews), k 4..40, plain or IDF-weighted: within-cluster similarity
      rises smoothly 0.21 -> 0.40 with no elbow, silhouette 0.06-0.14 at every k, two random halves agree poorly (adjusted Rand 0.2-0.5).
      The six-space is a continuum around about ten tight cores.
    - So the grouping is an ordered list of human-checkable rules, learned from the data and frozen: `cluster_opps.py rules 100`
      (results/core_rules_both_100.{txt,json}): species pairs / triples that co-occur at least twice as often as chance and cover at
      least 100 teams, greedy by coverage, grown to triples that ride along with 60% of the group and split on a species that divides it
      ("also has X" / "without X"); 25 rules cover 64% of real teams, the rest is "other" (today's if/else tree as the fallback name).
      `cluster_opps.tag(six, rules)` applies them: first rule whose species are all present (and excluded ones absent) names the team.
    - The sim's opponents are real games, not groups: `pssim/opp_pool.py build` -> `pssim/opp_pool.json` (git-ignored, 12 MB; rebuilt
      from pssim/replays_protect): one entry per side of each cached Reg M-C Bo3 game with an open team sheet (8,992 entries, 4,496
      games): the six with its sets from |showteam| (spreads by species from regionals/smogon_mc_sets.json, stat points are never shown),
      the lead pair and the four brought as played (81% fully seen; otherwise filled from the same six's other games, then at random;
      `bring_seen`), rating, result, and the core-rule group. `opp_pool.py jobs <myteam> <lead a,b> <back c,d> <n> <out> [min rating]
      [group]` writes explicit battle_starts.js jobs (our four fixed, their four as played, rating-weighted draw); 12 pool games with the
      TR six ran cleanly under v16 + engine_data_full with no unsupported hits.
    - The real reference for the bar: `pssim/group_real.py` -> results/group_real.{txt,json}: per group, team share and win rate in
      the regionals (per-game rates from Bo3 results) and on the ladder (both sides of the pool's games), and per group pair with at
      least 15 matches.
    - **Validated (Team search, 2026-10-06, 4:10 am; `teamsearch/poolbar_report_v17g.txt`):** the same ten teams with their climb
      brings, 23,907 pool games over 2,500 entries vs the archetype-model baseline, both scored against the field's real regional rate
      by opponent group with the offset removed. By rule archetype the RMS error falls 0.29 -> 0.18 without Perish and 0.41 -> 0.20
      with it (Tailwind +0.23 -> +0.13, Sun -0.35 -> -0.22, Indeedee TR -0.33 -> +0.09, Balance +0.32 -> +0.13, Rain -0.51 -> -0.33,
      Perish +1.21 -> +0.37); by core-rule group 0.23 vs the regionals (19 groups), 0.15 vs the ladder (12). What remains: Rain and
      Rain + Sun still too hard, Tailwind / Snow / Perish too easy. Team search's follow-up on the pool games: each archetype's real
      ladder win rate vs its sim win rate against our ten (Rain 46.0 / 44.1, Rain + Sun 56.1 / 47.0, Sun 49.6 / 45.3, Tailwind 49.7 /
      36.3, Balance 53.1 / 36.1, Snow 56.9 / 35.8, Indeedee TR 50.3 / 35.4, Perish 47.8 / 33.4): relative to their real strength, Rain
      and Sun sixes play 8-10 points stronger under the planner than Tailwind / Balance / Snow / Indeedee sixes; Snow is the strongest
      archetype in reality and among the weakest in the sim. Reading: the planner pilots "click the boosted move" teams near-perfectly
      and under-plays teams whose strength is multi-turn sequencing (Tailwind timing, Fake Out + setup, pivoting), the same weakness as
      the Protect / switch gap in the broadcast study. Cheap check for the Eval bar: regret by the player's archetype on the 560 real
      games (do Tailwind / Snow / Balance players make choices the planner rates worse yet win more). **The pool replaces the archetype
      models as the opponent source**;
      the sheets key by core group (nearest archetype name kept), Team search runs a fresh pool-based climb in the daytime (brings per
      opponent team or group, scores weighted by real group shares), the TR sheet's optimal-pick step takes the pool's sixes.
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
    and switching and flatter mixes) rather than at depth. Not used for play; the one-turn solve stays the default. **Follow-up by the
    Eval bar (2026-10-06, 1:30 am):** spread uncertainty does not explain it either: re-solving each player's mix on matrices averaged
    over four draws of the opponent's spreads (444 regional decisions) left planned Protect at 8.8% vs 13.3% played, agreement and log
    score unchanged, mixes no flatter (`evalbar/results/spread_uncertainty_day1.json`). So depth explains about half the Protect gap and
    spread knowledge none; the user's read of the 39 costly broadcast plays (13 switches, 10 Protects, 5 setup moves) is that the engine
    undervalues setup and switching, plus some real mistakes. **Tested on real outcomes by the Eval bar (2:00 am;
    `evalbar/results/aftermath_setup_switch.json`):** 3,408 Showdown Bo3 positions from turn 2 on, egvalue9_sym2, actual win rate minus
    the rescaled rating with each side's overall bias removed: after a setup move -3.2 points (SE 2.7) with the lookahead value, holding
    +1/+2 boosts -0.2 (1.9), +3 or more -0.9 (3.1); after a chosen switch +0.7 (0.9) with the lookahead, +1.9 (0.9) for the static
    value. So the boost feature is calibrated and a switch tempo term would be worth at most about 2 points on the static value,
    mostly covered by the one-turn lookahead: no value change warranted. The remaining Protect gap and the sharper-than-expert mixes
    are unexplained by depth to two turns, spread knowledge, or the value of boosts and switches. `EVAL_MATRIX=1|full`: the payoff matrix on each output line (rows / cols / labels / final mixes /
    one-turn values and seed counts per cell, two-turn values under EVAL_HORIZON=2) for reading departures from the equilibrium against
    the opponent's actual move; "1" raises the rows and columns holding a slot's actual or most-weighted option to full seeds first.
  - **champ-battle-v19 = v18 + `MISS_DOUBLE=<side>` + lock-free interning** (2026-10-06, 3:00 am; flag off: 20 check battles identical
    to v16, `champ turn` exact). `MISS_DOUBLE=0` (side 0 = MYTEAM): on every accuracy roll by that side, the final hit chance p (base
    accuracy, stages, ModifyAccuracy and Accuracy events applied) is replaced by max(0, 2p - 100) just before the roll (sim.rs
    `roll_accuracy`, both the first-hit and the per-hit multiaccuracy sites); rolls the game already made certain (accuracy `true`: No
    Guard, Lock-On, rain Hurricane, Poison-type Toxic, always-hit moves) are untouched; secondary chances unchanged; a rule miss is an
    ordinary miss (Blunder Policy, crash damage); the planner's analytic accuracy in the race and the reduced option ranking use the same
    transform for that side. Requested by the user through Team search for a climb where the user's side misses twice as often ("I
    dislike missing"). Check (`MISS_STATS=1` prints rolls and misses per side and move after a battle run, planner rolls included): 100
    pool games with a Hurricane / Rock Slide / Sleep Powder team: Hurricane 68.6% -> 36.3%, Rock Slide 89.9 -> 79.5, Sleep Powder 73.1
    -> 49.1, Draco Meteor 89.7 -> 80.1, 100%-accuracy moves unchanged, side 1 unchanged; side 0's win share 24.2% -> 16.7% over 300
    games. Also: `dex::id()` keeps a per-thread copy of the strings a thread has seen, so the shared intern table and its mutex are hit
    only for new strings, and `single_event` no longer formats a string per call (`cbp`). Team search found one 90-thread process ran six
    times slower per game than 30 processes of 3 on the box; the intern mutex (taken on every `id()` call: `$move` relays, volatiles,
    statuses, part callbacks) was the cause. **Confirmed by Team search (Oct 6, 3:30 pm, c7a.24xlarge, 112 pool games):** v17 one
    process x 90 threads 24.2 s per game (2.98 s per turn) vs 2.60 s as 30 processes x 3; v20 one process x 90 threads 2.64 s, within
    4% of the small-process layout. Big multi-threaded processes are fine again from v19 on.
  - **champ-battle-v20 = v19 + the recharge-turn fix** (2026-10-06, 4:20 am). TR sheet found about 6% of pool games ending early with a
    fractional result (10% of games against Sylveon). Cause: Showdown's `recharge` is a pseudo-move, not a dex entry, so the data stub
    has no target; `slot_options` read it as "normal" and offered the recharging Pokemon a foe target, which `valid` rejected (the
    request says `self`), so that side had no legal joint action and battle4 handed the game to the value function. Fix: the option
    builder branches on the request's target class (as Showdown's chooseMove does), and labels show "Recharge" / the locked move on
    locked turns. Games without a recharge turn are unchanged (18 of 20 check battles identical to v16; the two with a Hyper Beam user
    now play on); 300 pool games: early fractional ends 1 -> 0 (the turn-25 stall cutoff remains by design). `champ turn` exact.
    `BATTLE_BREAK_DEBUG=1` prints why a game is handed to the value function before it ended.
  - **Which human lines does the sim misjudge? (`pssim/human_lines.py`, 2026-10-07, 11:15 am; the user asked for specific lines, not
    "multi-turn plays" in general.)** Data: Eval bar's accuracy set (560 cached ladder Bo3 games, 3,968 positions, one-turn planner at
    32 seeds with sym2, `evalbar/out/acc_eval_sym2.jsonl` + `acc_p1.jsonl` on its branch), 12,272 slot decisions where the human's play is
    known, outcomes from the logs. Each human play is classed by kind of line and situation; the test is the side's actual win rate
    against the planner's own rescaled rating of the chosen line (log-odds x 0.7538, the bar's weight), with the kind's agreed plays
    (weight >= 30%) as the baseline (a play is only known when the Pokemon got to act, so known-play sides win ~2 points more than rated).
    Results (results/human_lines.txt, `_r1250` for games rated 1250+):
    - *Protect is the one large, solid misjudgment.* Humans Protect 14.7% of decisions, the planner 10.7%; 47% of human Protects get under
      5% from it. Those 846 plays were rated 46.0 as a line (54.0 for the planner's pick) and won 53.7%: +7.7 ± 1.6 over the rating, +4.9
      net of the baseline (+7.1 net among 1250+ players). The planner says these Protects cost 8 points; they cost about 3. Where:
      turn-1 Protect (269 plays, planner weight 0.12, top pick 10%; disliked ones +9.9 ± 3.6; of 151 with the foe's play known, 101 were
      attacked that turn and 20 blocked a Fake Out: real turn-1 opponents are predictable, the equilibrium one is not), Protect under the
      foe's Trick Room (+14.2 ± 7.7, n 40) or Tailwind (+7.9 ± 7.9), Protect while the partner sets up (+14.9 ± 12, n 13). Not double
      Protect: the planner gives it 0.50 and rates it right (+0.5 ± 4.9) since DP2.
    - *Switches: the sim is right.* Disliked switches cost what it says (net -2.5 ± 2.5; into Intimidate, at low HP, giving up boosts all
      about 0). *Setup:* roughly neutral (net +3.5 ± 4): humans set up twice as often (3.3% vs 1.5%) and the disliked ones recover about
      half of the 6.5 points the planner charges, consistent with Eval bar's aftermath result (boosted positions rated right).
    - *Support lines the planner dislikes work:* Helping Hand under 5% won 55.6% vs 39.2 rated (+16.4 ± 6.3, n 45; net +20.7); Follow Me /
      Rage Powder among 1250+ players +18.7 ± 8.6 (n 22); Taunt / Encore / Haze / Perish +17.7 ± 8.7 (n 37); Tailwind the planner dislikes
      +9.6 ± 6.9 (n 47). Small samples, all the same direction: a turn spent enabling the partner is undercharged by the one-turn search.
    - *Value-function biases, independent of the line (agreed and disliked plays show the same edge, so the rating of the resulting
      position is off):* after a priority attack **+10** (n 205, 3 SE: Sucker Punch / Bullet Punch / Grassy Glide users are underrated;
      the race ignores priority); after speed control (Icy Wind / Snarl / Electroweb / Bulldoze) **+12** (n 97); after a pivot (U-turn /
      Parting Shot / Volt Switch) **-7** (n 251; -15 among 1250+: pivoting Incineroar overrated, the foe's -1/-1 is charged in full and
      switched off for free); screens **-13 ± 8** (n 62: 0.158 per turn plus the race already halving damage double-counts).
    - *Planner rating bias by the side's team style* (same positions, root value vs outcome, both sides; the regret-by-archetype check
      Eval bar was going to run): Sun **-6.8 ± 3.2**, Rain + Sun -11.5 ± 5.8 (Charizard + Whimsicott Sun -24 ± 8; Archaludon + Grimmsnarl +
      Pelipper -13 ± 6), Rain -1.6 ± 3.7, Balance -1.5, Tailwind -0.6, Sand +3, Indeedee TR +3 to +5, Snow **+5.9 ± 4.0** (Froslass +
      Kingambit + Rillaboom +14.5 ± 6.4), Trick Room +7.7 ± 5.7, Perish +15 (the planner cannot play the trap). So the Rain/Sun-vs-Snow/TR
      gap Team search sees in self-play is already there in how the planner rates real positions: it is partly the value (priority,
      speed control, screens, pivots), not only play.
    - Horizon 2 on the 602-decision subset moves the planner toward humans on setup (weight 0.16 -> 0.30, top pick 13% -> 30%),
      Protect (regret 5.4 -> 4.4) and redirection (4.4 -> 3.0); switches and attacks unchanged.
    Next (not started): refit the value on real positions with features for own priority damage, foe speed stages, and refitted screen /
    pivot weights (Eval bar's 3,968 positions carry the feature vectors); let the race order priority moves first; then re-run the pool
    bar by group. Turn-1 Protect is mostly a read on predictable human turn-1 play and does not matter for self-play.
  - **champ-battle-v21 (2026-10-07, built 12:30 pm; all new behaviour behind flags; flags off: `champ turn` exact on the 6,900 positions,
    the 20 check battles identical to v20 with the full setup).** From the human-lines study above:
    - `RACE_PRIO=1`: the damage race orders priority moves first (Grassy Glide only in Grassy Terrain; a priority move is dropped against a
      grounded target under Psychic Terrain and against a side with Armor Tail / Dazzling / Queenly Majesty), each unit's turn order
      coming from its best option's priority at the start of the race turn; and the race calc knows Supreme Overlord (the ability
      state's fallen count; calc.rs `Mon.fallen`; the 20,000 Showdown damage cases stay 99.9% exact, they have no fallen allies).
    - `FEATS21=1` (needs RACE=1): five features after the two race edges, so the vector has 25: priority edge (RACE_PRIO; the best
      priority hit each side has on the field as an HP share, summed over its actives), Speed stages of the actives, stat drops of the
      actives (the negative part of the boost feature), weather turns left x who benefits (per active +1 / -1 / sand chip -0.5), Taunted
      actives. A 20-weight value file ignores them (`value()` uses `w.len().min(f.len())`).
    - `champ feats <engine_data> <positions.jsonl> <out.jsonl> [threads]`: the feature vector and static value per position, no lookahead
      (27,000 positions in about a second); `pssim/build_egvalue10.py` fits a symmetric value on them.
    - `BATTLE_HORIZON=2` (+ `BATTLE_HORIZON_SIDE=0|1`, `BATTLE_H2_SEEDS` 1, `BATTLE_H2_MARGIN` 0.05, `BATTLE_H2_TOP` 6): the evalpos two-turn
      horizon in real games: after the one-turn solve, the heaviest / closest options of each side (at most 6 x 6 cells per round, two
      rounds) are valued after one more turn (battle4 `next_value`) and the flagged sides re-solve their mixes on those values. Costs
      about 2.6x per game (2.1 -> 5.6 s per pool game on one thread with sym2); without the cap (every option within 0.15) it was 30x.
    **Refit on real positions (`build_egvalue10.py`, results/egvalue10_fit.json; the file egvalue10 is NOT adopted):** every turn of
    the 3,970 cached Bo3 games outside Eval bar's 560 held-out games (26,876 positions, built with Eval bar's position builder, hindsight
    sets) with the 25 features. Held-out static log loss (560 games, rescaled): sym2 as is 0.5551, the 20 features refitted 0.5537, the 25
    refitted 0.5567 (SE 0.017): no gain. The new features take sensible weights (priority +0.15, speed stages +0.14, drops -0.25, Taunt
    -0.20, weather +0.03) but the refit also moves old ones a lot (Protected last turn -0.48 -> -0.03, Trick Room turns 0.20 -> 0.08, type
    edge 0.08 -> 0.44, race KO 0.47 -> 0.26) and the held-out team-style bias does not move (Sun -7, Trick Room +7, Snow +5). On the
    27,000 fit positions the style bias of the static value is small: Rain -4.2 ± 1.4, Sun -2.0 (none / sun up) but -12 / -17 when a Sun
    side sits under sand / snow, Trick Room sides +4.3 ± 2.9 with Trick Room up and -1.4 with it down, Snow +0.5, faster sides +1.3 /
    slower -1.3 (SE 0.5). Reading: the value's style bias on real positions is a few points, mostly weather-war and speed; the 8-10 point
    self-play gap Team search measured must come mostly from play (Protect, support lines), which the horizon test below addresses.
    **Horizon head-to-head, local (240 mixed-style pool-vs-pool games, `pssim/h2test.py`, sym2, 3 threads):** the side with the horizon
    gained +2.3 ± 4.0 points as side 0 and +0.8 ± 4.0 as side 1 (146 of 240 results unchanged each time); by side 0's style the signs
    follow the hypothesis (Trick Room +20 ± 12, Tailwind +13 ± 12, Sun -13 ± 10) but at n 30 per style nothing is significant. The
    2,400-game version (`h2test.py jobs`, 30 teams per style x 10 opponents) is handed to Team search for the cloud box, three runs (A, B,
    C) of the same starts; `h2test.py report <A> <B> <C>` reads them.
    **Protect-tax head-to-head (same 2,400 starts, 7 threads, 1:00 pm):** sym2's "Protected last turn" weight is -0.477 (a ~12-point charge
    on every successful Protect, fitted on self-play endgames; the real-position refit gives -0.03). A side planning with -0.10 instead
    (EG_VALUE_B) changed a third of the games and gained +0.2 ± 1.1 as side 0, +0.9 ± 1.1 as side 1, pooled **+0.6 ± 0.8**: flat. The
    planner's reluctance to Protect is not a value-weight problem in self-play.
    **Self-play by team style vs rating-matched real rates (the baseline run A of the 2,400 starts, side 0 = a pool team of that style vs a
    random pool side, sym2):** sim win rate vs the field and the real ladder rate of the style in the 1200-1350 band: Rain **57.2 vs 48.0
    (+9)**, Tailwind 50.6 vs 45.6 (+5), Sun 52.0 vs 50.0 (+2), Snow 51.5 vs 49.6 (+2), Sand 49.4 vs 51.0 (-2), Indeedee TR 50.8 vs 53.8
    (-3), Balance 49.0 vs 52.9 (-4), Trick Room **47.3 vs 52.9 (-6)**; SE about 3 on the sim side. So after matching ratings only Rain
    stands out as overrated in self-play (2 SE) and Trick Room as underrated (1.5 SE); Sun is fine. Note for Team search's comparison: real
    archetype rates carry who plays them: Rain sides average rating 1183 against ~1240 for the rest (Rain wins 34% below 1200, 48% in
    1200-1350), Snow wins 68% below 1200 and 50% in 1200-1350, so overall real rates understate Rain and overstate Snow by 3-4 points.
    Matchup cells (n 15-60) are too noisy to localise Rain's +9; the 36 Rain / Trick Room vs "Snow" games show the Snow tag is the six's
    core, the fours brought are mostly Kingambit / Rillaboom / Sneasler / Basculegion. Unsupported mechanics are hit in 62 of 2,400 games
    (Air Balloon, Static, Metal Burst, Quick Claw...), not a factor.
    **Horizon head-to-head, 2,400 games (done locally 12:00-1:30 pm, 3-9 threads; Team search's box run is not needed):** the side with
    the two-turn horizon gained **+0.2 ± 1.2 as side 0 and +0.3 ± 1.2 as side 1, pooled +0.2 ± 0.9 over 4,800 games**; 1,524 / 1,519 of
    2,400 results unchanged; no style gains (Rain +5 ± 3.5 both times, Trick Room -0.7 / +0.7, Indeedee TR -5 / -2, Tailwind -0.3 / -3).
    So BATTLE_HORIZON=2 as built (reduced second turn, one seed, 6x6 cells, 1.4-1.7x cost) does not play stronger and does not go into
    the climb setup. Three evaluator changes aimed at the "sequencing" reading are now flat in self-play (value refit, Protect tax,
    two-turn horizon); what remains measurable is Rain +9 / Trick Room -6 vs rating-matched ladder rates (vs regional top-cut rates:
    Rain 49.6%, Trick Room 58-60%, so about +7 / -10 against competent play), and the by-archetype human-lines split says where: Trick
    Room players' disliked plays work when Trick Room is DOWN (+6.6, n 170; +2.5 with it up), above all switches (+17.6 ± 9.3, n 27),
    setup (+21 ± 12, n 15: Milotic Coil, whose Def / accuracy boosts the value does not see) and priority (+15 ± 9); Rain players'
    disliked plays lose as the planner says (status -23, setup -18, pivots -32, Fake Out -36) - but only below rating 1200 (-12 ± 6, n
    141); at 1200-1350 Rain players' disliked plays beat the planner's rating by +13 ± 8 (n 100), more than other players' (+4), and the
    sim's Rain +9 holds against the 1200-1350 band (48%), 1350+ (46%) and regional (49.6%) rates alike, so it is not Rain pilots being
    bad (the user pushed back on that reading, rightly). Low-rated Rain mistakes the data flags (n 9-29 each): Pelipper Hurricane / Weather
    Ball when Tailwind is the move, Incineroar Will-O-Wisp or Throat Chop instead of Fake Out / pivoting, Kommo-o Protect instead of
    Clanging Scales, Raichu-Mega Focus Blast over Zap Cannon, Grimmsnarl Foul Play instead of screens. Rain lines the planner dislikes that
    work: Pelipper Protect (+26) and Tailwind when the planner wants to attack (+27), Archaludon Protect (+16), Golisopod Protect (+20). Next lead (not started): a "plan potential" term for the Trick Room-down phase (a living Trick Room user on the slower
    side, Tailwind likewise) fitted on the real positions and tested with the same 2,400 starts (Trick Room teams as side 0), and the
    one-layer switch model (each side assumes the other stays in), since switching is where Trick Room players gain most.
  - **Plan potential, bench edge, full switch matrix: all flat or worse in self-play; and the style bias moves to brings and leads
    (2026-10-07, 1:30-2:20 pm).** `FEATS22=1` adds Trick Room potential (a living Trick Room user on the slower side while Trick Room is
    down or on its last turn, x tanh(speed edge) x its HP share), Tailwind potential and a bench edge (the best hit each side's bench has
    on the other's actives; `bench_edge`, sharing the race's memoised calc through `race_damage`). The real-position fit gives Trick Room
    potential **-0.20** (negative), Tailwind potential 0, bench edge +0.24. Head-to-heads on the 2,400 starts (side 0 with the variant
    value, side 1 sym2): Trick Room potential +0.3: **-1.1 ± 0.5** overall, Trick Room teams -0.3 ± 2.0, Indeedee TR -2.5 ± 1.9 (the fit
    was right: valuing an unset Trick Room hurts); with bench edge +0.24 as well -0.5 ± 0.9; bench alone: see results below.
    `BATTLE_FULLSW=0|1|both` (one full matrix game, both sides' switches in both matrices; costs only the switch x switch cells more)
    and `BATTLE_ANTICIPATE=2|3` (more anticipation passes): full matrix for one side +0.3 ± 0.9 / -0.0 ± 0.9 (450 of 2,400 games change,
    no gain); the one-layer model with one anticipation pass is as good.
    **Real pairings (`pssim/replay_report`-style, 2,094 cached games with both brings seen and both players rated 1150+, the sim playing
    each game from its actual leads and brings on both sides, sym2):** sim winner = real winner 54.4% (52.9% at 1150-1250, 59.6% at
    1350+). Sim minus real win rate by style, both sides pooled: Rain **-0.3 ± 4.1**, Sun -0.1 ± 2.9, Trick Room **-3.2 ± 4.2**, Indeedee TR
    **-6.6 ± 3.5**, Tailwind **+8.3 ± 2.5**, Snow +3.5 ± 4.0, Balance **-5.0 ± 2.7**, Sand -1.3 ± 3.9, Perish -8.1 ± 4.4 (the trap), Rain +
    Sun **+10.9 ± 5.2**. So with the humans' own leads and brings the planner plays Rain and Trick Room about right; the Rain +9 / Trick
    Room -6 of the pool-vs-pool test came from pairing a team's bring (tailored to the opponent it really faced) with a random opponent,
    which costs bring-sensitive styles (Trick Room) and spares Rain. Two consequences: (1) the climb's own lead / bring choice is where
    Trick Room packages most likely lose their value (ask Team search how the climb picks the four and leads for a Trick Room six), and
    (2) the planner's remaining play bias is Tailwind / Rain + Sun over (set Tailwind, attack) and Indeedee TR / Balance under (Follow Me,
    Fake Out, pivots: the support and positioning lines human_lines.py found undercharged). Symmetric value variants are being scored on
    this set by the by-style bias rather than by head-to-head strength (results below when in).
    **Symmetric value variants scored on the real pairings (2:40 pm):** sym2 as is: agreement with the real winner 54.4%, bias RMS over
    the nine non-Perish styles 5.6 points. The 28-feature real-position refit (egvalue10b, with RACE_PRIO): agreement **56.5%**, Balance
    -5.0 -> +1.1, Tailwind +8.3 -> +6.4, Rain + Sun +10.9 -> +7.4, but Trick Room -3.2 -> -7.2, Snow +3.5 -> +7.3; RMS 5.5. sym2 with
    Tailwind turns 0.11 and stat drops discounted by 0.12 (`sym2_tw_drops`): agreement **57.0%**, Balance -3.5, Tailwind +7.8, Sand -5.5;
    RMS 5.6. So the values move the bias around without shrinking it, while tracking the real games slightly better (agreement SE ~1.1).
    Bench edge alone as a side-0 value: +0.1 ± 0.8 (flat). Nothing adopted; the planner is at a local optimum for every knob tried today.
    **Team search's answer on the climb's bring step (2:45 pm): it leaks.** The climb's bring model (bring/fit_outcome.py: a ridge fit on
    Oct 3 to 11.5k champ-battle-v2 games vs the old archetype models; features: human log-prob, coverage, lead offense / defense / offense,
    a two-Mega penalty, nothing for enabling a plan) ranks (lead pair, back pair) per opponent core group, the top 3 are screened with 2
    games each, the best is fixed for the confirm games. For Brisbane-12's start vs real Torkoal + Trick Room sides: setter leads 29% (real
    players 65%), Torkoal brought 39% (63%), setter + Torkoal 39% (61%); the model's top choice leads a setter against 14% of the meta, its
    top 3 against 54%, and the 2-game screen keeps setter + Torkoal against 39% though it is in the top 3 against 100%. Team search added
    `TS_SYN_BRINGS=human` (the imitation model's most human-like bring and leads, no screen) and runs the synergy check both ways on the
    next box. Reading: the Trick Room package loses its value at team preview, not on the field; the engine plays it about right once the
    right four lead. Open design point for the user: the planner's opponent is the equilibrium mix, so read-based lines (Follow Me, Fake
    Out into the obvious target, pivots) are worth less in self-play than against humans, and unexploitable styles (Tailwind-and-attack)
    more; that is the shape of the remaining Tailwind +8 / Indeedee TR -7 / Balance -5 bias, and no value or depth change fixes it.
  - **Synergy check, human-brings way (Team search, 2026-10-07, 8:50 pm; its log and JSON in teamsearch/cloud_results/synergy/):** 87
    plan breaks (the plan's enabler swapped for a generalist) cost -1.7 on average vs -0.0 for control swaps; by plan, breaks vs controls:
    Sun -5.6 (n 18) vs -0.1, Tailwind -4.1 (20) vs -0.7, Rain -3.5 (15) vs +2.6, Psychic Terrain -0.6 (9) vs -0.9, Sand +2.6 (9) vs -0.1,
    Trick Room +4.4 (16) vs -0.7. So with human-typical brings the engine values Sun / Tailwind / Rain plans at 4-6 points over an
    ordinary swap and does not value Sand or Psychic Terrain setters. The Trick Room line is not evidence: the user's six gives +24 ± 2.6
    for removing Indeedee-F because the imitation model's brings leave Torkoal home with Indeedee-F and bring it without (the Oct 3
    finding again: imitation picks -24 vs the sheet's for this team); the three Sinistcha teams are goodstuff with a back-line Trick
    Room; the two fast Indeedee Trick Room teams do value their setter (Baltimore-04 -5.3 / -3.8 / -8.6). Significant pro-break cases are
    all "into Scarf Garchomp". The climb-brings way runs next (due about 10:20 pm); the comparison says whether the plans' value survives
    the climb's bring search.
  - **Synergy check, both ways (Team search, 2026-10-07, 10:30 pm; teamsearch/synergy_v20g_{human,search}.json):** leaving out the user's
    six (imitation artifact), plan breaks cost -2.6 with human brings and -2.3 with the climb's bring search (n 84); controls -0.2 / -0.9
    (n 29). Breaks minus controls, human / climb: Sun -5.5 / -5.7 (valued both ways), Rain -6.1 / -1.2 and Tailwind -3.4 / +0.1 (valued
    only with human brings: the climb's bring step loses those plans), Psychic Terrain +0.3 / -3.0, Sand +2.7 / +0.4, Trick Room +2.0 /
    +1.3 (13 teams, mostly Delphox goodstuff with a never-led Sinistcha plus two fast Indeedee teams: a weak test). The user's six with the
    climb's brings: Indeedee-F -> Garchomp -5.9 ± 2.6, -> Gholdengo +2.9 ± 1.1, -> Rillaboom -1.4 ± 2.1; control Incineroar -> Gholdengo
    -4.2. Reading (both threads): the bring step explains the Rain / Tailwind gap, but under either bring method a plan enabler is worth
    only ~2 points over an ordinary swap and a Trick Room setter nothing, so the climb treats enabler -> generalist swaps as nearly free
    and selection on noise does the rest. The clean Trick Room test still owed: the user's six with the sheet's own lead / bring plans
    (72.5% vs the fitted model's 60.1% in the sim on Oct 3), with and without Indeedee-F; Team search is setting it up on the box.
  - **The Trick Room six with the sheet's own plans (Team search, 2026-10-07, ~11:30 pm; teamsearch/trsix_sheet.py, trsix_sheet_v20g.json):
    the whole Trick Room story is brings.** v20g, pool opponents, 4 x 224 games per version, plans from sheets/trick-room-six/picks.json
    (all 28 groups). The sheet's plans never bring Indeedee-F; Farigiraf is the setter (led vs 82% of the meta, brought vs 95%), Torkoal
    brought vs 84%. The team as is: 70.3 with the sheet's plans, 61.9 with the climb's bring search, 42.9 with human-typical brings (±3).
    Plan fixed, Pokemon swapped into the outgoing one's slot: Farigiraf -> Gholdengo -28.5 ± 2.8, -> Garchomp -25.1 ± 2.7, -> Rillaboom
    -30.3 ± 2.7 (an upper bound: the generalist plays the setter's slot); Torkoal -> Gholdengo -6.8, -> Garchomp -7.4; Incineroar ->
    Gholdengo -8.8 (a plan piece too, led vs 39%). The setter's loss is largest against Indeedee TR (-40 to -57), Snow (-44 to -56),
    Tailwind goodstuff (-45 to -66) and Sun (-54). With the climb's re-planned brings the same swaps were -5.9 / +2.9 / -1.4. So from good
    leads the engine values Trick Room hugely and plays it fine; the climb's bring step loses about 8 points of this team against the
    sheet's plans, enough to make the setter look nearly free to the climb. **No engine-side Trick Room work is needed**; the fix is the
    climb's bring step (plan-aware shortlist candidates, a bigger screen, or the sheet's both-sides solver where affordable: Team search
    and TR sheet).
  - **Team search's plan-aware bring step (2026-10-08, ~12:10 am; teamsearch/bringplan.py, `TS_BRING_MODE=plan`), built, not yet validated
    in battles:** per group a shortlist of up to 7 brings (the outcome model's top 2, the imitation model's top 1, the most common bring of
    real players with similar sixes, and one candidate per plan the six has: one per Trick Room setter plus setter + Fake Out / redirection
    guard, weather, terrain, Tailwind, support + setup), screened 7 x 2 games then the best 2 x 6 more (728 games per team, old 168); run
    dirs hashed by their jobs. Offline: the sheet's exact plan is in the shortlist against 42% of the meta (old 30%), its four against
    65% (50%); Brisbane-12 gets a setter-lead candidate against 100% (54%). Validation (cloud/bring_validate.sh: bringcheck.py old vs
    plan-aware brings, paired, on the synergy teams and the Trick Room six against its sheet plans, then the synergy check with plan-aware
    brings) goes on the next box, about 3 h. Nothing is owed from the engine for it.
  - **Plan-aware bring step, validation part 1 (Team search, 2026-10-08; teamsearch/bringcheck_v20g.json):** plan-aware minus old brings on
    the synergy check's 30 teams, 4 paired batches x 224 pool games: mean +1.0 (17 better, 3 significantly, none significantly worse); by
    plan Rain +4.0 (Brisbane-09 +10.8 ± 2.8, Frankfurt-14 +7.6, Frankfurt-11 +6.3; Brisbane-06 -5.6), Sun +1.4, Sand +1.2, Tailwind 0.0,
    Trick Room 0.0, Psychic Terrain -0.6. Chosen brings came from the outcome model 54%, imitation 12%, similar real sixes 12%, plan
    candidates 22%. The Trick Room six against its sheet's plans on the same entries (sheet 68.5): old brings -10.2 ± 2.7, plan-aware
    -6.8 ± 2.1, so the step recovers a third of that team's bring gap; the rest needs the sheet's plan in the shortlist more often (42% of
    the meta now) or a less noisy screen than 8 games. Part 2 (the synergy check with plan-aware brings) runs on the next box. Longer term
    the shortlist's ranking model wants a refit with plan features on pool-mode games (Team search's area).
  - **Plan-aware bring step, validation part 2 (Team search, 2026-10-08; teamsearch/synergy_v20g_plan.json):** the synergy check rerun with
    plan-aware brings. Breaks minus controls without the Trick Room six, human-typical / old search / plan-aware: overall -2.4 / -1.4 /
    -2.3; Rain -6.1 / -1.1 / -4.6; Sun -5.5 / -5.6 / -6.3; Sand +2.7 / +0.3 / -2.2; Tailwind -3.4 / 0.0 / -1.4; Psychic Terrain +0.3 /
    -3.0 / -0.7; Trick Room +2.0 / +1.4 / +2.6 (still a weak test: Sinistcha goodstuff, and the six's enabler as picked is Indeedee-F,
    which its sheet never brings; trsix_sheet.py is the Trick Room result). So the plan-aware step restores most of the Rain plan value the
    old step lost and adds some for Sand and Tailwind. A per-archetype climb (Rain, Rain + Sun, Balance, Sand, Tailwind; 32 regional
    starts; swaps keep the start's archetype; opponents half regional / half ladder; plan-aware brings; hold batch; archverify.py at the
    end) is running on the Spain box at the user's request (cloud/run_env_arch.sh).
  - **champ-battle-v22 = v21 + ported mechanics the card opponents hit (2026-10-09, 1:30 pm; flags off = v20's games on the 20 check battles,
    `champ turn` exact on all 6,900 base cases).** Frankfurt-156 sheet found 1.1% of its 42,000 card games flagged unsupported (Purifying
    Salt in every game of the Garganacl + Hawlucha card, Mummy in 217 games of a Cofagrigus back row, slotCondition). Ported, each checked
    Showdown-exact on new focused cases: abilities Purifying Salt, Mummy, Static, Snow Cloak, Own Tempo, Quick Draw, Surge Surfer, Dry
    Skin, Zero to Hero (Palafin-Hero on switch-out); items Air Balloon (the pop), Quick Claw, Chesto and Rawst Berry, the five missing
    resist berries (Rindo, Wacan, Yache, Shuca, Payapa), Metal Coat / Hard Stone / Poison Barb / Silver Powder, Light Ball; moves Metal Burst
    (last foe that hit the user this turn), Mortal Spin, Hex, Rest, Salt Cure's residual (Champions halves it: 1/8 Water / Steel, 1/16
    otherwise), and slot conditions (sim.rs `add_slot_condition` / `remove_slot_condition`, handlers run for whoever is in the slot): Wish
    and Healing Wish. Two engine bugs found on the way: (1) the ifHit self-destruct compared against "ifHit" while the data holds "ifhit",
    so Healing Wish and Memento users never fainted (both were kept out of the planner's options for that; now in); (2) an old stub
    `h!(..., "zerotohero", "onSwitchOut", Undef)` later in register() shadowed the port (check for stubs before adding a handler: `grep
    '"<id>", "on' handlers/*.rs`). Test cases: `gen_turn_cases.js` gained `FOCUS_POOL=<sets.json>` (extra sets) and `FOCUS=<ids>` (every
    team gets one matching set); `native/focus_sets_f{1,2}.json` are the ladder sets from opp_pool.json with the mechanics above and
    `native/turn_cases_f{1,2}.jsonl` (1,200 + 800 four-member cases, git-ignored like the other case files; `champ turn
    ../engine_data_full.json ../turn_cases_f1.jsonl lo,hi,mid,real`) are 100% exact with 32 / 43 cases still unsupported: Shell Side Arm
    (14), Sleep Talk (22), Smack Down (7), Counter, Beat Up, Ally Switch, Baton Pass, Spikes, Alluring Voice's secondary, Wandering Spirit.
    `native/champ/bin/champ-battle-v22` (sha 3ba3ee45..., source `src_battle_v22.tar.gz`); the full-data file is unchanged.
  - **champ-battle-v23 = v22 + Eval bar's and TR sheet's unsupported lists (2026-10-09, 3:30 pm; flags off = v20's games on the 20 check
    battles; all 6,900 base cases and the 3,200 focused cases f1-f3 exact).** Ported, each Showdown-exact on new focused cases
    (`native/turn_cases_f3.jsonl`, 1,200 cases from `focus_sets_f3.json`): **Baton Pass** (sim.rs `copy_volatile_from`: boosts and the
    volatiles without noCopy move to the switch-in; it was 7% of Eval bar's day-1 broadcast positions, Espathra), **Encore's override**
    (run_move now swaps in the move the OverrideAction event names, as Showdown's runMove does), **Ally Switch** (sim.rs `swap_position`,
    the allyswitch counter condition), **Gravity** (accuracy x 6840/4096, grounded moves disabled, flying moves cancelled), **Curse** as
    Champions rewrites it (mods/champions/moves.js: no volatileStatus on the move; the Ghost version pays half HP and applies the curse in
    onHit, a random foe when it targeted an ally; the non-Ghost version boosts in onHit), Entrainment, Temper Flare, Shell Side Arm
    (category by the unboosted-stat comparison, contact added when physical), Vital Spirit and Insomnia, Healer, Gooey, Curious Medicine,
    Seed Sower, Swarm, Electromorphosis with the Charge condition, Ripen. Not ported: Unseen Fist (Champions uses an onHitProtect hook
    with a 0.25x damage path in the mod's getDamage: needs the Protect condition and the damage path changed; 8 of Eval bar's positions),
    Cute Charm (needs genders, which the engine state does not carry). Still unsupported in the f3 cases: Opportunist, Motor Drive,
    Pickup, Iron Ball, Harvest, Zoom Lens, Flying Press, Skill Link's onModifyMove, Speed Swap, Plus, Gyro Ball, Instruct, Sleep Talk,
    Beat Up, Future Sight (2-7 cases each). Caution learned: `register()` already held stubs for some abilities (zerotohero's
    `onSwitchOut` returned Undef) and a second registration later in the function silently replaces an earlier one, so grep for an id
    before adding a handler. `native/champ/bin/champ-battle-v23` (two-line sha file, as v20's: binary and `src_battle_v23.tar.gz`).
  - **Sweep after the Healing Wish bug (the user asked, 2026-10-09, 5:30 pm): is there anything else like it?** The bug had three parts:
    the move was excluded from the planner by name, the engine's self-KO was a silent no-op (a typo, not an "unsupported" flag), and the
    turn tests never used the move because their case generator draws sets from the regional / model pools, not from the user's team.
    Checks run, all in one afternoon: (1) **the Trick Room six, exhaustively**: 2,700 Showdown-exact cases with one of the six in every
    battle (`gen_turn_cases.js` FOCUS mode from `native/focus_sets_team.json`; `turn_cases_t1.jsonl` all six, `t2` Blastoise / Torkoal /
    Indeedee-F; git-ignored like the other case files), every one of the 24 moves used at least 15 times in the logs (Healing Wish 15,
    Aura Sphere 18, Water Spout 33, Eruption 50, the rest hundreds), the Mega, Psychic Seed, Drought, Psychic Surge, Armor Tail, Defiant,
    Sitrus, Chople and White Herb all seen: **100% exact**; every callback the data lists for the six's moves, abilities and items has a
    handler. (2) **stub handlers repo-wide**: 91 registrations whose body is `RV::Undef`, each compared with Showdown's callback: all
    message-only or Champions-irrelevant (Dynamax / Z / Terastal / Persistent / gen <= 5 / Illusion); Perish Song's faint lives in onEnd.
    (3) **literal comparisons against data fields** (selfdestruct, selfSwitch, target, category, status, type, terrain): the "ifHit" case
    was the only one. (4) **the planner's name-based rules**: Fake Out after turn 1, Protect with a Choice item, re-clicking Trick Room,
    and the feature lookups: all intended. (5) **export completeness**: every callback on Showdown's move / ability / item objects
    (nested self / secondary ones included, which the export marks `__fn`) is in the engine data. Nothing else of the Healing Wish kind
    was found. Standing gap, now documented: a mechanic that is neither ported nor on a set the case generator draws is invisible to
    the tests; the FOCUS generator closes it per team (`FOCUS_POOL=<the team's sets> FOCUS=<its species>`), so a new sheet's team should
    get a focused batch before its matrix run.
    **Healing Wish stays free in the planner.** The restriction tried for v24 (only a hurt user or hurt bench) is now opt-in
    (`EG_SELFKO_RULE=1`): the user's read is that a full-HP Healing Wish is often a real line (the setter leaves for free once Trick Room
    is up, the replacement comes in without taking a hit), and the free version scored higher in the 320 matrix games (46.6% vs 45.3%,
    v20 43.1%). So v23 is the version for the kit; no v24. TR sheet replays the results whose fours carry Healing Wish / Memento
    (`kit.py <team> flagged --moves healingwish,memento --write`), on both sides: the Camerupt + Farigiraf card's Indeedee-F and
    Sinistcha carry them.
  - **Focused case batches for the other sheets' sixes (2026-10-09, 7:00 pm, asked by TR sheet's rule):** Frankfurt-239 (Pelipper,
    M-Swampert, Archaludon, Indeedee-F, M-Metagross, Grimmsnarl): 1,500 + 800 cases (`native/turn_cases_f239{,b}.jsonl` from
    `focus_sets_frankfurt-239.json`), **100% exact**; Electro Shot 231 uses, Hurricane 138, Weather Ball 149, Steel Roller 115, Stomping
    Tantrum 91, Wave Crash 234, Parting Shot 110, Wide Guard 50, both Megas hundreds of times. Frankfurt-156 (Basculegion, Pelipper,
    Garchomp Z, Archaludon, Farigiraf, Golisopod): 1,500 + 800 (`turn_cases_f156{,b}.jsonl`), **100% exact**; Last Respects 220, Aqua
    Jet 240, Emergency Exit 31, Scarf Flip Turn 53, Twin Beam 22, both Megas hundreds. The only unsupported hits were opponents' Big
    Pecks, Wandering Spirit and Future Sight (one case each). Recipe for a new sheet: write its six as `focus_sets_<slug>.json`
    (species, item, ability, moves, nature), then from pssim/ `FOCUS_POOL=<that file> FOCUS=<its species ids> TEAM=4 node
    ../native/gen_turn_cases.js 1500 <out.jsonl> <seed>` and `champ turn ../engine_data_full.json <out.jsonl> lo,hi,mid,real`.
  - **champ-battle-v24 = v23 + Mega choice (the user, 2026-10-10, through TR sheet: "always mega evolving feels wrong in general";
    cut 10:20 am).** plan.rs `slot_options` offers every move of a stone holder with and without the Mega Evolution (joint options
    deduplicated; one Mega per side per turn as before; DP2 / horizon reduced sets still take the Mega); `EG_MEGA_ALWAYS=1` restores the
    old rule for both sides (then v24 = v23 exactly: the 20 check battles identical), `s0` / `s1` for one side. The value does not see an
    unused stone (an un-evolved holder is valued as its base forme), so the planner holds the Mega only when the one-turn playout makes
    the base form better now, or gives it to the partner because this turn's cells say so. Measured on the 2,400 pool-vs-pool starts
    (sym2): strength flat, the choosing side +0.3 ± 0.6 / +0.1 ± 0.6; of 4,323 stone holders on the choosing side (both runs) 17%
    delayed the Mega (median 2 turns) and 5% never evolved (the partner took it 1%, left the field first 3%, stayed in un-evolved
    0.9%); about the same for every Mega (Raichu 20% / 5%, Garchomp 22% / 5%, Salamence 12% / 5%, Staraptor 18% / 6%, Swampert 12% /
    2%, Metagross 16% / 2%, Blastoise 6% / 6%; a first tally that also counted Mega targets read 35% / 24% and was corrected); so no
    "Mega later" feature for now. Results differ from the always-Mega run in 9% of games with one side choosing (0.4% of games with no
    stone on that side, 8.8% with one holder, 39% with two), noise around an unchanged mean except on two-stone fours. Cost: about +20% per game while a stone is
    unused (the Trick Room six's 20 check battles 1.5 -> 2.6 s per game with opposing stones in play). Effects: two-stone teams
    (Frankfurt-239's Swampert / Metagross, Frankfurt-156's Garchomp / Golisopod) now pick which holder evolves per game; base Raichu can
    keep Lightning Rod; the Trick Room six changes little (Blastoise delayed its Mega in 6 of 20 check games). TR sheet makes t1sim.js
    consistent (no-Mega options in the turn-one step).
  - **champ-battle-v25 = v24 + the Mega tie-break and the grid-name fix (2026-10-10, 1:10 pm; TR sheet's read of the delays).** The user
    expected at most ~10% of holders to delay; the honest count (switch turns are not delays, a Pokemon cannot switch and evolve) was
    12.8% of holders using a move without the Mega first, and most of those turns were near-ties (Protect, Fake Out, field moves: the
    turn's result does not depend on the Mega's stats, the race after it differs by thousandths, and the fictitious-play mix splits).
    battle4 now moves a no-Mega option's weight to its Mega twin when the twin is worth at least as much against the other side's mix
    minus `EG_MEGA_TIE` (default 0.002; 0 turns it off): on 800 starts with side 0 choosing, delays 13.8% -> 8.3% of holders, results
    unchanged in strength (+0.8 over 800 games vs always-Mega), and the remaining un-evolved attack turns are mostly real base-form
    reasons (Golisopod keeping Emergency Exit 15 of ~40, Garchomp keeping Rough Skin against contact, Charizard). plan.rs `gname` maps an
    un-evolved holder to the grid's base entry when the grid has one (it read as the M- entry before, right under the always-Mega rule;
    `EG_MEGA_ALWAYS` for that side keeps the old mapping). With `EG_MEGA_ALWAYS=1 EG_MEGA_TIE=0` the 20 check battles are identical to
    v20. `native/champ/bin/champ-battle-v25` (two-line sha file).
    **Human baseline and the tie-break's default (TR sheet, 2026-10-10, 1:40 pm; sheets/trick-room-six/work/human_mega.py on the 4,555
    sheeted replays, same counting: move turns only, while the side's Mega was unused):** of 8,218 stone holders, 78.6% evolved on
    their first move turn, 15.6% delayed, 2.6% never because the partner took it, 3.2% never with the Mega unused: players hold the Mega
    on about 21% of holders, the same above and below the median rating; the un-evolved human turns were Protect 1,297, attacks 842,
    Fake Out 195, field moves 117, flinch / sleep 99; by species Raichu 23%, Tyranitar 24% (+15% partner), Metagross 22%, Garchomp 21%,
    Charizard 18%, Salamence 16%, Staraptor 14%, Golisopod 9%, Swampert 10%, Blastoise 5%. The planner holds it less (12.8%) and the
    tie-break pushes it further from play (8.3%), mostly on the Protect turns where players hold it most, so **the recommended setting
    is EG_MEGA_TIE=0** (the kit's v25 setup sets it; strength is flat either way). The audit of the remaining un-evolved attacking turns
    (`BATTLE_MEGA_AUDIT=<jsonl>` on any battle run: per turn both outcomes against the sampled reply over 8 seeds, abilities / types of
    both formes, the twin options' values; pssim/results/mega_audit.jsonl, 60 records from 800 starts) shows every one with the no-Mega
    option valued 0.5-45 points higher: base-form reasons such as Golisopod keeping Bug / Water against Flamethrower (14-23 damage
    base, 111-135 as the Steel Mega) and Garchomp keeping Rough Skin + Ground; TR sheet sorts them for the user.
  - **Bench-aware race (`RACE_BENCH=1|s0|s1`, in the source after v25, 2026-10-10, 3:30 pm): built, measured, not adopted.** The race's
    bench blind spot (a foe about to die on the field read better than that foe dead and replaced; the Greninja case in TR sheet's Mega
    audit) is real, so plan.rs `race_feats` gained a variant where each side's living bench Pokemon (healthiest first) are units that
    enter when one of their side's units falls, and `value2` can give each side its own variant. Head-to-head on the 2,400 pool starts
    (sym2): the bench-aware side **-0.9 ± 1.2 as side 0, +0.7 ± 1.2 as side 1** (flat; a third of the games change); the Mega audit with it
    on: 71 un-evolved attacking turns instead of 92, "the Mega KOs more yet base preferred" 8 cases. And it hardly changes finishing
    decisions: in 400 logged games, of 52 turns with a foe at 20% HP or less on the field the old race left and the new one attacked
    in 2 (a 10% Gholdengo about to Nasty Plot: reasonable; a 10% Incineroar instead of a healthy Floette: the user's point exactly,
    the support's Fake Out / Parting Shot are not in the race, so the new race finishes it; pssim/results/finish_cases.json). Removed on
    2026-10-09 (6:08 pm) at the user's word, with the support credits of the next entry; the default race is unchanged. The user's reading stands: the race overestimates the effect in some cases, but
    neither "finish" nor "leave" is right in general, and a support's last non-damaging action is priced by neither race.
  - **Pricing a support's remaining non-damaging actions (`RACE_SUPPORT`, 2026-10-09, 6:05 pm; TR sheet relaying the user: "have the battle sim
    look into it", then "can the credits be fitted directly?").** The one thing neither race priced was a support's next Fake Out / Follow
    Me / Tailwind / Trick Room / screen / Parting Shot / Helping Hand / Wide Guard, which is what makes "finish the 10% Incineroar or hit
    the healthy Floette" a real question. Three versions were built and measured; **none is adopted** (strength flat, players' decisions
    matched no better); the flags stay available.
    - *Hand credits* (`RACE_SUPPORT=1`): in plan.rs `race_feats` each unit's usable support moves carry a credit in KO units (Fake Out
      0.35 if fresh, Follow Me / Rage Powder 0.4, Tailwind 0.5 when down and the side is slower, Trick Room 0.6 when down and the side is
      slower, screens 0.3 when down, Aurora Veil 0.5 in snow, Parting Shot 0.3, Helping Hand 0.2, Wide Guard 0.15, sleep moves 0.4,
      Will-O-Wisp / Thunder Wave 0.25, Taunt / Encore 0.25); in the race a unit supports instead of attacking when its best credit beats
      its best hit's score (one-shot moves once), the credits count 1/k like KOs, and the support edge (side 0 - side 1) is appended to
      the features after FEATS22's (29th); `RACE_SUPPORT_CREDITS=fakeout:0.32,screens:0.67,...` overrides a class's credit (0 drops it).
      Head-to-head on the 2,400 pool starts vs the always-Mega sym2 baseline (side 0 with the credits, weight 0.19 / 0.474 on the edge):
      **-0.2 ± 0.9 / -0.1 ± 0.9**, with the bench race as well +0.7 ± 1.2; by style nothing beyond ±3. The real-position refit priced the
      edge at +0.115 (held-out log loss 0.5583 vs 0.5572 without it: no gain). Finish cases (400 logged games, hand credits + bench race
      vs the old race, 43 low-HP-foe turns with the same history): it now finishes 5 the old race left (a 10% Gholdengo about to Nasty
      Plot, a 3% Mega Floette, a 20% Kingambit, a 19% Mega Charizard-Y, a 20% Indeedee) and leaves 2 it finished (a 15% Mega Gengar and a
      12% Mega Raichu-Y, both while the partner screens): the credits move the decision in the intended direction, but these are
      single-seed planner picks either way. Mega audit with it: 63 un-evolved attacking turns (old race 92, bench race 71), "the Mega KOs
      more yet base preferred" 9 (11 / 8).
    - *Fitted per class* (`RACE_SUPPORT=classes`, TR sheet's route 1): one feature per class (11, `SUPPORT_CLASSES`), the side
      difference of the race units with the class usable under the same availability conditions, no credits anywhere; dumped with
      `champ feats` on the egvalue10 real-position sets (fit 26,876 positions / 3,732 games, held out 3,968 / 560) and fitted
      symmetrically with the other 28 features (`build_egvalue10.py`, 39 features, bootstrap SEs by game; `CLASS_SHRINK` shrinks the
      classes toward a shared weight, 0 used). Positions per class 1,500-7,400, games behind the rare classes a few hundred. Credits in
      KO-edge units (weight / KO-edge weight 0.276): Fake Out +0.32 ± 0.12, Tailwind +0.30 ± 0.21, screens +0.67 ± 0.27, Taunt / Encore
      +0.73 ± 0.33, Helping Hand +0.24 ± 0.25, sleep +0.35 ± 0.48; Trick Room -0.16 ± 0.32, Follow Me -0.36 ± 0.30, Parting Shot -0.59 ±
      0.23, Wide Guard -0.88 ± 0.45, Will-O-Wisp / Thunder Wave -0.83 ± 0.53. Identifiable at 2 SE: Fake Out (on the hand value),
      screens, Taunt / Encore, and Parting Shot negative. The negative ones are not credits: the race counts those units as attacking
      every turn, so a unit that will spend turns on Parting Shot / Wide Guard / status is overrated by the race and the fit corrects it.
      Held-out log loss 0.5542 ± 0.017 (28 features 0.5572; a hair, not significant). Head-to-head vs the baseline, side 0 with: the
      fitted class weights as a linear add-on to sym2 (scaled to sym2's KO weight) **-0.5 ± 1.0** (Indeedee TR -3.6 ± 3.0, the rest
      within ±1.5); positive classes only **+0.1 ± 0.9**; the fitted positive credits in the race (KO-edge weight) **-0.5 ± 0.8**
      (Trick Room -2.3, Indeedee TR -2.9, Sand +2.3, all within 1.2 SE). Six support variants, none moves self-play strength.
    - *Players' decisions* (route 2, `pssim/support_decisions.py`): on Eval bar's accuracy set (the 2,729 of its 3,968 positions with a
      decision the credits touch, one-turn planner at 32 seeds, same seeds in every setting), the planner's weight on what the player did
      and its majority's match rate for: Fake Out on a fresh Pokemon (1,262 decisions, players 47%), finishing a foe at <= 25% HP that
      still has a support move (945, players 40%) or has none (1,054, 42%), Tailwind when down (834, 26%), redirection (605, 28%),
      Trick Room when down (496, 21%). Under the four settings (none, hand credits,
      fitted credits, fitted linear weights) the planner's weight on what the player did moves by at most ±0.7 points on every decision
      but one: the fitted linear weights make it set Tailwind less often (31% of the decisions vs 36%, players 26%; p(human) +1.9 ± 0.6,
      match +0.8 ± 1.1). Finishing a foe at <= 25% that still has a support move: the planner and the players finish at the same rate
      (39% vs 40%) under every setting, p(human) 64.5% in all four; the credits do not change the planner's choices there. Baseline:
      p(human) 62-76%, match 64-79%; the planner sets Tailwind more than players (36% vs 26%) and redirects less (16% vs 28%), both
      unchanged by any credit; 1250+ players (1,627 decisions) the same picture. results/support_decisions.txt and _r1250.txt.
    - Verdict: **none adopted, and scrapped** (the user, via TR sheet, 6:05 pm: "Ok yeah let's scrap the whole thing"). The flags
      (`RACE_SUPPORT=1|classes`, `RACE_SUPPORT_CREDITS`, `RACE_BENCH`) are removed from the source: plan.rs is back to its state before
      the bench race (commit ac43e91) and build_egvalue10.py to 25 / 28 features; the flags-off games are unchanged (400 of the pool
      starts replayed identically to the always-Mega baseline run after the revert). `pssim/support_decisions.py` stays as a general
      tool (planner vs players on a class of decisions, any evalpos output), as do the results files. Do not redo this: the support
      credits, the bench race and the Tailwind / redirection gaps above are closed unless the user asks again. What the data says: the one-turn matrix already
      plays out this turn's Fake Out / Tailwind / Follow Me, and a static credit for the turns after that is within noise of zero on real
      outcomes except Fake Out (+0.32 KO), too small to move self-play or the planner's choices; the race's blind spots in the Mega audit
      are a horizon question, not a credit question. The kit stays on v25 / `EG_MEGA_TIE=0`.
  - **How strong is the equilibrium? (`BATTLE_POLICY_0|1`, 2026-10-10, 4:20 pm; the user's question.)** battle4.rs gained per-side
    policies for how a side acts on the solved turn: `eq` (default, samples its mix), `random` (uniform over all its options), `pure`
    (its mix's heaviest option, no mixing), `greedy` (the joint option with the highest expected calc damage this turn, plan.rs
    `greedy_damage`: never Protects, switches or clicks status), `exploit:<e>` (the best response to a model of the other side that plays
    its mix 1-e of the time and a uniform non-switch option e of the time; `exploit:0` = the opponent knows the line / mix exactly, since
    side 0's policy is applied first), `noise:<e>` (plays its own mix 1-e of the time and a uniform non-switch option e of the time).
    Measured on the first 800 of the 2,400 pool starts (side 0 with the policy, the usual sym2 always-Mega setup, gain = side 0's win
    rate minus the baseline's 53.8% on the same games; pssim/results/policy_study.txt):
    random moves and targets **-47.6 ± 1.9** (6% wins), random leads as well -48.7; greedy highest-damage every turn **-26.2 ± 2.2** (28%);
    pure no-mixing **+0.2 ± 2.1** against the normal planner but **-37.6 ± 2.0** (16%) once the opponent knows the line; greedy once the
    opponent knows it **-46.4 ± 1.9** (7.5%); the current mixed play once the opponent knows the mix **-8.4 ± 2.1** (45%: the planner's
    mix is 400 fictitious-play iterations on a one-layer switch model with seeded values, not an exact equilibrium, so a reader with the
    exact mix still finds 8 points); a 10% exploiter (best response to "they err 10% of the time") against an optimal opponent **+2.1 ±
    2.2** (a wrong read costs nothing); optimal play against a 10%-random opponent **+4.1 ± 1.6**, exploiting that opponent **+6.0 ±
    2.2** (the exploit itself is worth about 2 of the 6). Lock-in is free until someone looks and costs about 30 points against a reader;
    greedy loses 26 to the normal planner and 46 to a reader. Eval bar's per-turn read study (evalbar/HANDOFF.md "What is a read worth?",
    2026-10-06: a 20% lean worth ~4 points a turn, a 10% lean every turn 15.3 a game vs 16.0 for 20% on the best third of turns, a
    wrong read 0.1 a turn) is the static counterpart; these are the full-game numbers.
    What rises and falls (`pssim/policy_lines.py` on the same games replayed with BATTLE_LOG=1 BATTLE_TURNS=1; results/policy_lines.txt):
    a reader facing the pure line switches 20.6% of its decisions instead of 11.3% (3.2 switches a game vs 1.8), focus-fires 62% of its
    double attacks instead of 51%, Protects a little less (9.9% vs 11.7%), sets up more (3.1% vs 2.0%), and ends games half a turn
    sooner; Trick Room and Tailwind rates do not move. Facing the known mix it switches 15.3% (+4.1) with everything else flat. Facing
    greedy it Protects half as often (5.5% vs 11.7%: the greedy side never Protects, so there is nothing to block), attacks more and
    wins in 5 turns. The pure player itself plays almost the same lines as the mixer (Protect +1.1, focus fire -4) until it is read,
    then its attacks land into switches: attack 41.7% vs 48.2%, Protect 14.9% vs 9.9%. Greedy is 96% attacks, no Protect, no switch,
    no Trick Room, games 2.4 turns shorter.
  - **Play the planner yourself (`champ play`, `pssim/play_server.py`, `pssim/play_ui.html`; 2026-10-10, 6:55 pm; the user: "set up a
    simple ui so that you could play me directly", instead of piloting the sim's clicks on the ladder, which could count as outside
    help).** `champ play <engine_data> <start.jsonl>` runs one game with a human on side 0 and the planner on side 1 over JSON lines
    (native/champ/src/human.rs; battle4.rs `play` took an optional human, spot.rs `resolve_switches_h` lets the human pick replacements
    and the planner answer them). The server builds the start with battle_starts.js (explicit job, your four in lead order, the pool
    team's recorded bring) and runs the planner with the v25 kit setup (sym2, DP2, anticipation, free Mega choice, EG_MEGA_TIE=0). Both
    sides see everything, as in self-play. Run from the repo root: `pssim/battlesim-play pssim/play_server.py` (or the `play` entry in
    .claude/launch.json), then http://localhost:8765. The page: your six (the Trick Room six or any 1250+ pool team), the opponent's six
    from the pool (or random), bring four by clicking in lead order, then per turn one option per slot (illegal pairs grey out), forced
    replacements as buttons, and the engine's protocol log in plain words. No sim evaluation is shown during a game.
  - **Attacking into an immune target as a switch read (`PLAN_KEEP_IMMUNE=0|1|both`, 2026-10-10, 9:45 pm; the user, from the play
    page: "it's not pointless, because my opponent might switch").** `slot_options` drops a damaging move aimed at an immune target;
    the flag keeps those options for that side. The play page sets it for the human side. For the planner, head-to-head on 800 pool
    starts vs the always-Mega sym2 baseline: **+0.4 ± 0.8 as side 0, +0.1 ± 0.8 as side 1** (37 / 41 games change; the solve takes
    1.9x the time, every immune target being one more row). In a logged run the planner aimed 1.7% of its targeted attacks at an
    immune Pokemon and the target switched out on 10% of those turns, below the opponent's 11.6% switch rate overall: sampled low-weight
    branches of the mix, not reads that land. Not adopted for the planner; the flag stays for the page.
  - **Play page follow-ups (2026-10-10 evening):** matches (next game with the same sixes; the server keeps the score and the fours
    brought, shown under the title, survives a reload), the planner picks its four and leads against your six with Team search's bring
    heuristic (teamsearch/bring/policy.py's model, sampled among its best six (bring, lead) choices so a match varies; the pool team's
    recorded bring as the fallback), type effectiveness on every move and option (type chart on the target's current types; a move
    whose type depends on the field is marked by its listed type), the opponent's six (not its four) before the bring, plain-words log
    lines for the engine's new weather / terrain / Trick Room / side-condition / crit / effectiveness lines, Psychic Terrain blocks
    named as such, a living Pokemon always shows a sliver of HP bar, forced replacements named by position (a Switch choice carries
    a position, not an index: the page's label was wrong once the order had changed), the page says when the server is unreachable.
    The server runs in the user's Terminal panel (`pssim/battlesim-play pssim/play_server.py`); a preview-started copy was stopped by
    the app after an hour. The user's read after a few games: the planner "does feel decently strong", "it'd win a bo100 vs me", with
    the caveat that the unfamiliar presentation makes them play worse for now.
  - **Play page, later on 2026-10-10 (to 11:30 pm):** Forfeit; "Ask the planner to concede" (8 planner-vs-planner playouts from the
    position, switches on, in parallel, judged by the clock rule when they run long; it concedes when its turn value is under 2% or it
    wins and draws none; the value stays on the server); the clock (`PLAY_CLOCK_TURNS`, default 100: Pokemon left, then HP share, then
    HP, as the game's timer); a human game runs to that clock, not the 25-turn self-play cap; game slots (`?g=1..5`, each its own engine
    and match, a slot bar shows which is waiting); the match record in results/play_match[_N].json and every finished game in
    results/play_games.jsonl (the strength record, shown on the page as the all-time score). Engine log additions for the page: a
    spread move's targets, Armor Tail / Queenly Majesty / Dazzling blocks. **Record so far: you 2 – 3 planner (5 games, two from before
    the log, one of those reconstructed).** The user stopped there ("I apparently can't multi table pokemon like I can poker") and will
    think about a better way to get the games in; nothing is pending on this side.
  - **Showdown bot (`bot/`, 2026-10-11, 12:30 am; the user: "let's make the bot and just make sure the play nice").** The planner on its
    own bot account on the Reg M-C Bo3 ladder, to measure it against real players (the user cannot get enough local games in; a ladder
    rating is on the pool players' own scale). Rules from the user: human pace, never the timer, a name that says bot, one canned PM
    reply, modest volume, and **stop laddering once we would meet players near the top** (bot/limits.json: hourly / daily caps, a rating
    stop, "opponent in the ladder's top N" from the public ladder JSON; the user does not want to warp the top of the standings); a ban
    of the bot account is acceptable. Pieces: `bot/client.js` (Node, `--experimental-websocket`: login, /search and challenges in the
    format, room logs, |request| handling, a think delay, limits, bot/out/games.jsonl with ratings and results only); `bot/brain.py`
    (one process: team preview by the bring heuristic against the |showteam| sheet; turns via `bot/position.py`: the Eval bar's
    `evalbar/botpos.py` builds the position (opponent as a spectator knows it, our side from the request, topk back rows), live.positions
    + engine.run evaluate it with the current build and EG_MEGA_TIE=0, a joint action is sampled from side 0's mix; replacements after a
    faint scored by the engine's static value of the next turn's start with each candidate in (the Eval bar's `bot_replacement`, the
    opponent's own replacement averaged over its likely ones), a type-chart rule as the fallback; `bot/test_cached.py` runs every
    decision of a saved game through the brain (about 1 s a turn, 0.6 s a replacement)). **Local bot-vs-bot test (2026-10-11, 11:25 pm):** the client has a local mode (`--server ws://localhost:8777/showdown/websocket
    --name <guest> --format <id> --teams <file> [--challenge <user>]`, `BOT_DEBUG=1` logs every server line) against the Showdown
    package in pssim/node_modules run as a server (**`./pokemon-showdown start --skip-build 8777 --no-security`** from that folder:
    without `--skip-build` the launcher rebuilds dist/ from the TypeScript sources, which wipes the project's Champions data patch
    (pssim/engine_patch, copied in by setup.sh). It did exactly that on 2026-10-10 at 11:24 pm, unnoticed until TR sheet found it the
    next evening and re-applied the patch; meanwhile three Megas carried old abilities in rebuilt positions (Golisopod, Garchomp Z,
    Absol Z) and a few Champions move PP / data changes were missing. It predates Reg M-C,
    so the test used `gen9championsvgc2026regmbbo3` with pool teams that validate there, bot/out/local_teams.json). Two clients
    matched on its ladder and played a full best-of-3 through the real protocol (team preview with the open sheets, turns at 2-4 s,
    replacements, Mega, readiness between games), after three fixes: a locked turn (charging, recharging) must be sent as `move 1`
    with no target and the target / mega suffix now follow the request's own move list; "busy" comes from updatesearch's games list, so
    the client no longer searches twice; the best-of match room confirms readiness (`/confirmready`), records the match
    (bot/out/matches.jsonl) and is not counted as a game. The dry login on the real account works ("logged in as abnew123-bot",
    "ladder top 100: 1539+"). Not yet run live: the user creates the
    account (git-ignored bot/account.json {"name", "password"}); start with `node --experimental-websocket --no-warnings bot/client.js
    --dry` to check the login, then without --dry. Teams in bot/teams.json (the Trick Room six; add pool sixes for variety).
  - **The last Pokémon's pointless Protect (`EG_LAST_PROTECT=0|1|both`, 2026-10-11, 3 am; the user's rule).** plan.rs `pointless_protect`:
    when a side is down to one Pokémon, Protect is not offered if it would change nothing this turn: no weather, terrain, room / Trick
    Room / Gravity, no side or slot condition (Tailwind, screens, Wish, Future Sight), no Pokémon on the field asleep, frozen, burned,
    poisoned, charging, locked, confused, Taunted, Encored, Disabled, Throat Chopped, Heal Blocked, drowsy, Perish-counted, Leech Seeded,
    Salt Cured or trapped, no foe with a fresh Fake Out, our Pokémon cannot still Mega Evolve and has no Speed Boost / Moody, and no
    healing for it below full HP (Leftovers, Black Sludge, Aqua Ring, Ingrain). Self-play on 800 pool starts: side 0 with the rule
    **-0.2 ± 0.2** (2 games change), both sides -0.2 ± 0.2 (4 change); last-Pokémon Protects 293 -> 226 for the side using it, games
    8.26 -> 8.19 turns. PP stalling, the case it could cost: in 4,923 cached real games a move ran out of PP in 15 (0.3%; Protect itself in
    8), and the 7 Struggle games were too short for PP to be the cause (Taunt / Disable / Choice locks). On for the Showdown bot
    (bot/position.py), off by default elsewhere.

## A better position value (2026-10-12, started; the user: "let's start working towards a better position score")
- Why: on the bot's ladder games the planner predicts +4.1 points a decision from opponents' plays and the bot gets +0.9 (`bot/ladder_lines.py`;
  bot/planner_issues.md "Where the strength gap is"): the bot's own picks are drawn to positions the value overrates, and depth with the
  same value does not help (two-turn horizon flat in self-play twice). On Eval bar's 560 held-out real games the static value's log loss is
  0.557 and the one-turn search's 0.523 (turn 1: static 0.704, worse than a coin flip): the static value misses most of what one turn of
  search sees.
- Data (`pssim/value_data.py`, results/value/, git-ignored): every turn of the cached Bo3 games rebuilt by evalbar/spots.py (hindsight
  sets) as engine positions with results: fit 28,393 positions / 3,929 games, held out 3,968 / 560 (Eval bar's accuracy games); `search`
  adds the one-turn search value of every position (champ evalpos, 32 seeds staged, sym2; about 2 s a position on one core with the
  current build), `feats` the 28 plan.rs features.
- Features (`native/champ/src/vfeats.rs`, `champ vfeats`, dev build only): per side, its actives against the other side's this turn
  (damage potential, focus fire, foes it can KO alone / first / by focus, outspeeds, priority and spread potential), what it has on hand
  (Protect, Fake Out, redirection, speed control, setup, Intimidate on the bench, the bench's threat and safest switch-in), actives in
  danger, boosts, statuses, Mega, locks; the field per side (Trick Room turns and whom it favours, Tailwinds, screens, terrain, weather,
  turn). About 0.3 ms a position.
- Fits (`pssim/value_fit.py compare`): value = sigmoid(h(e) - h(e_swapped)), symmetric by construction. On real results, a linear h on
  the new features + the 28 old ones: held-out log loss **0.5423** vs the current static 0.5535 (-0.011 ± 0.006); one-hidden-layer nets
  overfit the ~3,900 games' results (0.545-0.67). Distilling the one-turn search (its log-odds as the target, squared error): linear
  0.5374, a 16-unit tanh net **0.5342** (-0.019 vs the static value; the search itself 0.5225: 60% of the gap closed). Exported with
  `value_fit.py export 16 1e-3 search` -> results/value/vnet_h16_search.json.
- In the engine (`EG_VNET=<json>`, dev build; needs RACE=1 RACE_PRIO=1 FEATS22=1 CALC_DATA): the net scores both sides' leaves
  (`EG_VNET_SIDE=0|1`: only that side, for head-to-heads; replacements honour per-side values). Matches the Python model to 1e-15;
  0.15 ms a position. One-turn search with the net at the leaves on 1,503 held-out positions (220 games): log loss 0.5235 vs 0.5301 with
  sym2 at the leaves, **-0.0065 ± 0.0051**, same cost (2.15 vs 2.04 s a position). Self-play head-to-head on the 800 pool starts (sym2
  baseline run with the same flags): net on side 0 +0.6 ± 2.2, side 1 +3.0 ± 2.1, **pooled +1.8 ± 1.5** over 1,600 games; 2.2x the time
  per game (the matchup features at every leaf; not yet optimised).
- More data: `protect_replays.py new` fetched 14,262 Bo3 replays from 2026-10-04 to 10-12 (19,194 cached); they lean low-rated (45% of
  the rated ones 1000-1099). `value_data.py positions new` / `feats new` / `search 6 new` put them in part 'new' (the fit and held-out
  sets stay as they were for comparisons).
- Refit on fit + new (130,759 positions / 17,919 games), search targets, held out as before: linear 0.5375, h16 0.5335, h32 0.5355, h64
  (l2 3e-4) 0.5330, **h64 (l2 1e-3) 0.5317** (search 0.5219, static 0.5533: 69% of the gap). Exported: results/value/vnet_h64_search_fit+new.json.
  With it at the leaves (dev build, which also carries the race memo fix; baselines rerun on it): held-out one-turn search 0.5221 vs
  0.5301 with sym2 (**-0.0080 ± 0.0052**; h16: -0.0066), 3.6 vs 2.1 s a position; self-play on the 800 pool starts: side 0 +0.9 ± 2.2,
  side 1 +5.8 ± 2.2, **pooled +3.3 ± 1.5** over 1,600 games (the first evaluator change here with a self-play gain beyond 2 SE), 2.1x the
  time per game. Both nets helped side 1 more than side 0 (within noise so far).
- **Full damage-calc data (2026-10-12 evening, pssim/value_fc.sh):** champions_data.json lacked 1,250 species (Basculegion-F among
  them), so the race features fell back for them. With native/champions_data_full.json: the positions it changes re-searched, the h64
  net refitted (bot/value/vnet_h64_search_fc.json). Held out: 0.5219 vs the deployed net's 0.5221 (-0.0001 ± 0.0013, a tie); self-play
  on the 800 pool starts (frozen engine champ-dev-2026-10-12d, full calc data, sym2 on the other side): side 0 +4.5 ± 2.2, side 1
  +5.3 ± 2.1, **pooled +4.9 ± 1.5** (the deployed net had +3.3 ± 1.5 on the older engine and calc data; no direct net-vs-net
  head-to-head: the engine takes one net and one calc file). A first run of the self-play arms used the dev link while the engine was
  being rebuilt and was discarded: freeze the binary before long comparisons.

## Engine bug hunt: mid-battle differential tests and ports (2026-10-12 evening; the user, through the Eval bar: a systematic bug hunt)
Split with the Eval bar: Battle sim runs engine-vs-Showdown differential tests and ports; the Eval bar audits handler coverage
(evalbar/hook_audit.py: callbacks in the champions mod with no engine handler, ranked by sheet usage; counts loop and constant-valued
registrations since its second version) and checks reachability of real logs in Showdown (evalbar/reach.py).
- **What the old suites could not see.** `gen_turn_cases.js` starts every case right after team preview with random HP, boosts, Trick
  Room or Tailwind; statuses, volatiles, hazards, used items, fainted allies, later-turn Fake Outs, low PP or sleep counters only arise
  inside the one turn; sets come from the regional / model / focus pools; no attack is aimed at an ally; `diff` compares only durations.
- **`native/gen_battle_cases.js`**: whole Showdown battles between the 8,377 distinct open team sheets of the cached Bo3 replays
  (`native/real_teams.jsonl`, git-ignored; generic spreads by nature), random legal choices (an attack at the ally 8% of the time, the
  Mega 70%, a switch 15%); every turn becomes a case: the state before it, the turn in lo / hi / mid / real RNG, each with the post-turn
  state, log and next request; the battle continues from the real-RNG branch. About 110 KB a case (1,000 battles ~ 1.5 GB: write to the
  scratchpad, delete after). `TRACE=<battle>:<turn>` prints that turn's Showdown log with the draw count per line, each draw's call stack
  and the queue.
- **`champ turn` additions**: `DIFF_FULL=1` compares every effect state's contents (volatiles, side and slot conditions, status, ability,
  item, weather, terrain, pseudo-weathers), stats, types, move slots, item history, counters, the active Pokemon's disabled moves and
  trapping as Showdown's request leaves them (locked moves trap; maybeTrapped only on the last active; hidden disables show as usable
  there), and with `req` in the case the engine's request moves; `ORDER=1` the order of moves; `MAXEX` the example count;
  `DRAWTRACE=1` (with LOG=1) ends each engine log line in its draw count and logs tie shuffles and handler lists. Comparing draw counts
  between `DRAWTRACE` and `TRACE` finds where the random streams part.
- **Engine bugs found and fixed** (each now exact): partial trapping trapped Ghosts (no tryTrap); Recharge read as target 'normal' and
  skipped Showdown's random-target draw; Showdown's turn-start actions were missing (beforeTurnMove: Counter, Mirror Coat;
  priorityChargeMove: Focus Punch, Beak Blast, Chilly Reception: their effects and their speed-sort draws); Mimikyu's bust damage ran
  Disguise's onDamage twice (a tie with itself drew a shuffle); permanent forme changes logged -mega and set moveThisTurnResult for any
  source and reset Disguise's state; a transformed Pokemon kept the copied moves after leaving the field (export_state.js now exports
  baseMoveSlots for transformed Pokemon); 11 Mega Stones (Golurkite, Sharpedonite, Scolipite, ...) lacked the onTakeItem that keeps them
  on their user (flagged unsupported, now data-driven in Dex::attach).
- **Ports** (handlers/batch4.rs to batch6.rs, about 90 effects, each Showdown-exact on focused cases from real sheets or hand-built
  carriers): No Retreat, Sweet Veil, Eelevate, Focus Energy, Dragon Cheer, Strong Jaw, Frisk, Analytic, Moxie, Beast Boost, Steadfast;
  Reckless, Dragonize, Refrigerate, Skill Link, Iron Ball, Wise Glasses, Zoom Lens, Water Absorb, Earth Eater, Motor Drive, Overcoat,
  Plus / Minus, Long Reach, Tangled Feet, Immunity, Anger Point, Berserk, Harvest, Flame / Toxic Orb, Gyro Ball, Synthesis / Moonlight
  / Morning Sun, Strength Sap, Pain Split, Endeavor, Quash, High Jump Kick's crash, Worry Seed, Ceaseless Edge and Spikes; Steely
  Spirit, Focus Band, Red Card, Leppa Berry, Metronome (item), Stored Power, Electro Ball, Avalanche, Burning Jealousy, Alluring Voice,
  Trick-or-Treat, Forest's Curse, Raging Bull's type, Rapid Spin, Speed Swap, Power Trick, Minimize, Stockpile / Spit Up / Swallow,
  Role Play, Smack Down, Octolock; Counter, Mirror Coat, Focus Punch, Beak Blast, Chilly Reception.
- **Status**: 6,736 mid-battle cases (500 battles) and every earlier case file exact in all four RNG modes on the full diff; about 1%
  of mid-battle turns still hit an unported effect (flagged, never silent). Left, by use: Imposter / Transform, Beat Up, Cute Charm
  (needs genders), Bug Bite, Sleep Talk, Shed Tail, Instruct, Pickup, Cud Chew, Symbiosis, Liquid Ooze, Aroma Veil, Shell Bell,
  Gluttony, the 'trapped' volatile with its trapper link (Block, Mean Look, Spirit Shackle, Anchor Shot, Jaw Lock), Unseen Fist.
- Frozen for comparisons: `bin/champ-dev-2026-10-12d` (b26aa53; link `battlesim-champ-fc`). The live bot is unchanged (its frozen
  `champ-bot-2026-10-12` has none of today's fixes); they go in only when the user approves.
- **champ-battle-v26 (2026-10-13, for Team search's climb):** the source as of cb9cf51 (every Oct 12 port and fix; the source the live
  bot's champ-bot-2026-10-12c was built from), `native/champ/src_battle_v26.tar.gz`, built from the tarball itself; on 12 pool starts it
  plays the bot binary's games exactly (timings apart). Sha file `native/champ/bin/champ-battle-v26.sha256`. The setup recommended for
  the climb (the Oct 12 self-play arms' flags, the net on both sides): RACE_TIES=avg RACE=1 TRSYM=1 RACE_PRIO=1 FEATS22=1
  EG_VALUE=egvalue9_sym2.json EG_VNET=bot/value/vnet_h64_search_fc.json EG_MEGA_TIE=0 DP2=1 BATTLE_ANTICIPATE=1, no EG_MEGA_ALWAYS (free
  Mega choice), CALC_DATA=native/champions_data_full.json, engine data native/engine_data_full.json, GRID_DIR an empty directory. The
  net costs about 2.2x the time a game of sym2 alone (12 starts: 17 s on 4 threads).
- **champ-battle-v27 (2026-10-13) = v26 + the calc data maps on the engine's Fx hasher** (data.rs): race_damage and vfeats look species
  and moves up before the damage memo, and SipHash was about a tenth of a game with the learned value. Game-for-game identical to v26
  (40 pool starts with the net, and 12 from the tarball build); with the net, 17% less CPU (277 vs 332 thread-s on the 40 starts).
  A profile of a net game: the net's call 58% of the time, of which the side features 46%, the plan features (sym2 computes them too)
  29%, the network arithmetic 22%: f32 or batching would gain little. `src_battle_v27.tar.gz`, sha file `bin/champ-battle-v27.sha256`.
  Building with RUSTFLAGS="-C target-cpu=native" should keep games identical (no mul_add, no fast-math in the source; Rust does not fuse
  into FMA on its own; exp / tanh come from the system libm either way): check against the Mac reference as usual.
- **battle_starts.js job.meta.seed_index (2026-10-13, Team search):** with SEED_PER_JOB, a job's battle and sampling seeds use it in
  place of the job index, so the same four against the same opponent entry plays the same game wherever it sits in the list (tested:
  identical start lines and games at different positions). champ battle's own seeds already come from seedKey (their four) and g.
- **Style bias of the learned value (2026-10-13, 1:51 pm; the user, through Team search: "how does the current model look bias wise?").**
  replay_pairs.py on the Oct 7 set (2,094 real pairings, both players 1150+, both brings seen, the humans' own leads and brings), v27
  with the climb's frozen flags, sim minus real win rate by style:
  | style | sym2 (v27s) | h64 net (v27) |
  |---|---|---|
  | Rain | +1.7 | +0.8 |
  | Sun | +0.9 | +2.7 |
  | Trick Room | -5.1 | -1.1 |
  | Indeedee TR | -9.7 | -3.4 |
  | Tailwind | +8.2 | +1.6 |
  | Snow | +7.0 | +5.4 |
  | Balance | -7.0 | -0.6 |
  | Sand | +0.0 | -5.4 |
  | Rain + Sun | +8.9 | -0.9 |
  (± about 2.5-5 by style, the same games for both.) RMS over the nine non-Perish styles: sym2 **6.4** (Oct 7: 5.6), net **3.0**, about
  what sampling noise alone gives. Agreement with the real winner 54.7% -> **55.9%**. The net removes the Tailwind-over / Indeedee TR and
  Balance-under shape that no value or depth change touched on Oct 7; Snow +5 and Sand -5 remain, both within 1.4 SE.
- **champ-battle-v28 + the refitted net (2026-10-13, 7:15 pm; the user: a Bo1 game's Mega Raichu-Y Zap Cannon).** v28 = v27 + hit_chance
  in the analytic features (No Guard, weather accuracy, accuracy / evasion stages, Compound Eyes, Hustle, Victory Star, Wide Lens,
  Bright Powder, Sand Veil, Snow Cloak, Gravity); the turn simulation was always right, only the leaf values counted listed accuracy.
  The one-turn search redone for the 62,958 training positions (47%) where a living Pokemon brings an accuracy modifier into play
  (pssim/value_acc.sh; Thunder / Hurricane / Blizzard with weather possible 16k+, Raichunite Y ~13k, No Guard ~13k, Muddy Water ~6k),
  the h64 net refitted on top of the _fc layer (value_fit.py, VALUE_EVAL_SUFFIXES=_fc,_acc): **bot/value/vnet_h64_search_acc.json**.
  Checks (pssim/v28_checks.sh): self-play on the 800 pool starts vs v28 sym2: side 0 +1.7 ± 2.1, side 1 +5.1 ± 2.1, **pooled +3.4 ± 1.5**
  (v27's net +4.9 ± 1.5 against v27's sym2; the baselines differ). Real-pairings bias: RMS 3.6 (v27 net 3.0; noise alone ~3.7),
  agreement 54.6% (55.9%); Raichunite Y sides -5.1 -> **-2.4**; v28 sym2: RMS 5.8, agreement 56.1%. Held-out outcomes (the static net):
  log loss 0.5340 vs 0.5320 (+0.0020 ± 0.0015); on No Guard / Raichunite Y positions +0.0116 ± 0.0039: both nets over-rate the No Guard
  side there (49-50% predicted vs 39% real, n 857 from few games), and the fix values it more. Shipped to Team search's climb.
- **The live bot stays on champ-bot-2026-10-12c + vnet_h64_search_fc.json (the user, 2026-10-13 evening).** Held-out one-turn search
  against results (1,503 positions): bot now 0.5218, v28 + its net 0.5238 (+0.0019 ± 0.0017; No Guard / Raichunite Y +0.0072 ± 0.0043),
  the same lean as the static net and the real-pairings agreement. v28 goes to the climb (mechanics); the bot moves with v29 after the
  same checks.
- **champ-battle-v29 (2026-10-13, 8:40 pm) = v28 + ports + partner targets.** Ported: Revival Blessing (the request kept for its slot,
  a fainted Pokemon chosen, revived at half HP, instaswitched into an empty slot; spot.rs switch_opts), Flying Press, Champions'
  Unseen Fist (contact through Protect at x0.25), Guard Split, Power Split, Defog, Sleep Talk, Beat Up, Poison Point, Grass Pelt,
  Muscle Band, Supersweet Syrup (its once-a-battle flag carried in the state: export_state.js syrupTriggered); hidden disables
  (Imprison) usable in the last active slot's request, as Showdown does. Partner targets (planner_issues 17, PARTNER_TARGETS=0/s0/s1).
  Differential vs Showdown (lo / hi / real, gen_battle_cases.js, which now answers Revival Blessing requests): every set built
  today 0 mismatches; the unsupported callbacks these sets hit went from hundreds a mode to Opportunist, Future Sight, Fling, Spirit
  Shackle, Uproar, Copycat (left for later, with Jaw Lock (linked volatiles), Attract / Cute Charm (no gender in the state), Magician,
  Bug Bite, Shed Tail, Instruct, Curse). Partner-target self-play on the 800 pool starts: -0.1 ± 0.2 (794 / 798 games unchanged).
  The net is v28's (vnet_h64_search_acc.json): the features are v28's. `src_battle_v29.tar.gz`, `bin/champ-battle-v29.sha256`.
  Positions built from logs must set syrupTriggered for a Pokemon whose Supersweet Syrup has activated (else it fires again).
- **Moving the bot to v29 (checklist):** CHAMP_BIN to a champ-bot copy of v29, EG_VNET to vnet_h64_search_acc.json, and `'syrupDue': True` in
  evalbar/botpos.py's spec (the Eval bar's positions.js sets p.syrupTriggered from replay.py's syrupDone under it, 2026-10-13); client
  restarts between games / matches. Only after the v29 gate checks and the user's go.
- **champ-battle-v30 (2026-10-13, 10:05 pm) = v29 with the hidden-disable fix reverted for planning.** v29 showed an Imprisoned move as
  usable in the last active slot's move list (Showdown's request does), and planned on that list; but choosing it is refused
  ("[Unavailable choice]") and the request re-sent with it disabled. request_moves (what can be chosen: hidden disables count) is the
  planner's again; request_moves_shown (the displayed list) only for the differential test, which stays exact on every set. The bot's
  decide() no longer falls to Showdown's 'default' when the mix has nothing the request allows: the best-valued allowed joint option.
  Found on a Bo3 game (…2698029711 turn 2): the opponent's Farigiraf Imprisoned ours (Protect and Trick Room both), the bot planned on
  both, its Protect was refused and the re-sent request answered 'default'. The bot's positions carry no Imprison volatile (a
  battle-reading gap: the Eval bar's replay.py / positions.js). Bot: battlesim-champ29-bot -> champ-bot-2026-10-13b (v30).
- **champ-battle-v31 (2026-10-13, 10:30 pm) = v30 + two position fixes.** (1) Imprison's handlers use the holder as the source (it always
  is: target self); the bot's rebuilt position gave the volatile the opposing active as its source, so the engine Imprisoned our
  Incineroar's moves and not the ones the opponent's Farigiraf knows. (2) evalpos recomputes the request's disables when it loads a
  position (Battle::refresh_disables, end_turn's DisableMove pass alone; EVAL_REFRESH_DISABLES=0 turns it off): positions rebuilt from
  logs carry volatiles (Imprison, Choice lock, Disable, Taunt...) but not the disables Showdown derives from them, so the planner offered
  a Choice-locked Pokemon every move and an Imprisoned Farigiraf its Trick Room. On 120 held-out positions, 12 change (Choice lock,
  Disable), none from thread noise. Every differential set still exact. Bot: battlesim-champ29-bot -> champ-bot-2026-10-13c (v31).
- **champ-battle-v32 (2026-10-14, 2 pm) = v31 + the planner's immunity filter (an outside review, item 1) + the anytime search.** (1) The
  immune-target filter (plan.rs immune_to) uses the move's type as used and Showdown's immunity rules: -ate abilities (Dragonize too),
  Normalize, Liquid Voice, the move's ignoreImmunity, Ring Target, Scrappy / Mind's Eye / Foresight vs Ghosts, Miracle Eye vs Darks,
  isGrounded for Ground. v31 dropped single-target moves that land (Pixilate Quick Attack / Hyper Beam into Ghosts, Aerilate Double-Edge,
  Scrappy Fake Out): 555 of 32,361 real positions. On 200 of them the restored options take 16% of the mix (over half in 20 slots); 134
  of 135 random positions unchanged (the other: Pixilate Hyper Beam into Basculegion). Battle mechanics untouched, so no differential
  rerun. (2) deep.rs: the budgeted search as a tree (EVAL_DEPTH / BATTLE_EVAL), deterministic, every evaluation counted; inert without
  those variables. Bot: battlesim-champ29-bot -> champ-bot-2026-10-14a (v32). `src_battle_v32.tar.gz`, `bin/champ-battle-v32.sha256`.
- **champ-battle-v33 (2026-10-14, 3:30 pm) = v32 + the immunity filter per Mega copy (the review's second pass).** A Mega copy of an
  option is judged with the Mega's ability (Evolution comes before the move), the plain copy with the current one: a move that lands only
  with the Mega gets no plain copy, one that lands only without it only the plain copy. v32 judged both with the pre-Mega ability, so
  Mega Salamence's Aerilate Double-Edge (and Mega Altaria / Gardevoir / Glalie / Lopunny cases) into Ghosts stayed dropped. On 60 such
  positions the Mega copy came back in all 60 (9% of the mix on average), nothing removed, no plain copy added; 59 of 60 random
  positions unchanged (the other a real Mega Salamence case). Bot: battlesim-champ29-bot -> champ-bot-2026-10-14b (v33).
- **champ-battle-v34 (2026-10-14, 11 pm) = v33, about 1.25x faster, games identical.** (1) plan.rs EvalMemo: VNet::value opens a memo
  for one leaf evaluation, and the features read each Speed, hit chance, mid-roll damage and the effective weather once (EVAL_NOMEMO=1
  turns it off). (2) VNet::h sums only the non-zero inputs (bit for bit the same sums). (3) The Mega copy's ability is suppressed as the
  current one would be (Neutralizing Gas, Gastro Acid; the review's third pass). Also inert unless set: BATTLE_NS_0 / _1 (per-side luck
  seeds a cell), EVAL_DEEP_K0 and EVAL_KEY_SALT (deep.rs). Profile of the climb's v33 setup: the leaf value about 58% of game time, the
  turn simulation about 28%. 200 games with the climb's v33 setup: all identical (result, length, final value), CPU 836 -> 671 s.
  Bot: battlesim-champ29-bot -> champ-bot-2026-10-14c (v34). `src_battle_v34.tar.gz`, `bin/champ-battle-v34.sha256`.
- **champ-battle-v35 (2026-10-15, 1 pm) = v34 + EG_VNET_B (net against net), games identical when unset.** Side 1 plans with the
  EG_VNET_B net and side 0 with EG_VNET (value2 / two_values; under BATTLE_EVAL each side's search scores its leaves with its own net,
  plan::as_side). For testing a net trained on deeper search targets (pssim/value_box.sh). Checks: 4 BATTLE_EVAL games identical to v34
  without it and with EG_VNET_B = EG_VNET (all fields but timing); with two nets, side 0's turn-one choices match the games where both
  sides use EG_VNET, side 1's those where both use EG_VNET_B. The bot stays on v34. `src_battle_v35.tar.gz`, `bin/champ-battle-v35.sha256`.
- **champ-battle-v36 (2026-10-16, 8 am) = v35 + BATTLE_ADAPT_SIDE + a payoff matrix from the tree search, games and the bot's current
  outputs identical.** (1) battle4 BATTLE_ADAPT_SIDE=0|1 (under BATTLE_EVAL): that side chooses by evalpos's own staged search (the bot's),
  for self-play of a new bot search against the live one (pssim/depth_confirm.sh: depth 2 k0 2 at 80,000 +3.2 +- 1.1 points). (2) evalpos
  with EVAL_DEPTH and EVAL_MATRIX: as the staged search's matrix pass, the contempt rows / cols get EVAL_SEEDS static rolls, the tree is
  solved again, and the root's table goes out as "matrix" (deep.rs Node::table / ensure / resolve), so the Bo3 bot's contempt can run on
  the tree search. Checks: 12 bot positions identical to v34 in the staged search with the matrix and in the tree search without it
  (apart from value_se's last digits); bot/position.py contempt_mix runs on the tree's tables. Bot: battlesim-champ29-bot ->
  champ-bot-2026-10-16a (v36). `src_battle_v36.tar.gz`, `bin/champ-battle-v36.sha256`.
- **champ-battle-v37 (2026-10-16, 6 pm) = v36 + the Perish fixes and a cap on the matrix pass, all inert unless set; the bot's outputs
  identical (12 positions, the staged search with the matrix and the tree search with it).** (1) VNET_PERISH=1 (s0 / s1: one side's
  searches): the learned value gets PERISH2's term; the net had no Perish input, so neither side saw a reason to sing, escape or KO
  the trapper. On the 244 real Bo3 pairings with a Perish side (both players' real brings and leads, the climb's setup): the sim's
  Perish side 42.6% -> 48.5% against a real 49.2% (real - sim +6.6 +- 3.5 -> +0.7 +- 3.5; with Perish Song brought +9.4 -> +0.3),
  singing in 9% -> 37% of playouts (humans 32%); self-play of the term against none on them +1.6 +- 1.3. (2) plan::perish_on (a count
  running, or a Perish Song user with a trapper in or a foe trapped; PERISH_TRAP=1 widens it to any trapper or trapped Pokemon) triggers
  a deeper tree search: BATTLE_PERISH_DEPTH / _BUDGET (battle4, the climb's setup too), EVAL_PERISH_DEPTH / _BUDGET (evalpos). (3)
  EVAL_MATRIX_MS caps the tree search's matrix pass (the Bo3 bot's decisions reached 33 s uncapped). `src_battle_v37.tar.gz`,
  `bin/champ-battle-v37.sha256`. Bot: battlesim-champ29-bot -> champ-bot-2026-10-16b (v37).
- **champ-battle-v38 (2026-10-20, 1:50 pm) = v37 + VNET_PROGRESS, the endgame progress check (src/progress.rs; planner_issues 21), inert
  unless set.** With 5 or fewer Pokemon left in all, each side's damage is played to the end (two attackers a turn on the foes one at a
  time, calc mid roll x hit chance with accuracy / evasion stages x hits, PP spent) against the target's recovery (Leftovers, Black
  Sludge, Grassy Terrain, Aqua Ring, Ingrain, Poison Heal) and chip (poison, burn, Leech Seed, Struggle recoil): a side that cannot KO
  the other's team while the other can reads lost (z -6), one that can while the other cannot reads won, the sooner the better (z = 5 -
  0.8 ln(1 + turns)), two long races (4+ turns each) keep the net within 1.5 of the race's log-odds; off under Perish Song;
  s0 / s1 for one side; PROGRESS_DEBUG=1 prints the turn counts. Goes with ppDue (evalbar/botpos.py pp_used / set_pp, positions.js):
  the bot's positions had every move at full PP; now PP used comes from the log (one per |move| line without [from], Spite's count;
  matches the bot's requests in 125,564 of 125,572 readings) and the bot's actives' exact PP from its request (the Eval bar's
  positions use the same count since 1d2891f). Checks: the Overqwil game (Bo1 ...2699800290: Simple Beam, +6 evasion and defences,
  Spite to Struggle; the bot read 95-100% to turn 45 and 70% on Struggle) now attacks mid-game and forfeits at turn 48 (0.25%);
  3,982 real endgame positions in the bot's games: 3% change, log loss on those 1.74 -> 0.98, 24 games forfeited earlier (all lost),
  none no longer forfeited; endgame decisions 4.8 -> 5.0 s (median, the bot's search); self-play on 750 real endgames (pssim/
  results/progress, deep_endgames.sh with ARM_B / ARM_C VNET_PROGRESS=s0 / s1) +0.1 +- 0.2 (7 results differ). `src_battle_v38.tar.gz`,
  `bin/champ-battle-v38.sha256`. Bot: battlesim-champ29-bot -> champ-bot-2026-10-20 (v38), VNET_PROGRESS=1 in bot/position.py and
  ppDue in botpos.BOT_FLAGS from the 1:50 pm client restart.

## The climb's simulator against the bot's ladder games (2026-10-16; the user: check the sim before trusting what the climb finds)
bot/ladder_sim.py + pssim/ladder_sim.sh: the bot's 1,128 saved games (689 Bo3, 439 Bo1) rebuilt at turn 1 as the bot saw them (botpos,
top back-row guess; open sheets in Bo3, guessed sets in Bo1), each played out 4 times with the climb's v33n1 setup. Report:
pssim/results/ladder_sim_report.txt (git-ignored).
- **On average the sim is right**: sim 50.9% vs real 50.5% (-0.3 +- 1.6); the Trick Room six 51.7 vs 51.7 (549 games), the regional
  pool teams 49.7 vs 49.8 (530). The sim's favourite won 61.5% of the 849 games it did not call even.
- **Per game it is overconfident**: real results move 0.62 +- 0.09 per unit of the sim's win chance (the 4-playout noise taken out;
  Bo3 0.67, Bo1 0.55: hidden sets and back rows cost the most where less is known; the back-row guess was right in 282 of 896 games).
  If that carries to team averages, real gaps between teams are about 0.6 of the sim's, with the order kept.
- **Style biases (real - sim, ~30 rows, so one or two at 2 SE by chance)**: our Balance teams -16.5 +- 5.5 (65 games, 29% real vs 46%
  sim; matches the Bo1 Balance slump); Perish opponents -16.0 +- 7.0 (the sim cannot play the trap; the climb's TS_PERISH=real covers
  it); Rain + Sun opponents -8.3 +- 5.4; Indeedee TR opponents +8.5 +- 5.6; our Tailwind teams +10.1 +- 5.2. The Trick Room six by
  opponent: Balance +7.8 +- 5.2, Rain +8.3 +- 7.3, the Trick Room mirror -10.4 +- 7.1, Rain + Sun -8.3 +- 7.2, Perish -16.3 +- 9.2,
  Sun 0.0 +- 5.4.
