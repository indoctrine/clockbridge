#!/bin/bash

# Function to stop the processes gracefully
stop_processes() {
  echo "Stopping processes..."
  # Stop Gunicorn
  pkill -TERM -P 1 gunicorn
  # Stop Nginx
  nginx -s stop
  exit 0
}

# Trap the termination signal and call the stop_processes function
trap 'stop_processes' SIGTERM

# Start Gunicorn in detached mode
gunicorn -b unix:/run/clockbridge.sock -w 4 -D app:app

# Start Nginx in the foreground
nginx -g "daemon off;"

# Sleep indefinitely to keep the script running
while true; do
  sleep 1
done

