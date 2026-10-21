#!/bin/sh

SESSION="ttcn3-s1gw-test"

OSMO_DIR="/home/$USER/osmocom"
S1GW_DIR="$OSMO_DIR/osmo-s1gw"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $S1GW_DIR" C-m
tmux send-keys -t $SESSION:0.0 "make shell CONFIG=$SUITE_DIR/s1gw/osmo-s1gw.config" C-m
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/s1gw" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh s1gw/S1GW_Tests S1GW_Tests.cfg"

tmux attach -t $SESSION:0
