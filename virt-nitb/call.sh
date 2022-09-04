#!/bin/sh
set -x
osmo_interact_vty.py -H 127.0.0.1 -p 4247 -c "enable;call 1 2"
sleep 5
osmo_interact_vty.py -H 127.0.0.2 -p 4247 -c "enable;call 2 answer"
