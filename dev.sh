#!/bin/sh
tmux new-session -s donglify   -n code -d

tmux new-window  -t donglify:2 -n run
tmux new-window  -t donglify:3 -n files
tmux new-window  -t donglify:4 -n git

tmux send-keys -t 'files' 'man tmux' Enter
tmux send-keys -t 'git' 'git log' Enter

tmux select-window -t donglify:1
tmux -2 attach-session -t donglify
