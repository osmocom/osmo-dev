#!/bin/sh

SESSION="ttcn3-pcu-test"

OSMO_DIR="/home/$USER/osmocom"
SUITE_DIR="$OSMO_DIR/osmo-ttcn3-hacks"
RESPAWN="$OSMO_DIR/scripts/respawn.sh"

tmux new-session -s $SESSION -n $SESSION -d

tmux split-window -t $SESSION:0 -v
tmux send-keys -t $SESSION:0.0 "cd $SUITE_DIR/pcu" C-m
tmux send-keys -t $SESSION:0.0 "$RESPAWN osmo-pcu -c osmo-pcu.cfg" C-m
tmux send-keys -t $SESSION:0.1 "cd $SUITE_DIR/pcu" C-m
tmux send-keys -t $SESSION:0.1 "../start-testsuite.sh pcu/PCU_Tests PCU_Tests.cfg"

tmux attach -t $SESSION:0
