#!/bin/bash

# RemotePi - Service Orchestration Daemon
# Controls the lifecycle of video streaming and input socket servers
# Usage: ./service_manager.sh {start|stop|status|restart}

PID_DIR="/var/run/remotepi"
LOG_DIR="/var/log/remotepi"
VIDEO_PID="$PID_DIR/mjpg.pid"
INPUT_PID="$PID_DIR/python_server.pid"

setup_env() {
    mkdir -p $PID_DIR
    mkdir -p $LOG_DIR
    # Ensure the GPIO daemon is running for UART timing
    if ! pgrep -x "pigpiod" > /dev/null; then
        echo "Starting pigpio daemon..."
        pigpiod
        sleep 1
    fi
}

start_services() {
    setup_env
    echo "Starting RemotePi Services..."

    # 1. Start MJPEG Streamer
    if [ -f "$VIDEO_PID" ] && kill -0 $(cat "$VIDEO_PID") 2>/dev/null; then
        echo "Video stream already running."
    else
        echo "Initializing MJPEG Streamer (Port 8080)..."
        mjpg_streamer -i "input_uvc.so -d /dev/video0 -r 1280x720 -f 30" \
                      -o "output_http.so -w /usr/local/www -p 8080" \
                      >> "$LOG_DIR/video.log" 2>&1 &
        echo $! > "$VIDEO_PID"
    fi

    # 2. Start Python Input Server
    if [ -f "$INPUT_PID" ] && kill -0 $(cat "$INPUT_PID") 2>/dev/null; then
        echo "Input server already running."
    else
        echo "Initializing TCP Input Server (Port 5000)..."
        python3 /opt/remotepi/server.py >> "$LOG_DIR/input.log" 2>&1 &
        echo $! > "$INPUT_PID"
    fi
    
    echo "All services started."
}

stop_services() {
    echo "Stopping RemotePi Services..."
    
    if [ -f "$VIDEO_PID" ]; then
        kill -SIGTERM $(cat "$VIDEO_PID") 2>/dev/null
        rm "$VIDEO_PID"
        echo "Stopped MJPEG Streamer."
    fi

    if [ -f "$INPUT_PID" ]; then
        kill -SIGTERM $(cat "$INPUT_PID") 2>/dev/null
        rm "$INPUT_PID"
        echo "Stopped Input Server."
    fi
}

check_status() {
    echo "--- RemotePi System Status ---"
    
    # Check Video
    if [ -f "$VIDEO_PID" ] && kill -0 $(cat "$VIDEO_PID") 2>/dev/null; then
        echo -e "Video Service:\t [ACTIVE] (PID: $(cat $VIDEO_PID))"
    else
        echo -e "Video Service:\t [INACTIVE]"
    fi
    
    # Check Input
    if [ -f "$INPUT_PID" ] && kill -0 $(cat "$INPUT_PID") 2>/dev/null; then
        echo -e "Input Service:\t [ACTIVE] (PID: $(cat $INPUT_PID))"
    else
        echo -e "Input Service:\t [INACTIVE]"
    fi

    # Check Network Ports
    echo "Active Ports:"
    netstat -tuln | grep -E '8080|5000'
}

case "$1" in
    start)   start_services ;;
    stop)    stop_services ;;
    status)  check_status ;;
    restart) stop_services; sleep 2; start_services ;;
    *) echo "Usage: $0 {start|stop|status|restart}" ;;
esac
