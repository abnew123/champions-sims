# TR sheet thread: handoff (2026-10-05)

On 2026-10-05 the user split the work in this repo into three Claude threads. This file is the starting point for the **TR sheet** thread.
The main `HANDOFF.md` at the repo root has the full history and every recipe; read its sections "Sheet Version 12" onward after this file.

| Thread (session name) | Owns | Does not touch |
|---|---|---|
| **TR sheet** (you) | The published sheet and everything that decides what is on it: `trsheet/`, `tr_leads.py`, `tr_rules.py`, the turn-one lead pipeline in `pssim/` (`t1sim.js`, `tr_final.py`, `run_jobs.sh`), the sheet's bring picks (`bringmx_*`, `bringcf_*`, `build_sheet_v*.py`), spreads, `recordings/` and game reviews, the 1v1 grid for the sheet (`mxtr/`) | `native/champ/src`, `egvalue*.json`, `teamsearch/` |
| **Battle sim** | The full-battle simulator and planner: `native/champ/` (Rust engine, `champ-battle-vN` binaries), the position value (`pssim/egvalue*.json`, `build_egvalue*.py`), replay analysis (`pssim/replays_protect/`, `protect_*.py`, `replay_feats.py`, `fit_real_value.py`, `elo_check.py`), planner tests (`dp_test*`, `ev*_test*`, `dplog*`, `dpfeats*`) | The sheet page |
| **Team search** | `teamsearch/` (hill climb for the strongest six; a thought exercise, exempt from the no-miss rule) | Everything else |

Talk to the other threads directly with SendMessage (names above); do not relay through the user. You use the battle sim as a tool: ask
**Battle sim** which binary, value file and flags are current before any large run, and tell it if results look wrong.

## The sheet now

- Published: https://claude.ai/artifact/Qufendyuq8b42JmB56XSc6, **Version 16**. Source: `trsheet/tr-sheet.html`. Backups `tr-sheet.v11.html` ... `tr-sheet.v15.html`.
- To publish from a new conversation: Artifact `action: "read"` on that URL first, then publish `trsheet/tr-sheet.html` with `url` set to it. Never touch the older sheet "Low-Variance Six" (https://claude.ai/artifact/DEF8ycjXrKGXokgH26he9A).
- The team (real sets, `pssim/myteam_real.json`; SP order HP/Atk/Def/SpA/SpD/Spe):

| Pokémon | Item | Ability | Nature, SP | Moves |
|---|---|---|---|---|
| Mega Blastoise | Blastoisinite | Torrent → Mega Launcher | Quiet 32/0/0/32/2/0 | Fake Out, Water Spout, Aura Sphere, Dark Pulse |
| Torkoal | Charcoal | Drought | Quiet 12/0/0/32/22/0 (see open item 1) | Eruption, Weather Ball, Earth Power, Protect |
| Indeedee-F | Psychic Seed | Psychic Surge | Relaxed 32/0/32/0/2/0 | Follow Me, Helping Hand, Trick Room, Healing Wish |
| Farigiraf | Sitrus Berry | Armor Tail | Relaxed 30/0/21/0/15/0 | Trick Room, Protect, Psychic, Thunderbolt |
| Kingambit | Chople Berry | Defiant | Brave 32/32/0/0/2/0 | Iron Head, Kowtow Cleave, Low Kick, Sucker Punch |
| Incineroar | White Herb | Intimidate | Brave 32/32/0/0/2/0 | Fake Out, Flare Blitz, Throat Chop, Close Combat |

- Each Leads tab shows one card: the four to bring (lead + back row) that won the most whole-game sims, with its turn-one lines. Picks
  (`pssim/bringcf_picks.json`; whole-game win % on 288 fresh games each, old planner: champ-battle-v4 + egvalue5):

| Tab (ladder share) | Lead / back | Wins |
|---|---|---|
| Tailwind (26.2) | Incineroar + Farigiraf / Torkoal, Kingambit | 92% |
| Sun (12.0) | Kingambit + Blastoise / Farigiraf, Incineroar | 52% |
| Indeedee TR (11.9) | Farigiraf + Kingambit / Blastoise, Incineroar | 68% |
| Rain (10.5) | Incineroar + Torkoal / Blastoise, Farigiraf | 58% |
| Balance (9.3) | Farigiraf + Blastoise / Kingambit, Incineroar | 80% |
| Sand (9.0) | Incineroar + Farigiraf / Blastoise, Kingambit | 83% |
| Snow (7.8) | Farigiraf + Blastoise / Torkoal, Incineroar | 85% |
| Trick Room (6.7) | Incineroar + Farigiraf / Blastoise, Torkoal | 73% |
| Rain + Sun (3.3) | Incineroar + Blastoise / Torkoal, Farigiraf | 48% |
| Perish (3.3) | Kingambit + Blastoise / Torkoal, Farigiraf | 95% |

  Ladder-weighted 75.6%.

## How the current page was built

1. Picks: bring matrix (all 90 fours x 6 opposing leads x 16 games per archetype, `pssim/bringmx_report.py`) and a fresh-game
   confirmation (`pssim/bringmx_confirm.py jobs|decide` -> `bringcf_picks.json`; a pick changes only if the fresh leader beats it by >= 1.5
   paired standard errors).
2. Turn-one lines: `pssim/v15_run.sh` (every tab's lead with the real sets and its planned back row; `run_jobs.sh` with 12 samples, then
   Indeedee-F item variants, `v15_merge.py`, `tr_final.py` -> `pssim/tr_final_v15plus.json`).
3. Page: `python3 pssim/build_sheet_v15.py <scratch dir>` from the repo root (runs `tr_leads.py` with `LEAD_OVERRIDE=pssim/lead_override_v14.json`
   and splices only the page's `const L=[...]`; also the Torkoal card), then `cd trsheet && python3 patch_v16_tork.py` (Matchups grid, Torkoal
   column, from `mxtr/gx_cells_{tr,notr}_inc_t22.json`).
   `tr_leads.py` still carries unpublished "Other" tab code from a v12 draft, so never write its output straight onto the page: splice `L`.
4. Check the page in the browser (Leads tabs, team card, Matchups rows) before publishing. Every turn-one switch must go to a Pokémon in
   that card's back row (v14 had switches to Pokémon outside the four; v15 fixed it by simulating with the real back rows).

## Open items (the user decides; none is started)

1. **Torkoal spread.** The user switched to 12 HP / 22 SpD on the 2v2 study's advice. A full-battle A/B on the same games
   (`pssim/tork_ab_run.sh`, `tork_ab_report.py`, `results/tork_ab_report.txt`) says the new spread is about 1 point worse on the tabs that
   bring Torkoal (Snow -5.4 +- 2.2, Trick Room -5.9 +- 2.5; others within noise), from physical leads (Sneasler, Incineroar). Recommendation
   given: go back to 32 HP / 2 SpD (`pssim/myteam_real_tork32.json`). Not decided. If he switches back, v17 = Torkoal card and grid column
   restored (`mxtr/gx_cells_*_inc.json` have the old-spread cells), old-spread whole-game %, and the Rain lead's turn-one lines re-run.
2. **Rerun the picks on the new planner.** The whole-game numbers above come from the old planner. Known biases: Perish far too high (the
   sim's Perish teams almost never trap and sing; real teams beat Perish 48%, the sim says 76%+), the Trick Room tab inflated (about a quarter
   of the modelled "TR" teams lead Delphox and never set Trick Room), status and setup undervalued, opponents double-Protect too much (worth
   about 2 points to us, 7 vs Tailwind). The Battle sim thread has a new setup (champ-battle-v8, `DP2=1 RACE=1`, `egvalue7.json`) and is
   still validating it. When it says the setup is final: rerun the bring matrix and confirmation (about an hour on a 192-core AWS spot box,
   see the aws-setup memory; the user starts the box), then rebuild the page.
3. **Rain near miss.** Blastoise + Farigiraf / Torkoal, Incineroar beat the sheet's Rain pick by 6.8 +- 4.5 on fresh games (1.49 SE, just
   under the bar); all of it against non-Pelipper leads (Dragonite + Gholdengo 77 vs 35, Archaludon + Grimmsnarl 62 vs 27). Revisit in the rerun.
4. **Species tells and per-archetype strategy guides** were delivered in chat only (`pssim/results/bringmx_report.txt`,
   `pssim/battle_guide_report.py`). The user has not asked for them on the sheet. Keep the sheet lean.
5. **Recordings.** The user sends ladder recordings; `recordings/process.sh <mov> <batch>` compresses, extracts frames, OCRs and parses a
   timeline; decision points go through `native/spot_starts.js` + `champ spot` (HANDOFF.md "Spread study, game reviews"). Two batches
   reviewed so far (`recordings/batch1`, `batch2`, `spots.json`).

## Running full battles (the sheet thread's main tool)

From `pssim/`:
```bash
MYTEAM=myteam_real.json node ../native/battle_starts.js <jobs.json> <starts.jsonl> <games> [first game index]
BATTLE_ANTICIPATE=1 EG_VALUE=<value.json> GRID_DIR=<grid dir> ../native/champ/bin/champ-battle-vN battle ../native/engine_data_spot.json <starts.jsonl> <outdir> <threads>
```
Jobs are `{arch, k, lead: [a, b], back: [c, d]}` (k = the archetype's opposing lead 0-5). Seeds depend on the opponent and the game index
only, so two runs with the same game indices are paired game by game: always compare on the same games and report paired differences with
standard errors. Use fresh game indices for confirmation (used so far: 0-23, 200-263, 400-431, 600-615, 1000-1047, 2000-2063, 3000-3003,
4000-4015, 5000-5003, 6000-6002). Ask **Battle sim** for the current binary, value file and flags.

Progress page: `status_server.py` on port 8766 (`sim-progress` in `.claude/launch.json`). A run shows up only if its log in `pssim/` starts
with `HH:MM:SS <jobs.json> -> <outdir>, <games> games, <threads> threads (...)`.

## Rules that apply (also in memory)

- No miss-able moves on the team (95% counts as miss-able). Keep it a distinct Trick Room team; do not drift toward the user's other team.
- Sims assume competent opponents; do not tune around ladder misplays.
- Keep the sheet lean; add sections only when asked. Times in 12-hour am/pm.
- CPU: never more than 10 busy cores on the Mac across all threads; at most 3 workers while the user may be playing (ask first); when
  several threads need cores, split evenly and coordinate by message. Never delete the user's files unless asked.
