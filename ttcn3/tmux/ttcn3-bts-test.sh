#!/bin/sh

SESSION="ttcn3-bts-test"

OSMO_DIR="/home/$USER/osmocom"
OBB_DIR="$OSMO_DIR/osmocom-bb"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"
RESPAWN="$OSMO_DIR/scripts/respawn.sh"

if [ ! -d $SUITE_DIR ]; then
	echo "Directory '$SUITE_DIR' does not exist"
	echo "Please specify where to find osmo-ttcn3-hacks"
	exit 1
fi

if [ ! -d $OBB_DIR ]; then
	echo "Directory '$OBB_DIR' does not exist"
	echo "Please specify where to find osmocom-bb"
	exit 1
fi

if [ ! -f $RESPAWN ]; then
	echo "Script '$RESPAWN' does not exist"
	echo "Please specify where to find respawn.sh"
	exit 1
fi

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $SUITE_DIR/bts" C-m
tmux send-keys -t $SESSION:0.0 "$RESPAWN osmo-bts-trx -c osmo-bts.cfg"
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/bts" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh ./BTS_Tests BTS_Tests.cfg"


tmux new-window -t $SESSION:1
tmux split-window -t $SESSION:1 -v
tmux split-window -t $SESSION:1 -v

# Start osmo-bsc
tmux send-keys -t $SESSION:1.0 "cd $SUITE_DIR/bts" C-m
tmux send-keys -t $SESSION:1.0 "osmo-bsc -c osmo-bsc.cfg" C-m
# Start trxcon
tmux send-keys -t $SESSION:1.1 "cd $OBB_DIR/src/host/trxcon" C-m
tmux send-keys -t $SESSION:1.1 "./trxcon -s /tmp/osmocom_l2" C-m
# Start fake_trx.py
tmux send-keys -t $SESSION:1.2 "cd $OBB_DIR/src/target/trx_toolkit" C-m
tmux send-keys -t $SESSION:1.2 "./fake_trx.py \
					--trx TRX1@127.0.0.1:5700/1 \
					--trx TRX2@127.0.0.1:5700/2 \
					--trx TRX3@127.0.0.1:5700/3" C-m

tmux attach -t $SESSION:0
