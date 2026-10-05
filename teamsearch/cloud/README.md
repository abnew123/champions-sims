# Running the hill climb on AWS

**When it's worth it:** a thorough round is about 123k 4v4 games. That's about 15.6 h on the laptop (13 threads at about 5.9 s per game). An AWS **c7a.48xlarge** has 192 vCPUs, and on c7a each vCPU is a full core. My estimate is about 1.5 h per thorough round there; step 4 measures the real speed.

**Prices** (Oct 2026):
- Spot: about $2.50–3.00 per hour (us-east-2 Ohio is usually cheapest), so roughly $4–5 per thorough round.
- On-demand: about $9.85 per hour.
- Smaller fallbacks: c7a.24xlarge (96 cores) or c7a.16xlarge (64 cores) cost proportionally less and run proportionally slower.

## 0. One-time account prep (do this days ahead: quota requests take time)

1. **Budget alert:** Billing → Budgets → Create budget → Cost budget, e.g. $30 per month, with an email alert at 80%.
2. **vCPU quota.** New accounts start with very low limits. Service Quotas → AWS services → Amazon EC2 → request **192** for:
   - *All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests* (for spot), and/or
   - *Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances* (for on-demand).

   Request in the region you'll use (say us-east-2). Approval can take a few hours to a couple of days.
3. **Key pair:** EC2 → Key Pairs → Create key pair (ED25519, .pem). Save it as `~/.ssh/KEY.pem`, then:
   ```bash
   chmod 400 ~/.ssh/KEY.pem
   ```

## 1. Launch the instance

EC2 console (same region as the quota) → **Launch instance**:
- **Name:** `champions-climb`.
- **AMI:** Ubuntu Server 24.04 LTS, 64-bit (x86).
- **Instance type:** `c7a.48xlarge`.
- **Key pair:** the one you created (written as `KEY` below).
- **Network settings:** allow SSH from **My IP** only (not "Anywhere").
- **Storage:** 40 GiB gp3.
- **Spot** (Advanced details → Purchasing option → Spot instances): keep the defaults, a **one-time** request that terminates on interruption.
  - Nothing lingers after you terminate it.
  - If AWS reclaims it mid-run, only in-flight battles are lost: results get copied back to the Mac every ~15 min, and a rerun reuses finished battles.
  - Leave this off for on-demand.
- Launch, then copy the instance's **Public IPv4 DNS**. Below it's `HOST`.

## 2. Pack and upload (on the Mac)

```bash
teamsearch/cloud/pack.sh
```

```bash
scp -i ~/.ssh/KEY.pem teamsearch/cloud/bundle.tar.gz ubuntu@HOST:
```

`pack.sh` collects only what the climb needs, about 1 MB:
- the teamsearch scripts, sets, matrix cells, bring model and climb state;
- the battle-sim source snapshot and its checksums;
- the Showdown data patch, t1sim, the archetype models, the value-function files;
- the regional data.

Node packages are reinstalled on the box, and old results and Mac binaries are left out.

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
3. Checks the battle source against the checksum the other thread recorded.
4. Builds `native/champ/bin/champ-battle-v3` for Linux (pass `src_battle_v2.tar.gz` to both scripts to build v2 instead).

## 4. Smoke test and timing

```bash
cd ~/champions-sims/teamsearch && TS_BATTLE_BIN=../native/champ/bin/champ-battle-v3 TS_THREADS=$(nproc) ../.venv/bin/python3 evaluate.py trick_room_six 1 0
```

This plays 60 games (one per archetype × lead pair) for the Trick Room six and prints the score and the seconds taken.
- **Check the score** against `cloud/reference.json` (the same 60 games on the Mac). They should match. If not, the Linux build differs; don't mix machines within a round.
- **Speed:** seconds × threads ÷ 60 = seconds per game per core. Compare with the Mac's 5.9.

## 5. Run a round

```bash
tmux new -s climb
```

Then, inside tmux:

```bash
cd ~/champions-sims/teamsearch && TS_BATTLE_BIN=$PWD/../native/champ/bin/champ-battle-v3 TS_PARALLEL=48 TS_THREADS=4 ../.venv/bin/python3 climb.py round thorough 2>&1 | tee -a round.log
```

- **Detach** with Ctrl-b then d; reattach with `tmux attach -t climb`. Closing the laptop is fine once detached.
- **Interrupted?** Rerun the same command. Finished battles are reused, and the round only commits to `climb_state.json` at the end.
- **48 × 4 = 192 threads:** 48 teams at a time, 4 threads each. Defaults are egvalue5 with anticipation on.
- **Value file:** use whichever one the other thread confirmed (egvalue4.json now, egvalue5.json once it's checked); add it to `pack.sh` if it's newer than egvalue4.
- **Same machine type for the whole round:** paired seeds assume the same binary, so don't switch machines mid-round.

## 5b. Auto power-off and copying results home (set up once the run is going)

Start a watchdog on the box. It powers off after 45 idle minutes, or 8 hours after the start time you pass:

```bash
scp -i ~/.ssh/KEY.pem teamsearch/cloud/watchdog.sh ubuntu@HOST: && ssh -n -i ~/.ssh/KEY.pem ubuntu@HOST 'setsid nohup ./watchdog.sh $(date +%s) >/dev/null 2>&1 </dev/null &'
```

Then start the Mac-side copy loop, which pulls into `teamsearch/cloud_results/` every 15 minutes:

```bash
nohup teamsearch/cloud/pull_loop.sh HOST >/dev/null 2>&1 &
```

Notes:
- Linux `pgrep` has no `-E` flag.
- Don't stop the watchdog with `pkill -f watchdog`: that also kills your own ssh command's shell. Kill it by PID.

## 6. Bring the results home (on the Mac)

```bash
rsync -az -e "ssh -i ~/.ssh/KEY.pem" "ubuntu@HOST:champions-sims/teamsearch/climb_*" "ubuntu@HOST:champions-sims/teamsearch/round.log" teamsearch/
```

```bash
rsync -az -e "ssh -i ~/.ssh/KEY.pem" ubuntu@HOST:champions-sims/teamsearch/runs/ teamsearch/runs/
```

## 7. Shut it down (billing stops only when it's terminated)

- EC2 → Instances → select → **Terminate**.
- **If you used a persistent spot request:** first cancel it under EC2 → Spot Requests, or it relaunches. (One-time requests end with the instance.)
- EC2 → Volumes: delete any leftover `available` volume.

## Letting Claude drive it

Steps 0, 1 and 7 need your AWS console. Once the box is up, give Claude the `HOST` and the key's path, and it can run steps 2–6 over SSH.
