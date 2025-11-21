#!/bin/bash
# Start listener and API server, keep alive until killed

USER_HOME="$HOME"

# Source conda dynamically
if [ -f "$USER_HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$USER_HOME/anaconda3/etc/profile.d/conda.sh"
else
    echo "conda.sh not found in $USER_HOME/anaconda3/etc/profile.d/"
    exit 1
fi

# Activate environment
conda activate radar

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start listener
python $SCRIPT_DIR/listener.py &
LISTENER_PID=$!

# Start API server
python $SCRIPT_DIR/api_server.py &
API_PID=$!

# Trap SIGTERM to stop both
trap "kill -TERM $LISTENER_PID $API_PID; exit 0" SIGTERM

# Wait forever until one of them dies
wait -n

