#!/bin/zsh
# One recording -> <batch>/games.mp4 (compressed, see compress.sh), 2 fps frames, Vision OCR, parse.py timeline.
# usage: recordings/process.sh <recording.mov> <batch dir>     (the original .mov is left alone)
R=${0:A:h}; F=$1; B=${2:A}; mkdir -p $B/frames
$R/compress.sh "$F" && mv "${F:r}.mp4" $B/games.mp4 || exit 1
nice -n 10 ffmpeg -v error -y -i $B/games.mp4 -vf "fps=2,scale=1600:-1" -q:v 3 $B/frames/g_%04d.jpg
echo "frames: $(ls $B/frames | wc -l)"
nice -n 10 $R/ocr $B/frames > $B/ocr.jsonl && python3 $R/parse.py $B/ocr.jsonl > $B/timeline.txt
echo "PARSE DONE: $(wc -l < $B/timeline.txt) lines"
