#!/bin/sh -x
# Automatically restart osmo-bts-trx while running TTCN3 tests. See docker-playground.git.

while true; do
	osmo-bts-trx "$@"
done
