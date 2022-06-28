#!/bin/sh

SESSION="ttcn3-bsc-test"

OSMO_DIR="/home/$USER/osmocom"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"
RESPAWN="$OSMO_DIR/scripts/respawn.sh"

if [ ! -d $SUITE_DIR ]; then
	echo "Directory '$SUITE_DIR' does not exist"
	echo "Please specify where to find osmo-ttcn3-hacks"
	exit 1
fi

if [ ! -f $RESPAWN ]; then
	echo "Script '$RESPAWN' does not exist"
	echo "Please specify where to find respawn.sh"
	exit 1
fi

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $SUITE_DIR/bsc" C-m
tmux send-keys -t $SESSION:0.0 "osmo-bsc -c osmo-bsc.cfg" C-m
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/bsc" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh ./BSC_Tests BSC_Tests.cfg"

tmux new-window -t $SESSION:1
tmux split-window -t $SESSION:1 -v
tmux split-window -t $SESSION:1 -v
tmux split-window -t $SESSION:1 -v
tmux split-window -t $SESSION:1 -v

# Start osmo-stp
tmux send-keys -t $SESSION:1.0 "cd $SUITE_DIR/bsc" C-m
tmux send-keys -t $SESSION:1.0 "osmo-stp -c osmo-stp.cfg" C-m
# Start osmo-bts-omldummy
BTS_FEATURES="-fCCN,EGPRS,GPRS,IPv6_NSVC,PAGING_COORDINATION"
tmux send-keys -t $SESSION:1.1 "$RESPAWN osmo-bts-omldummy $BTS_FEATURES 127.0.0.1 1234 1" C-m
tmux send-keys -t $SESSION:1.2 "$RESPAWN osmo-bts-omldummy $BTS_FEATURES 127.0.0.1 1235 1" C-m
tmux send-keys -t $SESSION:1.3 "$RESPAWN osmo-bts-omldummy $BTS_FEATURES 127.0.0.1 1236 4" C-m

tmux attach -t $SESSION:0
