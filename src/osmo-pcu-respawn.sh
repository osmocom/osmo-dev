#!/bin/sh -x
# Automatically restart osmo-pcu while running TTCN3 tests. See docker-playground.git's osmo-pcu-master/respawn.sh.

while true; do
	osmo-pcu "$@"
done
