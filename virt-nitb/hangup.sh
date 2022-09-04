#!/bin/sh
set -x
osmo_interact_vty.py -H 127.0.0.1 -p 4247 -c "enable;call 1 hangup"
