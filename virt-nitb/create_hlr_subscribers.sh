#!/bin/bash
set -x -e

touch empty
osmo-hlr -c empty &
sleep 1

osmo_interact_vty.py -H 127.0.0.1 -p 4258 -c "enable
subscriber imsi 901700000000001 create
subscriber imsi 901700000000001 update aud2g comp128v1 ki 11111111111111111111111111111111
subscriber imsi 901700000000001 update msisdn 1

subscriber imsi 901700000000002 create
subscriber imsi 901700000000002 update aud2g comp128v1 ki 22222222222222222222222222222222
subscriber imsi 901700000000002 update msisdn 2

show subscribers all
"
kill %1
rm empty
