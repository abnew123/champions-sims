#!/bin/zsh
# Shrink game screen recordings for parsing: HEVC on the hardware encoder, at most 1600 px wide, 10 fps, no audio (~50x smaller).
# Tested on the demo game: parse.py recovers every battle message and HP snapshot that the original recording gives.
# usage: recordings/compress.sh <recording.mov> ...   -> writes <recording>.mp4 next to each; originals are left alone
for f in "$@"; do
  out="${f:r}.mp4"
  if [ -e "$out" ]; then echo "skip: $out already exists"; continue; fi
  nice -n 10 ffmpeg -v error -hwaccel videotoolbox -i "$f" -vf "fps=10,scale='min(1600,iw)':-2" \
    -c:v hevc_videotoolbox -q:v 40 -tag:v hvc1 -an "$out" || { echo "FAILED: $f"; rm -f "$out"; continue; }
  d1=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"); d2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out")
  echo "${out:t}: $(du -hL "$f" | cut -f1) -> $(du -h "$out" | cut -f1), length ${d1%.*}s -> ${d2%.*}s"
done
