# Running the hill climb on AWS

**The setup** is the final one (Battle sim, 2026-10-05, amended the same day), in `cloud/run_env.sh`:
- `TS_SIM=v13g`: champ-battle-v13, `pssim/egvalue9.json` (general intercept), damage race with Speed ties averaged (`RACE_TIES=avg`), two-turn Protect check, anticipation.
- `TS_PERISH=real`: Perish trap is scored from real regional rates instead of battles (`perish_stock.py`).

**Size:** a thorough round 1 over the 52 starts is about 155k 4v4 games. At about 11.5 s per game per core on c7a, that's roughly 2.5–3 h on a **c7a.48xlarge** (192 vCPUs; on c7a each vCPU is a full core). Later rounds only re-run the starts still climbing. The first climb took ~8 h for 4 rounds. Run it in the daytime, so the user can launch the box and answer questions while it runs.

**Prices** (Oct 2026, spot, c7a.48xlarge):
- Europe (Spain, eu-south-2): about $1.16 per hour. Interruption 5–10% per month, the same bucket as Ohio. It's an opt-in region and needs its own quota and key pair.
- US East (Ohio, us-east-2): about $2.44–2.51 per hour in zones 2b and 2a. Zone 2c was ~$3.23, so avoid it.
- On-demand: about $9.85 per hour.

## 0. One-time account prep (quota requests take time)

1. **Budget alert:** Billing → Budgets → Create budget → Cost budget, e.g. $30 per month, with an email alert at 80%.
2. **Region:** Spain must be enabled first: Account → AWS Regions → Europe (Spain) → Enable.
3. **vCPU quota** in the region you'll use: Service Quotas → AWS services → Amazon EC2 → request **192** for *All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests*. Ohio already has 192. Spain was requested on Oct 5.
4. **Key pair** (key pairs are per region): EC2 → Key Pairs → Create key pair (ED25519, .pem). Save it as `~/.ssh/KEY.pem`, then:
   ```bash
   chmod 400 ~/.ssh/KEY.pem
   ```

## 1. Launch the instance

**Fastest: a launch template (create once per region; templates, key pairs and security groups are all per region).**
EC2 → Launch Templates → Create launch template: name `champions-climb`; AMI Ubuntu Server 24.04 LTS (x86); instance type
`c7a.48xlarge`; that region's key pair; no subnet (choose the zone at launch); the existing security group that allows SSH from
your IP; root volume 40 GiB gp3; Advanced details → Purchasing option → Spot (one-time, terminate on interruption). Then each
launch is Launch Templates → `champions-climb` → Actions → Launch instance from template. If your IP changes, add it to the
security group. Without a template, set these by hand:


EC2 console (the region with the quota) → **Launch instance**:
- **Name:** `champions-climb`.
- **AMI:** Ubuntu Server 26.04 or 24.04 LTS, 64-bit (x86).
- **Instance type:** `c7a.48xlarge`.
- **Key pair:** that region's key pair (written as `KEY` below).
- **Network settings:** allow SSH from **My IP** only. In Ohio, Edit → Subnet → `us-east-2b` (cheapest zone).
- **Storage:** 40 GiB gp3.
- **Spot** (Advanced details → Purchasing option → Spot instances): keep the defaults, a **one-time** request that terminates on interruption. If AWS reclaims it mid-run, only in-flight battles are lost: results are copied to the Mac every ~15 min, and a rerun reuses finished battles.
- Optional, before launching: EC2 → Spot Requests → **Spot placement score** for 1 × c7a.48xlarge shows how likely the request is to succeed per region and zone.
- Launch, then copy the instance's **Public IPv4 DNS**. Below it's `HOST`.

## 2. Pack and upload (on the Mac)

```bash
teamsearch/cloud/pack.sh
```

```bash
scp -i ~/.ssh/KEY.pem teamsearch/cloud/bundle.tar.gz ubuntu@HOST:
```

`pack.sh` collects what the climb needs (a few MB):
- the teamsearch scripts, sets, matrix cells, bring model and the Perish table;
- the battle-sim source snapshot (v13 by default) and its checksums;
- the Showdown data patch, t1sim, the archetype models, the archetype classifier and every value file;
- the regional set data.

It leaves out battle outputs, the first AWS climb's results (`cloud_results/`), any local climb state or pre-filter cache, and `regmatch/`. A new climb on the box therefore starts fresh.

## 3. Set up the box (about 10 minutes)

```bash
ssh -i ~/.ssh/KEY.pem ubuntu@HOST
```

Then, on the box:

```bash
mkdir champions-sims && tar xzf bundle.tar.gz -C champions-sims && cd champions-sims && teamsearch/cloud/remote_setup.sh
```

`remote_setup.sh` does four things:
1. Installs Node, Python and Rust.
2. Runs the repo's `setup.sh`: Showdown 0.11.11 plus our Champions fixes, and a Python venv with numpy/scipy.
3. Checks the battle source against the recorded checksum.
4. Builds `native/champ/bin/champ-battle-v13` for Linux. To add another binary later without reinstalling anything, use `teamsearch/cloud/build_battle.sh src_battle_vN.tar.gz`.

## 4. Smoke test and timing

```bash
cd ~/champions-sims/teamsearch && . cloud/run_env.sh && TS_THREADS=$(nproc) ../.venv/bin/python3 evaluate.py trick_room_six 1 0
```

This plays 54 games, one per archetype × lead pair; Perish is scored from real data. It prints the score and the seconds taken.
- **Check the score and per-job wins** against `cloud/reference_v13g.json` (the same games on the Mac: score 0.5762). They must match exactly. If not, the Linux build differs; stop and compare before running a round.
- **Speed:** seconds × threads ÷ 54 = seconds per game per core. The Mac was 6.1.

## 5. Run a round

```bash
tmux -L climb new -s climb
```

Then, inside tmux:

```bash
cd ~/champions-sims/teamsearch && . cloud/run_env.sh && TS_PARALLEL=60 TS_THREADS=3 TS_PREFILTER_PROCS=96 ../.venv/bin/python3 climb.py round thorough 2>&1 | tee -a round.log
```

- **Check the first line:** it prints the sim setup and binary. It must say `v13g` and `champ-battle-v13`.
- **Detach** with Ctrl-b then d; reattach with `tmux -L climb attach -t climb`. The climb uses its own tmux server (`-L climb`), so other runs on the box can't take it down.
- **Change the thread count or recover from a crash:** `cloud/relaunch.sh <P> <T>`. Finished battles are reused, and the round only commits to `climb_state.json` at the end.
- **Further rounds automatically:** `setsid nohup cloud/auto_rounds.sh <power-off epoch> [seconds per climbing start] &`. It keeps starting thorough rounds while starts are still climbing and the next round fits before the power-off.
- **Same machine type for the whole climb:** paired seeds assume the same binary.

## 5b. Auto power-off and copying results home (set up once the run is going)

Start a watchdog on the box. It powers off after 45 idle minutes, or MAX_H hours after the start time you pass (second argument, default 8):

```bash
scp -i ~/.ssh/KEY.pem teamsearch/cloud/watchdog.sh ubuntu@HOST: && ssh -n -i ~/.ssh/KEY.pem ubuntu@HOST 'setsid nohup ./watchdog.sh $(date +%s) 12 >/dev/null 2>&1 </dev/null &'
```

Then start the Mac-side copy loop. It pulls every 15 minutes; for the rerun, the destination is `teamsearch/cloud_results/v12`, so the first climb's results stay as they are:

```bash
nohup teamsearch/cloud/pull_loop.sh HOST ~/.ssh/KEY.pem cloud_results/v12 >/dev/null 2>&1 &
```

Notes:
- Linux `pgrep` has no `-E` flag.
- Don't stop the watchdog with `pkill -f watchdog`: that also kills your own ssh command's shell. Kill it by PID.
- `python3 report.py cloud_results/v12` prints the climb report from the pulled results.
- Progress page from the pulled results: `TS_CLIMB_DIR=cloud_results/v12 python3 status_server.py` (port 8767).

## 6. Shut it down (billing stops only when it's terminated)

- EC2 → Instances → select → **Terminate**.
- **If you used a persistent spot request:** first cancel it under EC2 → Spot Requests, or it relaunches. One-time requests end with the instance.
- EC2 → Volumes: delete any leftover `available` volume.

## Letting Claude drive it

Steps 0, 1 and 6 need the AWS console. Once the box is up, give Claude the `HOST` and the key's path, and it can run steps 2–5 over SSH.

## The miss-doubling climb (user, 2026-10-06)

The user's side misses twice as often (champ-battle-v20 with MISS_DOUBLE=0; setup `v20m`). Same steps as above, except:
- `remote_setup.sh` builds v20 by default.
- Smoke test: `. cloud/run_env_miss.sh && TS_THREADS=$(nproc) ../.venv/bin/python3 evaluate.py trick_room_six 1 0` must match `cloud/reference_v20m.json` (0.5788).
- Run: `tmux -L climb new -s climb` then `. cloud/run_env_miss.sh && TS_PARALLEL=30 TS_THREADS=3 TS_PREFILTER_PROCS=48 ../.venv/bin/python3 climb.py round thorough 2>&1 | tee -a round_miss.log`.
- Relaunch: `RUN_ENV=cloud/run_env_miss.sh cloud/relaunch.sh <P> <T>`; more rounds: `RUN_ENV=cloud/run_env_miss.sh setsid nohup cloud/auto_rounds.sh <cap> [secs per start] &`.
  These log to round.log; the climb's own files are `climb_miss_state.json`, `climb_miss_log.jsonl` and `climb_miss_progress.json`.
- Report: `python3 report.py cloud_results/<dir> climb_miss`.
- After round 1, check for degenerate miss-reward strategies (Blunder Policy, Stomping Tantrum or Temper Flare stacking, crash moves) before letting it continue.

## The two pool-based climbs (user, 2026-10-06): with and without the miss rule, side by side

Opponents are real pool entries; brings are chosen per core group (`poolmode.py`). The two climbs are `cloud/run_env_pool.sh`
(v20g, no rule: the control) and `cloud/run_env_poolmiss.sh` (v20m, the user's misses doubled). Each has its own state, log, progress,
cache, round log (`round_pool.log` / `round_poolmiss.log`) and tmux session, and its relaunch only touches its own processes.
On a c7a.48xlarge give each 30 x 3; on a 96-core box, 15 x 3 each (`cloud/threads_climb_pool.txt` / `threads_climb_poolmiss.txt`).
1. Setup as above (the bundle carries the pool, its rules and the full engine data; v20 is built by default).
2. Smoke: `. cloud/run_env.sh && TS_SIM=v20m ... evaluate.py trick_room_six 1 0` against `cloud/reference_v20m.json`, and the pool path:
   `TS_SIM=v20g TS_OPP=pool TS_POOL_ES=1 TS_BRING_K=1` poolmode.search_team(trick_room_six, 123, 3, K=1) against `cloud/reference_pool.json`.
3. Start each: `tmux -L climb new -d -s climb_pool ". cloud/run_env_pool.sh && TS_PARALLEL=30 TS_THREADS=3 TS_PREFILTER_PROCS=48 ../.venv/bin/python3 climb.py round thorough climb_pool 2>&1 | tee -a round_pool.log"`
   (and the same with poolmiss), then `RUN_ENV=cloud/run_env_pool.sh setsid nohup cloud/auto_rounds.sh <cap> &` for each.
4. Reports: `python3 report.py cloud_results/<dir> climb_pool` and `... climb_poolmiss`. After round 1, check the miss climb for
   degenerate miss-reward strategies (Blunder Policy, Stomping Tantrum / Temper Flare, crash moves) before letting it continue.
