# Champions sims

Simulators and tools for Pokémon Champions VGC doubles (Regulation M-C):

- a Rust port of Showdown's doubles engine, with a planner and a learned position value;
- ladder sheets built from whole-game sims;
- a search for the strongest six;
- an evaluation bar for replays and tournament broadcasts;
- a Showdown ladder bot.

This file is the map. Each area's handoff has the detail and the dated history.

## Who owns what

The work is split between Claude sessions ("threads"). Each owns its folders and changes only those; the threads coordinate by message.

| Area | Folders | Thread | Start with |
|---|---|---|---|
| Engine and planner | `native/champ/` (Rust; versioned `champ-battle-vN` builds), the position value (`pssim/egvalue*.json`, `bot/value/`), replay analysis and value training in `pssim/` | Battle sim | root `HANDOFF.md`, from "Full 4v4 battle sim" on |
| Showdown bot | `bot/` | Battle sim | the headers of `bot/client.js` and `bot/brain.py`; `bot/limits.json` |
| Eval bar | `evalbar/`: the replay reader (`replay.py`), the position builder (`battlestate.py`), evaluation, pages, accuracy | Eval bar | `evalbar/HANDOFF.md` |
| Broadcast watcher, public page | `evalbar/auto.py`, `evalbar/publish.py`, `page.html`'s public mode | Stream watcher | `evalbar/HANDOFF.md`, "Hands-free" and "The public page" |
| Trick Room Six sheet, sheet kit | `trsheet/`, `sheetkit/`, `sheets/trick-room-six/`, the root `tr_*.py`, `mxtr/`, `recordings/`, the turn-one lead pipeline in `pssim/` (`t1sim.js`, `tr_final.py`, `run_jobs.sh`), Showdown's Champions data patch (`pssim/engine_patch/`) | TR sheet | `trsheet/HANDOFF.md`, `sheetkit/README.md` |
| Frankfurt sheets | `sheets/frankfurt-239/`, `sheets/frankfurt-156/` | Frankfurt-239 sheet, Frankfurt-156 sheet | `sheetkit/README.md` |
| Team search | `teamsearch/` | Team search | `teamsearch/HANDOFF.md` |
| Progress page | `status_server.py`; each thread supplies its own cards (`evalbar/status.py`, `teamsearch/status_server.py`) | Battle sim | its docstring |

Shared and read-only unless agreed:

- `regionals/`: tournament teams and usage sets;
- `native/*.js` and `native/*.json`: engine data exports and test cases;
- `spreads/`;
- `tools/privacy_scan.py`.

## Setup

```bash
./setup.sh
```

- **Node and Python:** `setup.sh` needs Node 18+ and Python 3. The bot and the live feeds need Node 20.10+ (`--experimental-websocket`).
- **What setup.sh installs:**
  - Showdown 0.11.11 into `pssim/`, with this project's Champions data patch (`pssim/engine_patch/`);
  - a `.venv` with numpy and scipy.
- **The engine:** build it from `native/champ` with `cargo build --release`.
- **Never run Showdown's own launcher without `--skip-build`.** Its build regenerates `dist/` and wipes the Champions data patch. A local server is `./pokemon-showdown start --skip-build <port> --no-security`, run from `pssim/node_modules/pokemon-showdown`.
- **Worktrees:** replay logs, results and engine builds are git-ignored, so they live only in the main checkout. `evalbar/common.py` finds them from a git worktree. The sheet threads work in the main checkout.

## Common commands

Run from the repo root unless noted.

| What | Command |
|---|---|
| Progress page: every process using CPU, by thread, plus progress cards | `python3 status_server.py`, then http://localhost:8766 |
| A sheet's status and next step | `python3 sheetkit/kit.py <team> status` (the steps: `sheetkit/README.md`) |
| Check the kit after a change | `python3 sheetkit/selftest_tr.py` |
| Eval bar page for one replay | `python3 evalbar/build.py <replay id>`, written to `evalbar/out/` |
| Follow a Showdown battle as a spectator | `python3 evalbar/live.py list`, then `python3 evalbar/live.py watch <room>` |
| Broadcast watcher (a LaunchAgent; page on http://localhost:8768) | `python3 evalbar/auto.py streams`, `install` or `uninstall` |
| Hill climb | on a cloud box, from `teamsearch/` (setup: `teamsearch/cloud/README.md`): `. cloud/run_env_v32.sh && ../.venv/bin/python3 climb.py round thorough climb_v32`; `python3 climb.py stats` |
| Value training data | from `pssim/`: `../.venv/bin/python3 value_data.py positions`, then `search`, then `feats` |
| Engine tests against Showdown | `champ damage …`, `champ turn …` (see the header of `native/champ/src/main.rs`) |
| Bot, logged in but not searching | `node --experimental-websocket --no-warnings bot/client.js --dry` |

The bot plays on real ladder accounts. Test it against a local server (`--server`), never by logging the live accounts in or out: a logout forfeits rated games in progress.

## Rules for every thread

- **No names in anything tracked.** That covers code, data, docs and commit messages: no real names, usernames, opponents' or players' names, emails or absolute home paths. Write "the user" or "the player"; in game data, "Player 1" and "Player 2".
  - Replay logs, recordings and scraped pages stay git-ignored.
  - The pre-commit and commit-msg hooks (`tools/privacy_scan.py`) enforce this. Never bypass them.
- **Git:** commit your own area with explicit paths, never `git add -A`, then push `main`.
- **CPU:** at most 10 busy cores across all threads, and 3 workers while the user may be playing.
  - Name processes `<thread>-<program>` (`battlesim-`, `evalbar-`, `trsheet-`, `teamsearch-`, or a sheet's own prefix).
  - Every job using CPU shows on the progress page; long ones get a progress card.
- **Engine and value changes go through Battle sim.** Everything else depends on them; ask which build, value file and flags are current before a big run.
- **Position building goes through `evalbar/battlestate.py`.** The live page, the bot and the training data share it.
  - A fix there goes into `battlestate.FLAGS`.
  - It reaches the bot only when Battle sim adds it to `botpos.BOT_FLAGS`.

## Other files

- `HANDOFF.md`: the project's history and recipes for the lead sims, the sheets and the engine. It is long, with dated sections.
- `NOTICE.md`: Showdown's licence notice, data sources and the trademark line.
- `LICENSE`: MIT.
