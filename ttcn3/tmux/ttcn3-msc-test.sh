#!/bin/sh

SESSION="ttcn3-msc-test"

OSMO_DIR="/home/$USER/osmocom"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"

if [ ! -d $SUITE_DIR ]; then
	echo "Directory '$SUITE_DIR' does not exist"
	echo "Please specify where to find osmo-ttcn3-hacks"
	exit 1
fi

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $SUITE_DIR/msc" C-m
tmux send-keys -t $SESSION:0.0 "osmo-msc -c osmo-msc.cfg" C-m
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/msc" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh ./MSC_Tests MSC_Tests.cfg"

tmux new-window -t $SESSION:1
tmux send-keys -t $SESSION:1.0 "cd $SUITE_DIR/msc" C-m
tmux send-keys -t $SESSION:1.0 "osmo-stp -c osmo-stp.cfg" C-m

tmux attach -t $SESSION:0
