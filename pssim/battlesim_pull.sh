#!/bin/zsh
# Pull Battle sim's results from the shared AWS box (battlesim_box.sh) every 20 minutes into pssim/results/battlesim_box/, until the box
# marks ALL_DONE (or the box is gone: three failed pulls in a row). Only ~/battlesim/battlesim_results is read; nothing on the box changes.
#   HOST=ubuntu@<ip> KEY=~/.ssh/<key>.pem ./battlesim_pull.sh
ME=${0:A}; cd "$(dirname $ME)"
HOST=${HOST:?ubuntu@ip}; KEY=${KEY:?key file}; DST=${DST:-results/battlesim_box}; REMOTE=${REMOTE:-battlesim/battlesim_results/}; mkdir -p $DST; fails=0   # REMOTE / DST: another run's folders
while true; do
  if rsync -az --exclude 'grid' --exclude 'battlesim-champ-deep*' -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20" \
       --exclude 'inputs' --exclude 'build' $HOST:$REMOTE $DST/; then
    fails=0; dn=($DST/*.done(N)); echo "$(date '+%I:%M %p') pulled: ${#dn} jobs done"   # (N): no match is an empty list, not an ls of the folder
    [ -f $DST/ALL_DONE ] && { echo "all jobs done"; break; }
  else
    fails=$((fails + 1)); echo "$(date '+%I:%M %p') pull failed ($fails)"; [ $fails -ge 3 ] && { echo "box unreachable: stopping"; break; }
  fi
  sleep 1200
done
