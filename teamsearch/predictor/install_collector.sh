#!/bin/bash
# Run predictor/collect.py every two hours (and at login) as the LaunchAgent local.teamsearch.replays (the user, 2026-11-27:
# collect replays from the day M-D goes live). Re-running replaces the agent. Remove it with:
#   launchctl bootout gui/$(id -u)/local.teamsearch.replays; rm ~/Library/LaunchAgents/local.teamsearch.replays.plist
cd "$(dirname "$0")/.."
TS=$PWD; PL=$HOME/Library/LaunchAgents/local.teamsearch.replays.plist
cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.teamsearch.replays</string>
  <key>ProgramArguments</key><array><string>$TS/bin/teamsearch-py</string><string>$TS/predictor/collect.py</string></array>
  <key>WorkingDirectory</key><string>$TS</string>
  <key>StartInterval</key><integer>7200</integer>
  <key>RunAtLoad</key><true/>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>10</integer>
  <key>StandardOutPath</key><string>$TS/predictor/collect.err</string>
  <key>StandardErrorPath</key><string>$TS/predictor/collect.err</string>
</dict></plist>
EOF
launchctl bootout gui/$(id -u)/local.teamsearch.replays 2>/dev/null
launchctl bootstrap gui/$(id -u) "$PL" && echo "installed: local.teamsearch.replays (every 2 hours; log predictor/collect.log)"
