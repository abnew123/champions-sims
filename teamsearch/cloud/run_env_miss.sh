# The miss-doubling climb (user, 2026-10-06): the user's side misses twice as often. Every accuracy roll's final hit chance p becomes
# max(0, 2p - 100); accuracy-true cases (No Guard, Lock-On, rain Hurricane, always-hit moves) are untouched; secondary chances are
# unchanged; a rule miss is an ordinary miss (Blunder Policy, Stomping Tantrum, crash damage all apply). Otherwise the final setup
# (egvalue9, race with averaged Speed ties, two-turn Protect check, anticipation; Perish from real data) on champ-battle-v19.
# Its own state, log and progress files, so it never touches the rerun's. Use: RUN_ENV=cloud/run_env_miss.sh cloud/relaunch.sh ...
export TS_SIM=v19m TS_PERISH=real TS_STATE=climb_miss_state.json TS_LOG=climb_miss_log.jsonl TS_PROGRESS=climb_miss_progress.json
unset TS_BATTLE_BIN
