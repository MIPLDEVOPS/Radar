#!/bin/bash
# Start listener and API server, keep alive until killed

# Source conda
source /home/vasd/anaconda3/etc/profile.d/conda.sh

# Activate environment
conda activate radar

# Start listener
python /home/vasd/radar_app/listener.py &
LISTENER_PID=$!

# Start API server
python /home/vasd/radar_app/api_server.py &
API_PID=$!

# Trap SIGTERM to stop both
trap "kill -TERM $LISTENER_PID $API_PID; exit 0" SIGTERM

# Wait forever until one of them dies
wait -n

