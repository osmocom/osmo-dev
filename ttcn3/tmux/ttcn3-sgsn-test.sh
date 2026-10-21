#!/bin/sh

SESSION="ttcn3-sgsn-test"

OSMO_DIR="/home/$USER/osmocom"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $SUITE_DIR/sgsn" C-m
tmux send-keys -t $SESSION:0.0 "osmo-sgsn -c osmo-sgsn.cfg" C-m
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/sgsn" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh sgsn/SGSN_Tests SGSN_Tests.cfg"

tmux new-window -t $SESSION:1
tmux send-keys -t $SESSION:1.0 "cd $SUITE_DIR/sgsn" C-m
tmux send-keys -t $SESSION:1.0 "osmo-stp -c osmo-stp.cfg" C-m

tmux attach -t $SESSION:0
