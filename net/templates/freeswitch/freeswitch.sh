#!/bin/sh
NETDIR="$(cd $(dirname "$0")/..; pwd)"
(sleep 5; echo; echo; echo "NOTE: type 'shutdown' to quit"; echo) &
set -ex

export PYTHONPATH="$NETDIR/freeswitch/python:$PYTHONPATH"

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
