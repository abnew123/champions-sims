# Team search: the "optimal" six under our models

Handoff written 2026-10-03, 2:45 am, from the Trick Room Six thread. Start here. For the full tool history, also skim `../HANDOFF.md`, especially the last three sections.

## The question

The user wants to know which six our own machinery rates best. That machinery is three models:

- the turn-one lead model and solver,
- the 2v2 endgame planner,
- the one-on-one threat matrix.

The answer is "optimal under these models" only. Say so, and list the assumptions next to the result. This is an exploration, separate from the Trick Room Six:

- The memory note `team-identity` (keep that team a distinct Trick Room team) applies to the Trick Room Six. It does **not** restrict this search.
- Don't change the Trick Room Six's files or sheet based on findings here; report them to the user instead.

## Ground rules for this thread

1. **Everything outside `teamsearch/` is read-only.**
   - Another thread's runs depend on `pssim/`, `mxtr/`, `native/`, `recordings/`, `trsheet/` and the root files.
   - Put new team files, job files, results, scripts and logs under `teamsearch/`.
   - To change a shared script, copy it into `teamsearch/` first. Mind its relative paths, listed below.
   - Build Rust to its own target dir: `CARGO_TARGET_DIR=../teamsearch/target`, run from `native/champ`. `native/champ/target` is in use by the other thread.
2. **CPU:** at most 3 workers while the user is at the computer (about 25% of 14 cores). Ask before going higher.
   - The other thread's runs count toward this budget. Check `pgrep -fl "run_jobs|champ |cand_run|rilla2_run"` first. As of 2:45 am, `pssim/rilla2_run.sh` uses 3 workers until about 4:15 am.
   - The user often says "I'm away, use more". Then 10–12 is fine.
   - The Mac sleeps with the lid closed. `caffeinate -i -w <pid>` only stops idle sleep.
3. **The user's standing preferences** are in memory (MEMORY.md):
   - **Consistency** (100%-accurate moves) does **not** apply to this search; inaccurate moves are fine here (user, 2026-10-03; see the scope line in memory `consistency-preference`).
   - **No misplay design:** assume competent opponents.
   - **Times** in 12-hour am/pm.
   - **Short status updates** during long runs.
4. **Python:** use `.venv/bin/python3` for anything needing numpy/scipy (`tr_select.py`, `tr_final.py`, `tr_grid.py`). System python3 lacks numpy.

## Starting point

- `teams/trick_room_six.json` holds the user's real current six. The sim baseline `pssim/myteam_c_incin.json` still has the older Adamant Kingambit and Torkoal 32 HP.
- The user's other team, which already has its own sheet and guide: Rillaboom, Incineroar, Mega Salamence, Gholdengo, Kingambit, Sneasler. It's a good second reference point.
- Usage, for picking a pool (`../team-sheet.html.usage.json`, the M-C top list):
  - Rillaboom, Sneasler, Mega Salamence, Incineroar, Kingambit, Basculegion, Mega Floette, Farigiraf, Mega Golisopod, Pelipper, Indeedee-F, Gholdengo.
  - Arcanine-Hisui, Sylveon, Whimsicott, Archaludon, Mega Tyranitar, Mega Baxcalibur, Garchomp, Mega Garchomp Z.
  - Then Milotic, Mega Charizard Y, Mega Gardevoir, Mega Raichu Y, …
- Set sources:
  - `../regionals/smogon_mc_sets.json` (259 species, keyed "Species" or "Species-Mega"),
  - `../regionals/regional_sets.json`,
  - `pssim/opp_model_{a,b}.json` (the ladder sets by archetype).
  - Fix inaccurate moves before use. Example: Rillaboom's High Horsepower (95%) → Stomping Tantrum (100%).

## The three models (what exists, how to run, what's hard-wired)

### 1. Turn-one lead sims (Node + Showdown engine)

**How it works:** `pssim/t1sim.js` builds my lead and back row against one opposing lead pair from an archetype. It plays every joint action × their joint action for N RNG samples. Each cell is scored by the W2 win model (`analyze.py`), fitted on 7,781 replay games.

- **Paths:** t1sim reads `../foes.json` and the opponent models via `__dirname`, so it works from any cwd. `MYTEAM` is a path (`MYTEAM=../teamsearch/teams/x.json`).
- **Job maker:** `pssim/jobs_team.js` (all 15 pairs × 10 archetypes × 6 opposing leads = 900 jobs) is **hard-wired to our members**:
  - `CORE` order and `ATK0` attacker preferences decide lead naming and default back rows.
  - Lead names must be ordered consistently: trlib keys, Speed files and `tr_final` all join names with "+".
  - For general teams, write `teamsearch/jobs_any.js` with one fixed canonical order (e.g. pool order) and a generic back-row rule.
- **Run:** `pssim/run_jobs.sh <jobs> <outdir> <samples> <workers>`.
  - Stage one uses 1 sample per cell; refinement uses 12, on rows picked by `tr_select.py`.
  - Workers skip finished jobs, so runs resume.
  - Always set `TW_UNDER_TR=zero`.
  - `ITEM_OVERRIDE=Indeedee-F=colburberry|psychicseed` gives the opposing Indeedee item variants that `tr_final.py` merges. Run them from the same jobs file.
- **Speed:** about 15 CPU-seconds per stage-one job, so 900 jobs take about 10–15 minutes on 13 workers. Refining about 250 contender jobs is about 10 minutes on 13.
- **Solve:**
  - `tr_speeds.js <jobs> <out>` (needs `MYTEAM`) gives the Trick Room credit speeds.
  - `TR_SPEEDS=… READER_W=0.75 TRMULT_FILE=trmult_final.json tr_final.py <resultsDir> <out.json>` gives `leads[arch]['all']['vals']` = `[lead, ladder, reader, score, n]`. **Use `score` (index 3)**, which is 0.25 × ladder + 0.75 × reader.
  - `EXCLUDE_MOVES="switch -> X"` drops plan rows the team can't play. This matters when reusing results across teams.
- **Trick Room credit:** recomputed at load time from the Speed file (`trlib.adjust`), so raw results can be reused across teams with different back rows. The back row also affects turn-one switch options. Exclude those, or regenerate per team.

### 2. 2v2 endgame planner (native Rust, fast)

**How it works:** for each pair of mine against each archetype's likely turn-3 pairs (`pssim/endpairs.json`), both sides play the one-turn Nash each turn, and the game is played to the end.

- **Value function:** `pssim/egvalue2.json`, fitted on our team's 2v2 games. Its features are generic, including matchup-grid coverage.
- **Jobs:** `pssim/eg_jobs_t3.js` (reads `endpairs.json` from the cwd, so run from `pssim/`). Pairs come from the `MYTEAM` keys.
- **Run** (from `pssim/`):
  ```
  JOBS=<idx list> MYTEAM=… GRID_DIR=… EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 ./eg_run_native.sh <jobs> <outdir> <games> <threads>
  ```
  - `eg_run_native.sh` runs `native/eg_starts.js` (needs cwd `pssim/`) and then `native/champ/target/release/champ plan`.
  - About 2–3 thread-seconds per job of 8 games.
- **Seeds:** they depend only on the game index, so two teams on the same job list are paired. That's why the deltas in `sp_compare.py` are tight.
- **Engine scope:** only species, moves and items in `native/champions_data.json` are exported (`EXTRA_MOVES=a,b` adds moves, as in `native/engine_data_spot.json`). Moves or abilities with handlers not ported to Rust are flagged in each result's `"unsupported"`. Check it. Known gaps: Revival Blessing, Healing Wish, Baton Pass, Ally Switch, Beat Up, Magician, Wandering Spirit.
- **The planner never clicks Healing Wish or Memento**, so it undervalues them.

### 3. One-on-one matrix (pure Python, `mxtr/`)

- `matchup.py` holds **hand-written** stat and move entries (`MINE`, `CANDS`; foes in `F`).
- `tr_grid.py` with `GRID_MONS=<names> GRID_TAG=… TR=1|0 NPROC=…` builds `gx_cells_{tr|notr}{tag}.json`, keyed "foe|mine".
- The planner's value function reads the cells from `GRID_DIR` (`gx_cells_{tr,notr}_inc.json` plus `_ext`). A Pokémon with no cells gets neutral values.
- **For a pool search:** write a generator in `teamsearch/` that builds `MINE`-style entries from sets (Champions stats: stat = floor((base + 20 + SP) × nature), HP = base + 75 + SP). Inject them by importing `matchup` and updating `MINE` at runtime. Don't edit `mxtr/matchup.py`. It took about 20 seconds for one Pokémon.

## Reusable comparison scripts (in `pssim/`, read them for the formats)

- `sp_compare.py <tag>`: paired 2v2 deltas.
- `sp_lead_cmp.py <MON> name:dir:speeds[:EXCLUDE] …`: merges refined leads with `results/v11` and runs `tr_final`.
- `sp_team_cmp.py` (`SLOT` env): per team, best lead plus best back pair from the other four, weighted by archetype share.
  - Shares: Tailwind 26.2, Sun 12.0, Indeedee TR 11.9, Rain 10.5, Balance 9.3, Sand 9.0, Snow 7.8, TR without Indeedee 6.7, Rain + sun 3.3, Perish 3.3.
- **The "key trick"** (for one-slot swaps): keep the old member's key in the team JSON but put the candidate's set under it. Every job file, back row and Speed file then applies unchanged. For a full search, use real names instead.

## Suggested approach (cache at the pair level, then enumerate teams)

1. **Pool:** about 20–25 Pokémon, one set each (100%-accurate moves; explicit spreads; item clause in mind).
2. **One-on-one cells** for the whole pool (minutes).
3. **2v2 for every pool pair:** C(20,2) = 190 pairs × 120 jobs. Roughly 3 hours on 12 threads, 8 games each. Cached per pair, and independent of the rest of the team.
4. **Stage-one lead sims for every pool pair** against each archetype's 6 opposing leads: 190 × 60 = 11,400 jobs, about 45 CPU-hours (about 4 hours on 12 cores). Use no back-row switch options, or a generic back row. Recompute the Trick Room credit per team from the Speed file.
5. **Enumerate every legal six** (species clause, item clause, mega rules: check what Champions allows):
   - team score = archetype-weighted best lead score + best back pair from the other four, like `sp_team_cmp.py`,
   - report both parts, and add Trick Room-up share as a style indicator.
6. **Refine the top ~10 teams properly** (refinement rows, item variants, real back rows) and compare them against the Trick Room Six and the user's other team on the same footing.

**Pitfalls the previous thread hit:**
- tr_select gaps longer than a minute meant the Mac was asleep.
- `tr_final` crashes on results with zero rows (empty `F`): skip those files.
- A reused `results/m_<name>` or `tr_final_m_<name>.json` name from another study overwrites it silently. Use unique names.

## Assumptions to state with any answer

- **The opponent model is fixed:** replay archetype shares, their lead and bring frequencies, and click rates from about 5,000 Showdown M-C Bo3 replays. Opponents don't adapt their bring to our team, except through the reader solve.
- **The win model** scores turn one only, from replays. The 2v2 planner looks one turn ahead, and its value function was fitted on our team. The middle of the game (turns 2–3 with full back rows) isn't modelled. Trick Room is counted at 59% of its 2v2 value (anchored to the replay fit).
- **One set per species**, standard Smogon spreads unless optimized. The sims can't value Healing Wish, Revival Blessing or similar.

## Progress (2026-10-03, 3:05 am)

**Scope changes from the user:** accuracy doesn't matter here ("strongest team period"; inaccurate moves are fine). New plan: **hill-climb** from each Reg M-C regional top-16 team, swapping one member at a time for a common Pokémon + set, keeping improvements until nothing improves. The evaluator will be the **full 4v4 sim the user is building in another thread**. Don't start team-level sims before it exists. The pool and pair plan above (steps 3–5) is superseded.

**Built (all under `teamsearch/`):**
- `build_sets.py` (helpers in `sets_lib.py`) writes:
  - `teams/start/`: 48 top-16 teams (Baltimore/Brisbane/Frankfurt, MYTEAM format) + `trick_room_six.json`. `index.json` gives event, place, archetype, member grid ids and spread sources.
  - `swap_pool.json`: 48 sets over 38 species (≥4% of the 768 regional teams). Per species: item clusters with ≥25% share, max 2, each with its modal nature/ability/moves.
  - `field/regional_field.json`: all 768 regional teams, normalized (an opponent pool option).
  - `grid_sets.json`: every distinct set, keyed by grid id (`M-Salamence#1`, …). 189 sets are in the start teams + swap pool.
  - `support.json`: sets the Rust engine can't fully run. Among the starts, only Brisbane-06's Indeedee (Baton Pass) and the Trick Room six's Healing Wish.
- **Spreads:** open team sheets have no stat points. `sets_lib.fill_spread` uses the top Smogon spread with the same nature (280 of 288 top-16 sets), else a nature-based default.
- **One-on-one grid for any set:** `mx/` is a copy of the mxtr modules. `pool_mine.py` builds `MINE` entries from Showdown's Champions data:
  - Mega forme stats and ability; base-forme `entry_st` and entry ability; -ate and Tough Claws; spread, drain, recoil and self-drops; 100% target drops.
  - Multi-hit, Psyshock and Freeze-Dry, plus the existing special moves.
  - In `matchup.py`: my setter's weather/terrain wins; White Herb, Choice Band/Specs, Assault Vest, Expert Belt, Psychic Seed; full nature table.
  - **Validated:** the Trick Room six's Kingambit reproduces all 46 old mxtr cells exactly, with and without Trick Room.
  - **Run:** `mx/grid_pool.py` (one job = one set vs 46 threats, about 15 s; output `mx/out/{tr,notr}/<gid>.json`; resumes). `mx/run_grid.sh` waits for the other thread's sims to be idle, then runs 3 workers (log `mx/run_grid.log`). `mx/merge.py <team>|--all` writes per-team planner `GRID_DIR`s to `mx/griddirs/<team>/`, with cells keyed by base species as plan.rs expects.
- **Known gap:** a Grassy Seed holder of mine (Sneasler#1) only gets its seed when the threat brings grassy terrain. Partner terrain isn't assumed on my side.

### Hill-climb driver (`climb.py`, 3:20 am)
Rules agreed with the user:
- **Megas:** no Mega cap in round 1. If no accepted round-1 swap has 3+ Mega Stones, cap at 2 from then on.
- **Screening:** screen every neighbour with a few paired-seed games, then confirm the top few (`N_SCREEN` 16, `TOP_K` 5, `N_CONFIRM` 128, move if better by `MARGIN` 1 SE).
- **Item clause:** a clashing candidate falls back to that species' next item-clause fallback set; it is skipped if the species clearly uses one item (top item ≥85% of its regional sets, and every Mega).

Usage:
- `python3 climb.py stats`: round 1 has about 11,100 neighbours over 49 starts (about 225 each; about 48 of a 2-Mega team's neighbours have 3+ Megas). That's about 215k games at the defaults, so the 4v4 sim's speed decides whether screening needs a cheaper pre-filter.
- `evaluate()` is the hook for the 4v4 sim. Contract: `team_json` dicts, `n_games`, `seed0`; game k uses seed `seed0 + k` for every team; returns `(wins, games)` per team. Scores are memoized by team, n and seed. Log goes to `climb_log.jsonl`.

### Evaluator, bring heuristic, cloud notes (3:50 am)
- **Evaluator:** `evaluate.py` runs the other thread's 4v4 battle sim in archetype mode: 10 replay archetypes × their 6 modelled lead pairs = 60 jobs per team, in a fixed order, G0 = seed, so games pair across teams.
  - Each team gets `runs/<key>/` with myteam.json, jobs.json and grid/.
  - Score = archetype share × lead-pair-share-weighted win share. Games flagged unsupported are dropped.
  - Env: `TS_EG_VALUE` (default pssim/egvalue5.json, the other thread's checked recommendation, with BATTLE_ANTICIPATE=1 via `TS_ANTICIPATE`), `TS_BATTLE_BIN` (default v2 since 3:55 am; v2 plays out no-damage stalls to 250 turns, so PP and Struggle decide them; v1 hands them to the value function at turn 25), `TS_PARALLEL`, `TS_THREADS`.
- **Climb:** `climb.py round thorough|lean` plays one round; state in climb_state.json, log in climb_log.jsonl.
  - Matrix pre-filter (`bring/policy.matrix_score`), plus random extras to check it.
  - A thorough round is about 123k games, about 15.6 h on 13 local threads. A lean round is about 4.8 h.
- **Brings** (user, 2026-10-03: "our own heuristic, matrix but not solely"):
  - `bring/feats.py` features; weights fitted by `bring/fit.py` on team-preview choices in 3,060 public M-C Bo3 replays (`bring/fetch_preview.py` -> previews.json).
  - `bring/policy.py` picks the four and leads per archetype.
  - Refit after the grid finishes. Then `rm -rf runs` is unnecessary: runs re-prepare when bring_model.json changes.
- **Cloud (user asked, undecided):**
  - AWS c7a.48xlarge: 192 cores, spot about $2.5–3/h, a thorough round in about 1.5 h.
  - Needs: Linux build from `native/champ/src_battle_v1.tar.gz` (checksums in `native/champ/bin/champ-battle-v1.sha256`); `native/engine_data_spot.json`, `native/battle_starts.js`, `native/export_state.js`; pssim/ (t1sim.js, seedmix.js, opp_model_{a,b}.json, node_modules via setup.sh's engine-patch step); foes.json; GRID_DIRs; EG_VALUE json.
  - Node 18+ on the box, or generate starts.jsonl locally and upload.
- **Cloud guide:** `cloud/README.md`, with `cloud/pack.sh` (Mac: ~1 MB bundle) and `cloud/remote_setup.sh` (Ubuntu 24.04: deps, setup.sh, checksum-verified Linux build of champ-battle-v2). The user chose the laptop for now. TODO: write `cloud/reference.json` = `evaluate.py trick_room_six 1 0` on the Mac with the final bring model, so the cloud build can be checked against it.

### Bring weights from battle outcomes (11 am)
- **Why:** a heuristic fitted to ladder players' brings (`bring/fit.py`, `bring_model.json`) agreed with the sheet's solver picks for the Trick Room six in 0/10 archetypes (2/10 without the species-popularity prior). The user chose to fit the weights to battle outcomes instead.
- **Training:** `bring/train_battles.py`: 12 start teams × 10 archetypes × 8 choices (human top 3, features-only top 2, random) × 6 lead pairs × 2 games, about 11.5k games, written to `train_labels.json` (log `train_battles.log`, runs/train_*). The Trick Room six is held out.
- **Fit:** `bring/fit_outcome.py` is within-group ridge on bring + lead features + human log-prob; it writes `outcome_model.json` and reports the held-out pick gain. `policy.chooser()` and `evaluate.prepare` switch to it automatically once that file exists (`TS_BRING=human` to override).
- **Check after fitting:** `bring/compare_sheet.py` (same picks as the sheet?), then battle the Trick Room six with the sheet's picks vs the fitted picks via `evaluate.run_team(..., fixed=...)`.
- **Defaults now:** champ-battle-v2 + egvalue5 + BATTLE_ANTICIPATE=1 (the other thread's checked recommendation; its runs are finished).

### Brings: results, and bring search in the climb (2 pm)
- **Outcome fit** (`bring/fit_outcome.py`, 960 labels): ridge chose the strongest setting (1e5), i.e. a correlation-weighted direction.
  - Held-out picks beat a random choice by +8.8 win-share points; the human-imitation picks by +4.7.
  - Top relative weights: human log-prob 1.0, two Megas -0.7, coverage 0.66, lead offense 0.55, defense 0.49, offense 0.48.
- **Trick Room six check** (`bring/sheet_battle.py`, 240 paired games each): sheet picks 72.5%, fitted 60.1% (-12.5 ± 4.0), human 48.6% (-23.9 ± 4.8).
  - Bring choice swings a team by 10–25 points.
- **Shortlist check** (`bring/search_check.py`): battle the fitted model's top 4 per archetype, keep the best, re-test on fresh seeds: 72.3%, the same as the sheet.
  - Kept ranks: #1 ×4, #2 ×2, #3 ×3, #4 ×1.
- **So the climb now uses bring search** (`evaluate.search_team`, K = `bring_k` 3): screening = top-3 choices per archetype × 6 lead pairs × 1 game, best kept (selection-biased, used only to rank). Confirm = fresh paired games with the chosen brings (`evaluate.evaluate_fixed`), and only those decide a move.
  - A thorough round is about 162k games, about 20 h on 12 threads; a lean round about 79k.
- **Round 1 (thorough)** started at 2:05 pm: `round1.log`, progress at localhost:8767.
  - Settings: TS_PARALLEL=5, TS_THREADS=2 while the other thread runs 3 workers; raise to 6×2 when it's idle (kill + relaunch: battles are cached).
  - A plumbing test (`climb.py round test`, TS_STATE/TS_LOG/TS_PROGRESS/TS_STARTS for a sandbox) ran clean first.
- **3:35 pm:** round 1 relaunched at 6×2 = 12 threads (the other thread is idle). Battles resume from cache.
- **Noise note from the other thread:** in v2, turn and planning seeds come from (job index, g). The same matchup at a different job index gets independent planner RNG. Run-to-run differences of an identical combo reached 24 points on 96 games (per-archetype SE 3–6 points).
  - The confirm stage keeps jobs in a fixed (arch, k) order, so it's paired.
  - Bring-search candidates (job = arch, candidate, k) aren't paired with each other in v2.
  - The other thread is building champ-battle-v3 with seeds keyed on (arch, k, g). Switch `TS_BATTLE_BIN` to it from round 2 (not mid-round).
- **champ-battle-v3** (4:00 pm, from the other thread): turn and planning seeds key on the opponent instead of the job index, so candidates and teams meeting the same opponent in game g share RNG.
  - The seed key comes from `seedKey` in starts lines, written by the updated native/battle_starts.js. Starts files without it run like v2.
  - `climb.py` pins the binary per round: round 1 = v2 (it started on v2), round 2+ = v3, unless `TS_BATTLE_BIN` is set.
  - cloud/pack.sh and remote_setup.sh now default to src_battle_v3.tar.gz.
- **12:35 am Oct 4:** added the user's "Low-Variance Six" (Rillaboom, Incineroar, Sneasler, Gholdengo, Kingambit, Mega Salamence; sets from their team-sheet artifact) as start `low_variance_six` (teams/low_variance_six.json, via build_sets.py USER_TEAMS).
  - New grid ids: Gholdengo#17, Incineroar#80, Kingambit#29, Rillaboom#55, Sneasler#85; Mega Salamence = M-Salamence#6. Cells computed.
  - Round 1 relaunched at 3 cores (user back), now 642 teams to screen.
  - `set_threads.sh P T` changes threads; `at_bedtime.sh` raises to 6×2 at 3:30 am unless HOLD_CPU exists.
- **CPU rules (user, 2026-10-04):**
  - At most **10 busy cores in total** across both threads, even when the user is away (the battery drains above that). Split evenly when both threads need compute.
  - `at_bedtime.sh` goes to 5×2 = 10 alone, or 3×2 = 6 if the other thread's run is up. Use `set_threads.sh 5 2` after the other thread says it's done.
  - Estimates assuming 12–13 threads are now about 20% longer.

### Cloud round 1 (Oct 4, 4 am)
- **Box:** AWS c7a.48xlarge spot, us-east-2, `ubuntu@HOST`, key `~/.ssh/KEY.pem` (box since terminated); repo subset at ~/champions-sims.
  - champ-battle-v3 built there; it matched the Mac reference on 60/60 jobs (68.5% both).
- **Round 1 restarted fresh** on v3: `tmux` session `climb`, 36×4 = 144 cores, log `round.log` on the box. The other thread may use the other 48.
  - The laptop's partial v2 round 1 (440/642 teams screened) stays in `runs/` for comparison only.
- **Results** are pulled every 15 min to `teamsearch/cloud_results/` by `cloud/pull_loop.sh` (log `cloud_results/pull.log`). They're kept apart from the local runs/: same folder names, different binary.
- **Auto-off:** `~/watchdog.sh` on the box powers off after 45 idle min or 8 h. `~/KEEP_ALIVE` pauses the idle rule.
  - After the user's night: check that the EC2 instance is terminated.
- **Round 1 done on AWS (7:20 am, v3):** 29 of 50 starts moved; 21 are at a local max.
  - Moves mostly bring in Garchomp (10), Basculegion (5), Kingambit (3).
  - One accepted move made a 3-Mega team (Frankfurt-14: Farigiraf → M-Swampert), so per the user's rule the Mega cap stays off.
  - 3 of the 29 moves came from random extras.
- **Learned pre-filter** (`climb.learned_prefilter`, used from round 2): ridge on incoming/outgoing set effects + matrix score, fit on all earlier rounds' screened swaps in climb_log.jsonl.
  - Held-out-start within-team correlation +0.30, vs +0.20 for the matrix score alone; predicted top 3 averaged +2.8 vs -2.8 for random swaps.
- **Round 2** (thorough, 29 teams, about 96k games) started at 8:00 am on the box at 30×3 = 90 cores (the other thread had 96). Expand to about 60×3 when it's done. Expected end about 10 am, before the 12:03 pm watchdog cap.
- **9:40 am:** the other thread finished on the box. Round 2 relaunched at 60×3 = 180 cores via `cloud/relaunch.sh P T`; it's a script because pkill patterns typed on an ssh command line can kill that command's own shell.
- `cloud/auto_rounds.sh <cap epoch>` on the box starts further thorough rounds after the current one if they fit before the 12:03 pm power-off (about 3 min per climbing start at 180 cores, plus a 10 min margin).
- **Rounds 3–4 done** (state round 4; pulled 11:51 am): 2 of 50 starts still climbing. Round 5 for those 2 was cut off by the 12:03 pm power-off and isn't committed.
  - Leaders on confirm games: Frankfurt-10 → Delphox*, Garchomp, Incineroar, Kingambit, Raichu*, Sneasler (79.5, local max); Frankfurt-05 → Archaludon, Charizard*, Delphox*, Garchomp, Incineroar, Rillaboom (78.4); Baltimore-12 → Archaludon, Delphox*, Garchomp, Incineroar, Indeedee-F, Kingambit (77.4).
  - The top 3 share Mega Delphox + Garchomp + Incineroar. trick_room_six is 72.2, unchanged (local max in round 1).
  - `python3 report.py` prints the table from cloud_results/.
  - The Indeedee-vs-Trick-Room-Rillaboom head-to-head on the box was offered but never run (no answer before the power-off).

### Sequential testing + sharpening pass (built 4:20 pm Oct 4, NOT run yet: user said build, don't start)
**The rule** (`climb.SEQ`, all future rounds), per candidate swap after the confirm batch:
- **Move** if pooled gain - 2·SE > 0.
- **Drop** if gain + 1·SE < +2 points.
- **Otherwise** add a batch of 240 fresh paired games for it and the current team, up to 8 batches in all.
- **Why:** the old rule (best of 3 at > 1 SE) accepted a no-effect swap ~40% of the time and couldn't see gains under ~4 points.
- **Env:** `TS_SEQ_Z`, `TS_SEQ_ZDROP`, `TS_SEQ_DELTA`, `TS_SEQ_BATCH_PJ`, `TS_SEQ_MAX`.

**`python3 climb.py sharpen`** is a one-off pass on the existing state:
1. Re-test each start's latest move if it was marginal (gain - 2·SE ≤ 0; 20 of them). Revert it if it's clearly not worth 2 points, and let that start climb again.
2. Re-test the confirmed near-misses of stopped starts (34), and move where one is now clearly better.
- Batch 0 = the original confirm games, read from the runs/ cache. Extra batches use seeds from 900000. Log: `climb_sharpen.jsonl`.

**Test:** `test_sharpen.py` uses a fake evaluator (no battles). A true +4-point swap is accepted after 2 batches; no-effect swaps are dropped after 2–3. A dry run over the real AWS state: about 60k extra games, about 1 h on a c7a.48xlarge.

**Running it next AWS session** (after setup and smoke test):
1. Upload the AWS results as the live state: `rsync -az cloud_results/{climb_state.json,climb_log.jsonl,climb_prefilter_r*.json} BOX:champions-sims/teamsearch/` and `rsync -az cloud_results/runs/ BOX:champions-sims/teamsearch/runs/`, so batch 0 and screening come from cache (about 1 GB of out_* files, a few minutes to upload; starts/grid get rebuilt).
2. `TS_BATTLE_BIN=$PWD/../native/champ/bin/champ-battle-v3 TS_PARALLEL=60 TS_THREADS=3 ../.venv/bin/python3 climb.py sharpen` in tmux.
3. Then `cloud/auto_rounds.sh <cap epoch>` (rounds now use the sequential rule), with the watchdog as before.

### Sim vs real archetype matchups (Oct 4, 4:40 pm)
- **Real data:** `regmatch/f19{2,3,4}.json` = pokedata.ovh standings JSON for Baltimore/Brisbane/Frankfurt (`https://www.pokedata.ovh/standingsVGC/00001NN/masters/00001NN_Masters.json`). It has every player's team sheet and every round's opponent and result: 2,531 sheets, 10,373 matches.
- **`archmatch.py [--regionals]`:** real (ladder replays or regionals; Bo3 match rates converted to per-game) vs sim (all cloud_results battles) archetype × archetype. Log-odds gap = our-archetype offset + opponent-archetype offset + residual.
  - Both sources agree that Perish opponents are far too easy in the sim (76% vs 48%) and Rain vs Trick Room is too kind to rain (71% vs 47%, about 4 SE). Snow and Rain opponents are too hard.
- **`dig.py`:** 48 logged games (dig/*.json). Findings:
  1. The Perish AI rarely sings, Gengar switches out (losing Shadow Tag), and it spams Protect.
  2. Delphox-led "TR without Indeedee" pairs (about a quarter of that archetype) never set TR, because the setter Sinistcha is in back.
  3. Frequent double Protects on both sides.
  - Theme: the one-turn planner misses multi-turn plans, which flatters immediate-damage cores (the climb's Delphox + Scarf Garchomp + Incineroar leaders) and underplays setup archetypes (TR, Perish), likely including the user's Trick Room six. Sent to the other thread (planner owner).
- **Turn-1 audit** (`t1check.py`, existing outputs only): sim opponents' turn-1 clicks vs replay t1 rates for the same lead pairs. Mean total-variation distance 0.53.
  - Sim under-uses setup (Tailwind 4% vs 22%, Follow Me 18 vs 40, Aurora Veil 27 vs 41, Floette Calm Mind -44) and Sleep Powder (Venusaur -43). Fake Out and TR are confounded: our side was always the TR six (Armor Tail).
  - Theories sent to the other thread: setup undervalued by the one-turn horizon; sleep undervalued by egvalue's weak status weights; weather offense overvalued and no weather wars.
  - To unconfound: rerun with non-TR teams on our side.

### New sim setup from the other thread, and the climb re-check (Oct 5, prepared, NOT run)
- **Recommended setup:** `champ-battle-v8` + `DP2=1` (two-turn check of a second Protect) + `RACE=1 CALC_DATA=../native/champions_data.json` (damage-race value features) + `egvalue7.json` (sleep/paralysis/burn/Tailwind weights from 4,496 real Bo3 games) + anticipation. Details in ../HANDOFF.md, "Double Protect, real-game value weights".
  - Sim double-Protect rate fell from ~35% to ~26% (real 5.5–10%); sleep/setup use barely moved.
- **`evaluate.py`:** `TS_SIM=v3` (default; what AWS rounds 1–4 used) or `TS_SIM=v8`. Non-default setups write `out_<sim>_<seed>_<pj>`, so caches never mix. `climb.py` no longer pins the binary per round; it follows `TS_SIM`.
- **`simcmp.py`:** replays 10 teams' cached confirm games (same six, brings, 240 seeds) under v8 and prints rank changes vs the v3 results in cloud_results. About 2,400 games, ~30 min at 10 cores. `--report` prints what exists without running.
- **If v8 is adopted:** run the sharpening pass and later rounds with `TS_SIM=v8`, and build v8 on the box (`cloud/pack.sh src_battle_v8.tar.gz`, `remote_setup.sh src_battle_v8.tar.gz`). The v3 results then serve only as the pre-filter's training data; scores aren't comparable across setups.
- **Ideas sent to the other thread:** classify remaining double Protects (doomed/slower/HP); continue the damage race past a KO with bench replacements (prices switching, sacks and sweeps); a margin in the DP2 check; split the boost feature; a two-turn "investment check" that promotes setup moves.
- **Comparison run done (Oct 5, 2:17 am; `simcmp.json`, `simcmp.log`):** 10 teams × 240 games, same six/brings/seeds, v3 → v8.
  - Ranks: Frankfurt-10 1 → 1 (79.5 → 73.2); Baltimore-12 3 → 2 (77.4 → 72.9); trick_room_six 4 → 3 (72.2 → 65.7); Frankfurt-05 2 → 7 (78.4 → 61.1); Frankfurt-09 6 → 10 (68.5 → 50.2); low_variance_six 10 → 8 (52.4 → 60.8); Frankfurt-15 9 → 5 (58.7 → 63.8). Rank correlation ~0.55.
  - Opponents got harder mainly in Sun (-15.5), Indeedee TR (-11.8) and Snow (-8.6).
  - Caveats: moved teams' v3 scores are selection-inflated; brings were chosen under v3.
  - Conclusion: results depend on the sim version. Rerun the climb under the settled sim rather than sharpen the v3 results.
- **Sessions (Oct 5):** this thread is "Team search"; "Battle sim" owns native/champ + egvalue + replay analysis; "TR sheet" owns the published sheet.
- **Sim vs real regionals, v3 vs v8 (Oct 5; analysis only, the 10 simcmp teams):** per opponent archetype, the 10 teams' sim win rate vs the real regional per-game rate for teams of the same archetypes, after removing each sim's overall offset (v3 +0.75, v8 +0.53 log-odds; our teams are climbed). The RMS gap is about the same: 0.37 → 0.36 log-odds, about 9 win-rate points; the sim-side noise floor is about 0.14. Closer: Tailwind, Rain, TR w/o Indeedee, Rain+Sun. Further: Sun (0.00 → -0.43, now too hard), Indeedee TR, Snow, Balance, Sand. Perish is unchanged and still the biggest error (+0.82; raw 78% sim vs 48.5% real). The full archmatch (all cells, residuals) needs v8 battles from many teams, so it waits for the climb rerun.
- **mx/ is a dependency of TR sheet's sheet kit (Oct 5):** sheetkit/ calls `pool_mine` + `grid_pool.cell()` read-only (cwd mx/, its own POOL_FILE, cells written under sheets/<team>/work/grid/). Before changing what a cell computes (matchup.py, pool_mine.py, grid_pool.cell, foes.json), message "TR sheet" first.
- **Trick Room six update (Oct 5):** the user moved Torkoal back to Quiet 32 HP / 32 SpA / 2 SpD (was 12 / 32 SpA / 22 SpD since Oct 2). `teams/trick_room_six.json` is updated, so the start now uses Torkoal#1, which already has grid cells. The real six is `sheets/trick-room-six/team.json`, owned by TR sheet. `build_sets.py` now keeps grid ids that are no longer used, e.g. Torkoal#8, because old results name them. The v3 results for trick_room_six used the old spread.
- **Perish from real data (Oct 5, user):** Perish lines are long and specific, so the sim plays them badly, and Perish is a small part of the meta (3.3% weight). With `TS_PERISH=real`, the 6 Perish jobs are skipped and Perish trap is scored at the real regional per-game rate for our team's archetype vs Perish (`perish_stock.py` → `perish_stock.json`; 1,115 matches; shrunk toward the pooled 47.5% with a 30-match prior; 44.9% for Snow up to 53.0% for Sun).
  - Perish is the last archetype, so the other 54 jobs keep their indices and paired seeds. Starts go to `starts_*_live.jsonl`. `climb.paired` adds the fixed Perish shift (non-zero only when a swap changes the team's archetype).
  - Use it for the climb rerun. It also saves 10% of the battles. Tested with fake battles: read, search, paired and run_team.
  - `cloud/pack.sh` now also bundles every `pssim/egvalue*.json` and `pssim/pro_replays.py` (the archetype classifier).
- **Decomposition of v3 → v8 (Oct 5, 3:48 am; `decomp.py`, `decomp.json`; Battle sim's request):** the 10 simcmp teams against Sun / Indeedee TR / Snow only, same games. Setups: A = v3, B = + status weights (egvalue6b), C = + race (egvalue7 + RACE), D = + DP2 = v8.
  - Win share A → B → C → D: Sun 67.4 → 61.6 → 52.2 → 51.9; Indeedee TR 69.6 → 68.0 → 56.2 → 57.8; Snow 67.1 → 65.4 → 58.2 → 58.5.
  - The race is the main step; DP2 does nothing. Opponents get Trick Room up more under the race (Sun 45 → 51%, Indeedee TR 29 → 38% by turn 3), but Snow never sets TR and still drops 7, so the effect is broader than TR.
  - A run of only these archetypes' jobs reproduces the full run's games exactly (seeds key on arch, k, g). Setups 'v8b' / 'v8c' are in evaluate.SIMS.
- **Race by side, v12 (Oct 5, 4:58 am; `decomp.py v12ro v12rt v12 v12nr` → `decomp_v12ro_v12rt_v12_v12nr.json`):** same games as the decomposition; egvalue8 vs egvalue8_norace, set per side with EG_VALUE / EG_VALUE_B (setups in evaluate.SIMS).
  - Win share, neither / ours / theirs / both: Sun 61.4 / 62.5 / 51.3 / 58.7; Indeedee TR 65.3 / 65.2 / 43.8 / 52.7; Snow 62.8 / 62.4 / 58.7 / 61.8.
  - The race helps the archetype opponents, above all Indeedee TR (TR up by turn 3: 30 → 36%).
  - Our side gains from it only when the opponent also has it. That may be anticipation predicting the opponent with our own value file; asked Battle sim.
- **Features run for a multi-team value fit (`feats_run.py`, started 4:58 am):** the 10 teams × 60 jobs × 4 games under v12 with BATTLE_FEATS=1, seed 610000. Output folders are listed in `feats_run_dirs.txt`. Thread counts for both scripts come from `decomp_threads.txt`.
  - **Done:** two passes, 2,400 games each, all with top-level 'feats'. The v8 pass (4:58 am, by mistake: simcmp sets TS_SIM=v8 on import) is in `feats_run_dirs_v8.txt`. The v12 pass (5:52 am) is in `feats_run_dirs_v12.txt`.
  - Battle sim's finding from the v8 pass: egvalue8 rates our teams ~14 points too low. Slopes transfer across teams; the intercept doesn't. egvalue9 will have pooled slopes plus a general intercept and per-team intercept files.
  - Next: `intercept_test.py` (general vs own intercept; its general arm is also the bar run, `simreal.py v8 v12g`).
- **egvalue9 checks (Oct 5, 7:06 am; `intercept_test.py`, `simreal.py v3 v8 v12g v12t`):** pooled slopes over 11 teams; general intercept +0.54; per-team files in pssim/egvalue9_teams/.
  - General vs own intercept, 10 teams × 2,400 games per arm: mean |diff| 2.1 points (about 1 SE), χ² p ≈ 0.16, rank correlation 0.90. The general intercept is fine for the climb.
  - Sim-vs-real RMS without Perish: v3 0.26, v8 0.25, v12g 0.26. Unchanged.
  - The structural pattern persists: Rain, TR w/o Indeedee, Indeedee TR and Rain+Sun come out 0.3–0.4 too hard; Tailwind and Balance 0.25–0.33 too easy. The rough floor of this bar is ~0.15–0.2.
  - Proposed climb setup: TS_SIM=v12g (champ-battle-v12, egvalue9, RACE, DP2, anticipation) + TS_PERISH=real. Waiting on Battle sim to call it final.

### Climb rerun under the final setup (prepared Oct 5, 7:20 am; not started — the user launches the box in the daytime)
- **Setup:** `cloud/run_env.sh` = TS_SIM=v12g (champ-battle-v12, egvalue9 general intercept, RACE, DP2, anticipation; Battle sim called it final) + TS_PERISH=real.
- **Starts:** 52. The 48 regional top-16 teams, trick_room_six (Torkoal back to 32 HP), low_variance_six, and two earlier finals from `teams/climb_finals.json`:
  - Baltimore-12-final: #1 of the 10 under v12g.
  - Frankfurt-10-final: v3's #1.
  - `build_sets.py` adds them to the start index.
- **Fresh climb on the box:** `pack.sh` leaves out `cloud_results/`, `regmatch/`, `bring/previews.json` and every `climb_*` file. The bundle is ~2 MB and defaults to src_battle_v12; its checksum line was added by Battle sim.
- **Results home:** `pull_loop.sh HOST KEY cloud_results/v12`, so the first climb's tracked results stay put. Then `report.py cloud_results/v12`.
- **Smoke test:** `cloud/reference_v12g.json` = `evaluate.py trick_room_six 1 0` on the Mac under run_env: 54 games, score 0.5667, 6.1 s per game per core. The box must match it exactly.
- **Script changes:**
  - `relaunch.sh` and `auto_rounds.sh` source run_env.sh; `auto_rounds.sh` takes seconds per climbing start (default 210).
  - `watchdog.sh` takes MAX_H as its second argument.
  - `climb.py` takes TS_CACHE_DIR for the pre-filter cache, used by sandbox tests.
- **Plumbing test (7:19 am, sandbox, 1 start, test mode, ~400 games):** the round ran under v12g. Brings covered 9 archetypes (no Perish), sequential testing ran an extra batch, and state was written only to the sandbox.
- **Size:** round 1 ≈ 155k games ≈ 2.5–3 h on a c7a.48xlarge. Spain is ~$1.16/h if its quota is granted; otherwise Ohio zone 2b, ~$2.44/h.
- **Rerun launched (Oct 5, 1:58 pm):** Ohio c7a.48xlarge spot, Ubuntu 24.04. Spain had no spot capacity; Ohio didn't at first either. Root volume grown 8 → 40 GB live (growpart + resize2fs); the default 8 GB is too small, since start files take ~15 KB per game.
  - Smoke test: 54/54 jobs identical to the Mac reference (0.5667).
  - Round 1 thorough on 52 starts at 60×3 threads in tmux `climb`.
  - Watchdog: 12 h cap (start epoch in ~/start_epoch on the box). auto_rounds.sh runs later rounds up to the same cap.
  - The Mac pull loop copies to `cloud_results/v12`.
- **Box lost (Oct 5, ~2:30 pm):** unreachable from 2:30 pm, most likely a spot reclaim; capacity had been scarce at launch.
  - TR sheet was sharing it at 96 threads, from 2:17 pm, at the user's request.
  - Saved on the Mac in `cloud_results/v12`: 19,629 screening games, up to round 1's 100/668 teams, plus the pre-filter cache.
  - To resume on a new box (launch with 40 GB storage), after setup and the smoke test: `rsync -az cloud_results/v12/runs/ BOX:champions-sims/teamsearch/runs/` and `rsync cloud_results/v12/climb_prefilter_r1.json BOX:champions-sims/teamsearch/`, then start round 1 as before. Finished jobs are reused; start files are regenerated identically.
- **Relaunched in Spain (Oct 5, 4:08 pm):** eu-south-2 c7a.48xlarge spot, 40 GB root, that region's own key pair. The Ohio box's spot request status was `instance-terminated-no-capacity`, i.e. AWS reclaimed it.
  - Smoke test 54/54 identical.
  - Restored the 19,629 saved screening games and the pre-filter cache; round 1 resumed at 100/668 screening teams.
  - The climb runs at 32×3 while TR sheet uses the other 96 threads (tmux `trsheet`; expected done ~7:20 pm).
  - Watchdog 12 h cap from 4:08 pm; auto_rounds up to the same cap. The pull loop goes to `cloud_results/v12`.
- **Switched to v13 (Oct 5, 5:20 pm; Battle sim's amendment):** champ-battle-v13 + RACE_TIES=avg. v12's race gave side 0 every Speed tie, which favoured sixes on common Speed numbers. Setup `v13g` in evaluate.SIMS; `cloud/run_env.sh` now sets TS_SIM=v13g.
  - The v12g round 1 was stopped at about 240/668 screening teams; its outputs stay on the box and in `cloud_results/v12` as out_v12g_*.
  - Round 1 restarted from scratch under v13g at 32×3. TR sheet also restarted on v13, at 96 threads.
  - v13 was built on the box with the new `cloud/build_battle.sh`: build only, no package reinstall.
  - New Mac reference `cloud/reference_v13g.json` (0.5762; 53 of 54 jobs identical to v12g). The box matches it 54/54.
  - The results folder on the Mac is still `cloud_results/v12` (now v13g outputs too).
- **v14 (Oct 5, ~6 pm):** plays exactly v13's games, about 25–39% faster. Built on the box (mimalloc on); the smoke test against the v13 reference is 54/54 identical.
  - Setup `v14g` in evaluate.SIMS. `cloud/run_env.sh` picks v13g while there's no climb_state.json (round 1) and v14g after, so the climb switches at the round boundary and a mid-round relaunch keeps its round's cache. Outputs are tagged by setup.
  - TR sheet uses the same v14 build.
- **Shared-box incident (Oct 5, 5:59 pm):** we shared one tmux server, whose process title is the command of whichever session created it. TR sheet's `pkill -f 'sheetkit/kit.py ...'` matched the server and killed the climb's session; later my `pkill -f "[c]limb.py round"` killed theirs the same way.
  - The climb resumed from cache both times.
  - Fixes: the climb now runs on its own tmux server (`tmux -L climb`, in relaunch.sh, auto_rounds.sh and the README), and auto_rounds takes P×T from `cloud/threads.txt` ("32 3" while sharing). TR sheet moved off tmux to setsid nohup.
- **v16 (Oct 5, 7:20 pm):** the same games again, ~2.3x faster than v14. Built on the box; a fresh 54-game run (tag v16g) matches cloud/reference_v13g.json 54/54.
  - Round 1 finishes on the v16 binary under its v13g tag: `TS_BATTLE_BIN` overrides only the binary, so the round's cache stays valid.
  - From round 2 the setup is v16g (`cloud/run_env.sh` keys on climb_state.json). v14g is no longer used.
  - Relaunched at 32×3 with round 1 screening at 210/668.
- **Third box (Oct 5, 10:06 pm):** the second Spain box (c7a.48xlarge) went unreachable after 8:59 pm in round 1's batch 6, again presumably reclaimed. The new box is a Spain c7a.24xlarge (96 cores), Ubuntu 26.04, root grown to 40 GB, v16 built. Smoke 54/54.
  - Round 1 resumed from the pulled outputs (all 108,216 screening games plus confirm and batches 1–5) at 30×3, with `cloud/threads.txt` "30 3".
  - New watchdog 12 h cap from 10:05 pm. auto_rounds uses 420 s per climbing start for the smaller box.
  - Provisional round 1, replayed from saved games with the scratch replay (run_team/run_jobs read-only, max 6 batches): 32 moves, 6 stops, 14 undecided.
    - Scarf Garchomp is the most common swap-in (9), then Kingambit (6).
    - trick_room_six scores 66.2, #2 of 52 starts; its best swap is Indeedee-F → Gholdengo (+3.3 ± 1.4).
- **Opponent-pool validation (Oct 6, queued 2 am; Battle sim's real-game pool, the user approved the work):** `poolbar.py`.
  - The 10 simcmp teams with their climb brings per rule archetype play 2,500 rating-weighted pool entries, one game each, with the same entries for every team.
  - Plus the archetype-model baseline under the same setup.
  - Scored as our sim win share vs each group against the field's real per-game rate vs it, with the offset removed: by rule archetype (regionals) and by core-rule group (group_real regional and ladder).
  - Setup v17g: v16 games with the 256-bit callback mask, needed for engine_data_full.json; v16 panics on it.
  - On the box, `~/run_poolbar.sh` waits for the climb to end, runs it at 90 threads, writes `poolbar_report.txt`; `~/copy_poolbar_report.sh` then copies the report into runs/, so it arrives at `cloud_results/v12/runs/poolbar_report.txt`.
  - The box watchdog was restarted with the renamed-battle pattern.
- **Climb rerun finished (Oct 6, 2:20 am): 5 rounds; every start is at a local max** (`python3 report.py cloud_results/v12`). Scores are each team's latest confirm win share.
  - Top: Frankfurt-10-final 70.4 (Basculegion, Delphox*, Garchomp, Incineroar, Kingambit, Raichu*).
  - Then Frankfurt-04 69.5 (Charizard*, Delphox*, Garchomp, Gholdengo, Incineroar, Kingambit).
  - Then Baltimore-11 69.3 (no swaps: Aerodactyl*, Charizard*, Farigiraf, Garchomp, Kingambit, Sylveon).
  - Then Baltimore-12-final 68.2 and Frankfurt-10 67.5 (both Archaludon + the core).
  - Convergence: 4 starts sit within one species of Charizard-Y + Delphox + Garchomp + Incineroar + Kingambit.
  - Most added: Scarf Garchomp (always the Adamant Choice Scarf set, Garchomp#1), Kingambit, Mega Charizard Y. Most removed: Sneasler.
  - trick_room_six 58.3 after Indeedee-F → Gholdengo and Kingambit → M-Froslass; low_variance_six 50.3, no swaps.
  - `report.py` was fixed on Oct 6 to use the sequential verdicts and the state; earlier printouts showed undecided swaps as moves.
- **Opponent-pool validation: PASS (Oct 6, report run on the Mac at 4 am; `poolbar_report_v17g.txt`).** Same 10 teams, brings and setup (v17g); only the opponents differ.
  - By rule archetype, against the field's real regional rate: RMS gap **0.29 → 0.18** without Perish, and 0.41 → 0.20 with it. Perish +1.21 → +0.37, Rain −0.51 → −0.33, Sun −0.35 → −0.22, Indeedee TR −0.33 → +0.09, Balance +0.32 → +0.13.
  - By core-rule group: RMS 0.23 vs regionals (19 groups), 0.15 vs ladder (12 groups).
  - The box run used 30 processes × 3 threads: one 90-thread process ran ~6x slower per game. Battle sim's v19 should remove that lock contention; not yet measured.
  - The report needs `regmatch/`, which isn't bundled, so `poolbar.py report cloud_results/v12/runs` runs on the Mac.
- **Sixth slot for the converged core (Oct 6, 3:10 am; `sixth.py`, `sixth_result.json`):** core Delphox, Scarf Garchomp, Charizard Y, Sitrus Incineroar, Sash Kingambit; 8 batches × 216 paired games each.
  - Archaludon 69.1, Gholdengo 67.0, Rillaboom 64.0. Gholdengo − Archaludon −2.1 ± 1.6; Rillaboom − Archaludon −5.1 ± 1.7; Rillaboom − Gholdengo −3.0 ± 1.1.
  - Archaludon's edge is Rain (72.9 vs 28.8 / 11.6) and Rain+Sun. Gholdengo is better vs Indeedee TR (60.7 vs 43.8) and TR (74.2 vs 61.7); Rillaboom vs Snow.
- **Perish source decision (Oct 6):** archetype-model climbs keep `TS_PERISH=real` (models' Perish gap +1.21). A pool-based climb scores Perish from the pool's sim games (gap +0.37, in line with Rain −0.33 and Snow's under-rating), so team-specific Perish answers count.
- **Pool-based climbs built (Oct 6, 11:30 am; `poolmode.py`, `TS_OPP=pool`):**
  - The user chose two pool-based climbs, with the miss rule (v20m) and without it (v20g, the control), and brings per core group.
  - Bring groups: the 28 core groups with ≥1% of regional sheets and ≥8 pool entries ('other' split by rule archetype), 96% of the meta, weighted by regional share (`pool_keys.json`, aggregate counts only).
  - Screening: per group, the outcome model's top 3 brings (against the group's species profile from its entries) × 2 entries; the best bring is kept. Confirm: 8 entries per group per batch, one game each.
  - Entries are drawn per (group, seed): the same for every team in a batch, new each batch. Full engine data, SEED_PER_JOB=1. Perish is played.
  - `climb.paired` weights jobs by `w_job`. Env files `cloud/run_env_pool.sh` and `cloud/run_env_poolmiss.sh`; relaunch and auto_rounds take RUN_ENV, CLIMB_SESSION and CLIMB_LOG, and kill only their own climb's processes.
  - Plumbing test passed: one start, test mode, v20m. References: `cloud/reference_v20m.json`, `cloud/reference_pool.json`.
- **Pool climbs running (Oct 6, 3:28 pm; Spain c7a.24xlarge, 96 cores, 15 x 3 each; results pulled to `cloud_results/pool`):**
  - Smoke tests matched the Mac exactly (v20m archetype 0.5788, pool path v20g and v20m 0.5594, per job).
  - 90-thread check for Battle sim: v20 in one process with 90 threads ran 2.64 s/game vs 2.53 s at 30 x 3; v17 ran 24.2 s/game in one big process.
  - Bugs fixed on the way: `poolmode._run` set TS_ENGINE_DATA / SEED_PER_JOB in os.environ, and the climb's team threads raced on it: one team ran on spot data, errored, and crashed the control. Now passed per run (`run_jobs(extra=)`). tmux `-t climb_pool` prefix-matched `climb_poolmiss`, so relaunching the control killed the miss climb: targets are exact now (`=name`).
  - **The user's plan:** the control runs round 1 only. If it looks like the finished climb's round 1 (`roundcmp.py`; calibration: the first AWS climb vs the rerun agreed on 30/50 verdicts, 12/25 same set in, Spearman 0.70), only the miss climb continues, with the whole box (`cloud/threads_climb_poolmiss.txt` = `30 3 90`). After round 1, run `misscheck.py` on the miss climb for degenerate miss-reward strategies.
  - **What the user wants from the miss climb:** a team that's fun to play. Does the M-Delphox + Scarf Garchomp core (Heat Wave / Rock Slide 90%, 80% under the rule) stay on top with misses doubled, or does another core win? At the end, play the core head to head against the miss climb's top teams under v20m, including the core with Solar Beam Charizard Y (`M-Charizard Y#5`) in place of Hurricane.
  - **Swap-pool quirk (left as is, user's call):** `build_sets.modal_set` takes the most common nature first, then moves. That made the only Charizard Y candidate the Timid Hurricane set (`M-Charizard Y#2`), which at the regionals was run only on dual-weather teams (34/34 with a rain setter; sun-only teams ran Solar Beam 43, other 26). Indeedee-F's candidate (`#2`) has Protect, not Trick Room (19 vs 27 sets). Matrix cells already exist for `M-Charizard Y#5` (Timid, Solar Beam) and `Indeedee-F#1` (Trick Room) if a later climb adds them.
- **Hurricane vs Solar Beam Charizard Y (Oct 6, 6:05 pm; `hurricane.py`, `hurricane_result.json`; old setup v16g + real Perish, on the Mac at 5 x 2):** the rerun's best teams with `M-Charizard Y#2` vs the same teams with `#5` (Solar Beam, same Timid spread), own bring search each, 6 paired batches x 216 games.
  - Solar Beam minus Hurricane, pooled over 7 teams: **+0.8 ± 0.4**. Baltimore-12-final +2.8 ± 1.0, Baltimore-14 +1.5, sixth's core + Archaludon +1.3, Frankfurt-10 +0.9, Baltimore-08 +0.9, Frankfurt-04 −0.7 ± 0.6, Brisbane-01 (dual weather, Pelipper) −1.0 ± 1.8.
  - It comes from Rain: with Solar Beam the bring search starts bringing Charizard against Rain (Drought overrides rain, then Solar Beam hits the Water types). Elsewhere the third move barely matters. Some per-archetype swings are the two versions' bring searches picking differently (e.g. Baltimore-12-final vs Rain + Sun −13.7).
- **Round 1 of both pool climbs (Oct 6, 8:25 pm miss / 8:35 pm control):**
  - Miss climb degenerate check (`misscheck.py`): none. Inaccurate moves per team 3.44 → 3.25; Stomping Tantrum sets 10 → 11; Compound Eyes 2 → 1. It continues.
  - **The control does not look like the old climb's round 1** (`roundcmp.py`): verdicts agree 26/52, same set in 4/20 where both moved, Spearman 0.60 (the calibration between the two archetype climbs was 30/50, 12/25, 0.70). Scarf Garchomp came in once (old climb: 9 times); the control brings in Golisopod, Basculegion, Froslass, Staraptor, Milotic. The miss climb shows the same pattern, so that shift comes from real opponents, not the rule. Control vs miss: 24/52, 5/15, Spearman 0.71.
  - So, by the user's rule, the control continues (user, 8:40 pm), both at 15 x 3 from round 3 (the miss climb's round 2 started at 30 x 3). The watchdog cap and auto_rounds CAP moved to 3:28 am (12 h); the Mac pull loop was restarted to outlast it. Stage 1 refinement (`refine.py`) runs after the miss climb converges, probably on a new box.
- **Hold batch in the sequential test (user, Oct 6, 10:45 pm; `climb.SEQ['hold']`, on from round 4 of both pool climbs and in `refine.py`):** a candidate that clears gain − 2 SE > 0 gets one more fresh batch and moves only if that batch's gain is positive and the pooled gain still clears; otherwise it stays undecided. Prompted by Frankfurt-11's Farigiraf set swap (#55 → #1) passing at +14.4 ± 5.2 on one batch: Farigiraf was in every bring, so not bring luck; one-game-per-entry pool batches are noisy (a one-set change alters ~1/3 of the games). Simulated on fake paired batches: a no-effect candidate is accepted 8.0% → 3.5% of the time; +3 points 63% → 56%; +5 points 93% → 89%; about one extra batch per accepted swap. `TS_SEQ_HOLD=0` restores the old rule.
- **Both pool climbs converged (Oct 6, 11:59 pm miss / 12:04 am control), then stage 1 refinement (Oct 7, 12:00–1:44 am, `cloud_results/pool/climb_refine/`, `round_refine.log`):** the old climb's core (sixth.py's team) changed Archaludon Bold → Modest (+5.8 ± 2.1) and Kingambit Focus Sash → Black Glasses Swords Dance (+6.3 ± 3.0), but on the same opponents it scored 52.6 vs 57–62 for the miss climb's top teams. The Solar Beam Charizards screened +0.9 / −0.8 and were not confirmed.
- **The user's verdict:** the pool climbs' teams are "individually strong Pokemon with terrible synergy". Niche counters are welcome; artificial caps are not (they regress to the meta). Hypotheses: one-swap search can't build or keep synergy packages (Brisbane-12 dismantled its Trick Room plan piece by piece), and/or the sim undervalues coordination. Battle sim was asked (Oct 7, 2 am) about planner gaps for multi-turn coordination.
- **Next (daytime box): `synergycheck.py`** (steps in cloud/README.md): 30 real teams' plan enablers swapped for generalists vs control swaps, v20g pool, 4 batches. Its plumbing test on the Mac ran the bring search and part of the confirm games, then the Mac slept; run `TS_SYN_TEST=1 ... synergycheck.py run` on the box first to check the summary step. If the sim prefers broken plans, it's an evaluator problem (Battle sim); if breaks clearly hurt, build package swaps (pairs/trios that co-occur on real teams).
- **Battle sim's evaluator tests (Oct 7, its HANDOFF):** a value refit on 27k real positions, a smaller Protect charge, and a two-turn horizon (champ-battle-v21, BATTLE_HORIZON=2: +0.2 ± 0.9 over 4,800 games) all changed nothing in self-play; climbs stay on v20g / egvalue9. Rating-matched real rates (ladder 1200–1350) vs the sim's pool-vs-pool rates: Rain +9 overrated, Tailwind +5, Sun +2, Snow +2, Sand −2, Indeedee TR −3, Balance −4, Trick Room −6 (vs regional top cut: Rain +7, Trick Room −10). So the real biases are Rain too strong and Trick Room too weak; "Sun overrated" and "Snow strongest" were mostly rating artifacts. Expect the synergy check to undercharge Trick Room enabler removals by ~6–10 points and overcharge Rain pieces by ~7–9. Trick Room players gain over the planner when Trick Room is down (switches, setup, priority).
- **The bring step is the leak (Oct 7, with Battle sim):** replaying 2,094 real ladder pairings from the players' own leads and brings, the engine plays Rain and Trick Room about right (Rain −0.3, TR −3.2 ± 4.2). The pool-vs-pool Rain +9 / TR −6 came from the climb's brings. Brisbane-12's start vs real Torkoal + TR players against the same groups: setter leads 29% vs 65%, Torkoal brought 39% vs 63%. Causes: the bring model (`bring/fit_outcome.py`, fitted Oct 3 on champ-battle-v2 battles vs archetype models; features offense / defense / coverage / human log-prob, nothing for plans) puts a setter lead first against 14% of the meta; the 2-game screen keeps setter + Torkoal (always in the top 3) against 39%. `synergycheck.py` now also runs with human-typical brings (`TS_SYN_BRINGS=human`, `poolmode.human_ranked`).
  - Battle sim's suggestions for the next climb's bring step: refit the outcome model on pool-mode games with the current sim, with plan-enabler features (setter + abuser in the four, setter in the lead, Fake Out / Follow Me partner beside it); widen the screen to 8–10 games per candidate or drop it. `champ feats` / evalpos give a static or one-turn value of a start position without a full game.
  - Remaining engine-side bias (real pairings): Tailwind +8, Rain + Sun +11 over; Indeedee TR −7, Balance −5 under. Battle sim reads it as the equilibrium opponent undervaluing read-based lines (Follow Me, Fake Out into the obvious target, pivots): a design question for the user.
- **Synergy check results (Oct 7, 8:55 pm and 10:15 pm; `synergy_v20g_human.json`, `synergy_v20g_search.json`; Spain c7a.24xlarge):** 30 real teams' plan enablers swapped for generalists (87 breaks) vs a random non-enabler swap (30 controls), v20g pool, 4 batches × 224 games per version.
  - Overall, without the user's TR six: breaks −2.6 (human-typical brings) / −2.3 (the climb's bring search); controls −0.2 / −0.9. So breaking a plan costs only ~1.5–2.5 points more than an ordinary swap, under either bring method: the sim barely values plan enablers, which is why the climb trades them away.
  - By plan, breaks minus controls (human / climb brings): Sun −5.5 / −5.7 (valued both ways); Rain −6.1 / −1.2 and Tailwind −3.4 / +0.1 (valued only with human-typical brings: the climb's bring step loses them); Psychic Terrain +0.3 / −3.0; Sand +2.7 / +0.4; Trick Room (13 teams without the TR six) +2.0 / +1.3 (not valued either way).
  - The user's TR six: with human-typical brings, removing Indeedee-F scored +24 with any replacement: an imitation-model artifact (it brings Blastoise + Indeedee-F / Farigiraf + Incineroar and leaves Torkoal home; without Indeedee-F it brings Torkoal). With the climb's brings: −5.9 / +2.9 / −1.4, control −4.2.
  - Most "Trick Room" starts are Delphox goodstuff with Sinistcha as a back-line option (never led), so the TR line mostly isn't a test of real TR plans. A clean TR test: the user's TR six with the TR sheet's own bring plans (Oct 3: the sheet's picks 72.5% vs the fitted model's 60.1% vs imitation 48.6% in the sim).
- **Trick Room six with the TR sheet's own plans (Oct 7, 10:25 pm; `trsix_sheet.py`, `trsix_sheet_v20g.json`; plans from `sheets/trick-room-six/picks.json`, which never brings Indeedee-F: Farigiraf is the setter, led vs 82% of the meta):** the team scores 70.3 with the sheet's plans, against 61.9 with the climb's bring search and 42.9 with human-typical brings (different seed sets, ±3).
  - Keeping the plan and swapping the Pokemon: Farigiraf → Gholdengo −28.5 ± 2.8, → Garchomp −25.1, → Rillaboom −30.3; Torkoal → Gholdengo −6.8, → Garchomp −7.4; control Incineroar → Gholdengo −8.8 (Incineroar is a plan piece too). The fixed plan disadvantages the variants (the generalist plays the setter's slot), so −28 is an upper bound; with re-planned brings (the climb's) the same swaps cost −5.9 / +2.9 / −1.4.
  - Conclusion: the engine values and plays Trick Room fine from good leads; the leak is the bring/lead step. For this team, the climb's bring search costs ~8 points against the sheet and the imitation model ~27. The next climb's bring step should approach the sheet's both-sides-pick plans (or seed the shortlist with plan-aware candidates and screen with more games).
- **Plan-aware bring step built (Oct 7–8; `bringplan.py`, `poolmode.search_team_plan`, `TS_BRING_MODE=plan`; not yet validated in battles):** per opponent group, a shortlist of up to 7: the outcome model's top 2, the imitation model's top 1, the most common bring of real players with similar sixes (≥ 4 shared species; works for regional starts, rarely for unusual sixes), and one candidate per plan the six has (a Trick Room candidate per setter, Trick Room + Fake Out/redirection guard, Rain/Sun/Sand/Snow, Psychic/Grassy/Electric Terrain, Tailwind, support + setup), each the outcome model's best choice that puts the plan on the field and isn't listed yet. Screen: 7 × 2 games, then the best 2 × 6 more (different entries), the best over 8 kept: 728 games per team vs 168 (4.3x). Run dirs are named by a hash of their jobs.
  - Offline: the TR sheet's exact plan is in the shortlist vs 42% of the meta (old top 3: 30%), its four vs 65% (50%), its lead vs 56% (49%); Brisbane-12 gets a setter-lead candidate vs 100% of the meta (old 54%). Logic tested with fake battle results.
  - Validation, needs a box: `cloud/bring_validate.sh` (bringcheck.py: old vs plan-aware brings paired on the synergy teams, the TR six vs its sheet plans; then the synergy check with plan-aware brings). The climb log now records `bring_tags` (which shortlist source each chosen bring came from).
- **Plan-aware bring step, validation part 1 (Oct 8, 12:05 am; `bringcheck.py`, `bringcheck_v20g.json`; Spain c7a.24xlarge):** old vs plan-aware brings on the synergy check's 30 teams, 4 paired confirm batches each. Mean +1.0 (17 of 30 better, 3 significantly, none significantly worse). By plan: Rain +4.0 (Brisbane-09 +10.8 ± 2.8, Frankfurt-14 +7.6, Frankfurt-11 +6.3; Brisbane-06 −5.6), Sun +1.4, Sand +1.2, Tailwind 0.0, Trick Room 0.0, Psychic Terrain −0.6. Chosen brings came from the model 54%, human 12%, real players 12%, plan candidates 22%. The TR six: old brings −10.2 ± 2.7 vs its sheet's plans (68.5), plan-aware −6.8 ± 2.1, so the step recovers about a third of that gap. Part 2 (synergy check with plan-aware brings) waits for the next box.
- **Plan-aware bring step is on for the next climb (user, Oct 8):** `cloud/run_env_pool.sh` and `run_env_poolmiss.sh` export `TS_BRING_MODE=plan`. Round 1's bring search grows from ~112k to ~490k games (~2 h on 60 x 3 threads); auto_rounds needs a larger seconds-per-start (~900 at 60 x 3). The hold batch is on by default. The finished pool climbs (Oct 6–7) used the old bring step; don't resume them with these files.
- **Per-archetype climb built (user, Oct 8; `cloud/run_env_arch.sh`, `build_arch_starts.py`, `teams/arch_start/index.json`):** the user's goal is fun, strong teams per style, not one global best (global climbs converge on the same cores). Archetypes: Rain, Rain + Sun, Balance, Sand, Tailwind (user's choice); 32 starts (regional top 16 + next best placements to 6 each, + low_variance_six). `TS_ARCH_LOCK=1` keeps every swap inside the start's rule archetype (`climb.arch_of`, pro_replays.arch); `TS_POOL_WEIGHT=blend` weights opponent groups half regional, half ladder (30 groups); normal accuracy; plan-aware brings; hold batch. `TS_INDEX` selects the start index. A dry round with fake results (2 starts) ran clean. 12 new sets' cells computed. Not run yet: needs a box (~3–4 h on a c7a.48xlarge).
- **Per-archetype climb running overnight (user, Oct 8, 1:34 am; Spain c7a.24xlarge, 30 x 3, sharing the box with the plan-brings synergy check until ~2:30 am):** `climb_arch` session; auto_rounds stops starting rounds at 2:33 pm, the watchdog's hard cap is 3:33 pm; `cloud/after_arch.sh` runs `archverify.py` when the climb ends. Results copy to `cloud_results/arch` (the Mac's pull loop). If the box is reclaimed, resume on a new box by rsyncing `cloud_results/arch/runs` and the `climb_arch_*` files back.
- **Plan-aware bring step, validation part 2 (Oct 8, 3:00 am; `synergy_v20g_plan.json`):** the synergy check with plan-aware brings. Breaks minus controls (without the TR six; human-typical / old search / plan-aware brings): overall −2.4 / −1.4 / −2.3; Rain −6.1 / −1.1 / −4.6; Sun −5.5 / −5.6 / −6.3; Sand +2.7 / +0.3 / −2.2; Tailwind −3.4 / 0.0 / −1.4; Psychic Terrain +0.3 / −3.0 / −0.7; Trick Room +2.0 / +1.4 / +2.6. So plan-aware brings restore most of the Rain plan value the old step lost, add some for Sand and Tailwind, keep Sun; Trick Room stays unvalued here, but this check's TR line is a weak test (Sinistcha goodstuff teams; the TR six's chosen enabler is Indeedee-F, which its sheet never brings); `trsix_sheet.py` is the real TR test.
- **Per-archetype climb verified (Oct 8, 11:30 am; `archverify.json`):** 5 rounds, then each start's final team vs its start on fresh games (4 batches, same opponents for all, so scores compare across archetypes too). Best verified finals: Rain Brisbane-4 72.4 (+12.0 ± 2.7: Sneasler → M-Staraptor, Incineroar → Kommo-o); Rain + Sun Baltimore-2 68.8 (no swaps); Sand Frankfurt-47 64.8 (no swaps); Tailwind Brisbane-2 64.8 (no swaps); Balance Frankfurt-4 63.1 (+4.6 ± 2.3: M-Floette → Basculegion) and Frankfurt-1 63.0. The user's low_variance_six 52.4 → 62.4 (+10.0 ± 2.7, Sneasler → M-Staraptor). One accepted swap verified worse: Baltimore-5 Raichu Y → Kingambit −4.3 ± 2.6 (its start, 67.3, is the better team). Most starts never moved: the regional teams are already near-local-max in the sim. Accuracy refinement (`accrefine.py`) on each archetype's best 2 started 11:31 am.
- **Accuracy refinement (Oct 8, 11:31 am–12:55 pm; `accrefine.json`):** set-only swaps toward more sure-hit moves (`accrefine.sure_hit`: No Guard, Hurricane/Thunder with a rain setter, Blizzard with a snow setter, Toxic from Poison types, Compound Eyes, Wide Lens, Hustle), accepted when gain + 1 SE >= 0; 3 rounds on the 10 best verified teams (2 per archetype). Brisbane-4 already had 24/24 sure hits; Brisbane-9 had no candidates. Clear gains: Frankfurt-4 Sneasler Rock Tomb set → Focus Sash Fake Out / Poison Jab / Close Combat / Quick Guard (+5.2 ± 2.1); Baltimore-5 Milotic Hypnosis/Muddy Water/Coil → Scald / Icy Wind / Ice Beam / Protect (+4.7 ± 2.6), then Rillaboom → U-turn (+2.1), Milotic → Recover set (+1.3): 20 → 23 sure hits. Others about neutral; two Volcarona support → Quiver Dance swaps slightly negative (−1.4, −2.0). The run was stopped after round 3 (the box had to go by 1:05 pm), so **the final check (refined vs original on fresh games) did not run**; nor did the pair probe (`pairprobe.py`, 12 exact type recombinations listed). Both are queued for the next box.
- **Accuracy refinement final check (Oct 8, 9:18–9:42 pm, Spain c7a.24xlarge; `accrefine.py final`, `accrefine.json` totals):** refined vs original, same fresh games (seeds 85000/885000; the old 79000/879000 repeated round 3's games). Frankfurt-47 +5.7 ± 2.6, Baltimore-2 +4.2 ± 2.7 (62.7 → 67.2, 22 sure hits), Frankfurt-32 +2.4, Baltimore-17 +0.2, Frankfurt-4 −2.0, Baltimore-5 −4.0, Frankfurt-1 −6.0, Brisbane-2 −6.5 ± 2.4 (its one swap, Rillaboom High Horsepower → U-turn, measured +0.3 in its round). Mean −0.8: more sure hits cost nothing on average. **Run-to-run drift is large:** the same original teams scored up to 8 points below the afternoon's archverify (Frankfurt-32 67.2 → 59.6; Brisbane-2 64.8 → 69.1 the other way): winner's curse plus bring-search luck, which the ± (games only) leaves out. Compare teams within one run; the refinement rounds held brings equal, the final check searched both anew.
- **Pair probe (Oct 8, 9:42–10:06 pm; `pairprobe_exact_swap.json`):** all 12 exact type-preserving pair swaps lost (best −0.2 ± 2.8, Brisbane-7 M-Garchomp + Basculegion → Milotic + Dragapult; mean −6; the user: "most seem absolutely terrible synergy wise"). Not expanded (looser rules give 37 / 97 / 217 swaps, mostly the same kind). If pairs come back, build them from cores real players pair (Pelipper + Archaludon, Rillaboom + Incineroar), not from types.
- **Floette-Eternal is not recruitable for the user** (Oct 8), so the 24/24 sure-hit teams with it (Brisbane-4, Brisbane-2) aren't playable. 33 regional teams are 24/24 without it (15 Perish, 6 Rain, 5 Sun, 3 TR, 2 Snow, 1 Tailwind, 1 Indeedee TR); the user finds Perish unexciting. **The 6 Rain ones scored (Oct 8, 10:26 pm; `scoreteams.py`, `scoreteams_sure24_rain.json`, 6 batches, references in the same run):** Frankfurt-239 68.3 (Grimmsnarl, M-Swampert, Archaludon, Pelipper, M-Metagross, Indeedee-F), Brisbane-4 (ref, Floette) 68.2, Baltimore-2 refined (ref) 68.1, Frankfurt-156 67.3, Frankfurt-193 67.0, Brisbane-137 60.8, Baltimore-203 59.3, Frankfurt-163 56.6 (± 1.6 over games). The top three match the Floette team.
- **Battle sim's champ-battle-v22 (Oct 9, 12:xx am; commit e60101b, `native/champ/src_battle_v22.tar.gz`):** v21 plus mechanics card opponents hit (Purifying Salt, Mummy, Static, Snow Cloak, Own Tempo, Quick Draw, Surge Surfer, Dry Skin, Zero to Hero, Air Balloon, Quick Claw, Chesto / Rawst / resist berries, Light Ball, Metal Coat, Metal Burst, Mortal Spin, Hex, Rest, Salt Cure, Wish, Healing Wish) and Healing Wish / Memento users now faint. Flags off, it plays v20's games exactly except where those mechanics occur (62 of 2,400 pool games). Superseded the same night by **v23** (commit 729ccd0, `src_battle_v23.tar.gz`): v22 plus Baton Pass, Encore's override, Ally Switch, Gravity, Curse, Entrainment, Temper Flare, Shell Side Arm, Vital Spirit / Insomnia, Healer, Gooey, Curious Medicine, Seed Sower, Swarm, Electromorphosis, Ripen; planner and value untouched. Then **v24** (commit 6d633d2, `src_battle_v24.tar.gz`): v23 plus the Mega choice the user asked for. A stone holder's moves are offered with and without Mega Evolution, so the planner decides whether and when to evolve and, on two-stone teams, which holder does (`EG_MEGA_ALWAYS=1` restores the old always-evolve rule, making v24 = v23). Battle sim's test, 2,400 pool games: strength flat (+0.3 ± 0.6 for the choosing side); holders delayed the Mega in a third of games and the other holder took it in a fifth of two-stone games; about +20% cost per game while a stone is unused. **Results on teams with stones are no longer comparable with v20g.** Not adopted yet: runs that must compare with earlier ones stay on v20g (or v24 with `EG_MEGA_ALWAYS=1`); the next fresh climb takes v24 as its new baseline (pack with `cloud/pack.sh src_battle_v24.tar.gz` and add a setup for it). Battle sim notes the bring model's two-Mega penalty is less necessary under v24, since a two-stone four can use either stone; revisit it when the climb moves to v24 (`climb.megas` still caps a team at 2 stones).
- **The v27 climb is set up (Oct 13; not run yet).** Five regionals (Louisville from Victory Road's open team sheets, Recife from Limitless; `regionals/fetch_vr.py`, `fetch_event.py`), 40 starts = every regional's top 8 (`teams/top8_start`), archetype lock, Floette allowed, normal accuracy then a sure-hit pass, opponent weights from all five (`pool_keys_2026-10-12.json`). Setup v27 (Battle sim: the Oct 12 engine, full calc data, Mega choice free, h64 value net; `cloud/run_env_v27.sh`), seed keys on pool jobs and the cross-team game cache (`gamecache.py`; last climb had 24% repeat games), late-round thread spreading. Cells for 35 new sets: `cloud/cells_v27.sh` on the box. Smoke: `cloud/reference_pool.json` v27 / v27s.
  - **Style bias on real pairings (Battle sim, Oct 13, 2,094 games, humans' own leads and brings), sim − real:** sym2 (v27s) → net (v27): Rain +1.7 → +0.8, Sun +0.9 → +2.7, Trick Room −5.1 → −1.1, Indeedee TR −9.7 → −3.4, Tailwind +8.2 → +1.6, Snow +7.0 → +5.4, Balance −7.0 → −0.6, Sand +0.0 → −5.4, Perish −4.7 → −2.9, Rain + Sun +8.9 → −0.9 (each ± 2.5–5). RMS 6.4 → 3.0 (about sampling noise); agreement with the real winner 54.7% → 55.9%. The net removes the Tailwind-over / Indeedee TR- and Balance-under shape; Snow +5.4 and Sand −5.4 remain (1.4 SE). So the climb runs with the net.
  - **First start stopped (Oct 13, 2:15–2:17 pm):** round 1 began on v27 (Spain c7a.24xlarge; smoke tests matched the Mac exactly, the 35 cells were computed), then the user chose to wait for Battle sim's v28: the value features (race, vfeats, bench edge, archetype threat) used each move's raw listed accuracy, missing No Guard, rain Hurricane / Thunder, sun, snow Blizzard, Compound Eyes, Hustle, Wide Lens and accuracy stages (the turn simulation itself was right); v28 fixes them and refits the h64 net. Box terminated. **To restart on v28:** add `v28` / `v28s` to `evaluate.SIMS` (same flags, seedkey, the new net file), make the Mac references (`cloud/make_reference_pool.py v28 v28s`), set `TS_SIM` in `cloud/run_env_v27.sh` (or a copy), pack with `src_battle_v28.tar.gz`, then setup, smoke, `cloud/cells_v27.sh`, and the launch as on Oct 13 (`climb.py round thorough climb_v27`, `auto_rounds.sh <boot + 18 h> 900`, `after_v27.sh`; all files in the bundle this time).
- **The v33 climb (Oct 14–15; `archverify_v33.json`, `accrefine_v33.json`):** 40 top-8 starts from five regionals, archetype lock, blended field. Round 1 on v33 (two seeds; the v34 binary from mid round, game for game identical), rounds 2–4 on one seed (v33n1); finals verified and the sure-hit pass on two seeds. The first Spain 24xlarge was reclaimed mid round 1; round 1 resumed on a 48xlarge from a game cache rebuilt from pulled runs (`rebuild_gamecache.py`). 13 of 40 starts moved; every start at a local max after round 4. **Verified (fresh games, two seeds), final vs start:** Frankfurt-5 Perish +16.3 ± 2.7 (Politoed → Kingambit; a weak start, 37.5 → 53.8), Brisbane-4 Rain +7.4 (Sneasler → M-Staraptor; 69.4, Floette), Louisville-1 Sun +5.7 (Farigiraf → Kingambit; 67.3), Brisbane-2 Tailwind +4.1 (Floette), Baltimore-3 +3.6, Recife-2 +3.5, Recife-5 +2.3, Baltimore-7 +2.0, Frankfurt-8 +1.6, Frankfurt-4 +1.1, Frankfurt-1 +0.2; worse: **Louisville-6 −5.9 ± 2.8 (M-Garchomp → a second rain setter, Politoed)**, Baltimore-5 −1.4. Highest verified finals: Brisbane-8 Rain + Sun 70.0 (unchanged), Brisbane-4 69.4, Louisville-4 Rain 69.1, Louisville-1 Sun 67.3, Baltimore-6 Snow 66.6. **Sure-hit pass** (accept if gain + 1 SE ≥ 0) again lost on fresh games overall: Baltimore-4 −8.6, Frankfurt-1 −7.6, Brisbane-5 −7.5, Baltimore-3 −6.6, Louisville-3 −4.7; held up: Frankfurt-2 +2.4 (21 → 24/24), Brisbane-8 +1.4 (21 → 22), Brisbane-4 +1.1 (23 → 24), Baltimore-6 +0.8 (22 → 23), Frankfurt-7 −0.1 (23 → 24). Small accepted losses add up: a stricter accept rule (gain ≥ 0) would suit the next pass.
