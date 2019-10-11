#!/bin/sh -x
# Run in a separate script, so we can kill it with "killall"

DIR="$(readlink -f "$(dirname $0)")"
cd "$DIR"
PID=""

cleanup() {
	echo "Caught signal, cleaning up..."
	set -x
	kill "$PID"
	exit 1
}

trap cleanup "TERM"

./osmocom-bb/src/target/trx_toolkit/fake_trx.py "$@" &
PID="$!"

set +x
while true; do
	sleep 0.1
done
