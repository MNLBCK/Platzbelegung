#!/usr/bin/env bash
set -euo pipefail

echo "-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-"
echo "Starting Platzbelegung Scraper"

# Directories and PID file
LOGDIR="../logs"
RUNDIR="../run"
PIDFILE="$RUNDIR/npm.pid"

mkdir -p "$LOGDIR" "$RUNDIR"

# If a PID file exists, try to kill the running process before rebuilding
if [ -s "$PIDFILE" ]; then
	oldpid=$(cat "$PIDFILE" 2>/dev/null || true)
	if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then
		echo "Killing existing process $oldpid"
		kill "$oldpid" || true
		# give it a moment to exit
		sleep 1
		# try a stronger kill if still running
		if kill -0 "$oldpid" 2>/dev/null; then
			kill -9 "$oldpid" || true
		fi
	fi
	rm -f "$PIDFILE"
fi

npm install

# Start the app and record its PID so it can be stopped next run
nohup sh -c "exec env npm start" > "$LOGDIR/npm_log.log" 2>&1 < /dev/null &
echo $! > "$PIDFILE"

echo "."
sleep 1
echo "."
sleep 1
echo "."
sleep 1
cat "$LOGDIR/npm_log.log"
echo "-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-=-=-=--=-=-=-"