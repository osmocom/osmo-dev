#!/bin/sh
DIALPLANDIR="$(cd $(dirname "$0")/../../../src/osmo-hlr/contrib/dgsm; pwd)"
(sleep 5; echo; echo; echo "NOTE: type 'shutdown' to quit"; echo) &

if ! [ -e "$DIALPLANDIR/freeswitch_dialplan_dgsm.py" ]; then
	echo "ERROR: freeswitch_dialplan_dgsm.py not found in: $DIALPLANDIR"
	exit 1
fi
set -ex

export PYTHONPATH="$PYTHONPATH:$DIALPLANDIR"

if ! [ -d /usr/lib/freeswitch/mod ]; then
	echo "ERROR: missing dir /usr/lib/freeswitch/mod"
	exit 1
fi

if ! [ -e freeswitch/mod ]; then
	ln -sf /usr/lib/freeswitch/mod freeswitch/mod
fi

freeswitch \
	-nf \
	-nonat \
	-nonatmap \
	-nocal \
	-nort \
	-c \
	-base ./freeswitch
