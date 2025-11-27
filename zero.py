import pigpio
import socket
import time
import subprocess
import os

# -------------------- CONFIG --------------------
TX_GPIO = 21
BAUD = 19200

HOST = "0.0.0.0"
PORT = 5000

# mjpeg-streamer configuration
MJPEG_INPUT_PLUGIN = "input_uvc.so"
MJPEG_OUTPUT_PLUGIN = "output_http.so"
MJPEG_WWW_PATH = "./www"
MJPEG_PORT = 8080
MJPEG_FRAMERATE = 10

# Quality presets - maps quality to max resolution tier
QUALITY_PRESETS = {
    "720p": {
        "16:9": (1280, 720),
        "4:3": (1024, 768),
        "5:4": (1280, 1024),
        "16:10": (1280, 800)
    },
    "480p": {
        "16:9": (720, 480),
        "4:3": (640, 480),
        "5:4": (640, 512),
        "16:10": (800, 480)
    },
    "360p": {
        "16:9": (640, 360),
        "4:3": (640, 480),
        "5:4": (640, 512),
        "16:10": (640, 400)
    }
}

# Supported resolutions by your capture card
SUPPORTED_RESOLUTIONS = [
    (1920, 1080), (1600, 1200), (1360, 768), (1280, 1024),
    (1280, 960), (1280, 720), (1024, 768), (800, 600),
    (720, 576), (720, 480), (640, 480)
]

# Global process handle
mjpeg_process = None
current_quality = "720p"
target_w, target_h = 1920, 1080
stream_w, stream_h = 1280, 720

# -------------------- INIT --------------------
pi = pigpio.pi()
if not pi.connected:
    print("Cannot connect to pigpio daemon")
    exit(1)

pi.set_mode(TX_GPIO, pigpio.OUTPUT)

# -------------------- MJPEG STREAMER MANAGEMENT --------------------
def stop_mjpeg_streamer():
    """Stop mjpeg-streamer"""
    global mjpeg_process
    
    try:
        subprocess.run(['pkill', '-9', 'mjpg_streamer'], capture_output=True)
        
        if mjpeg_process:
            try:
                mjpeg_process.terminate()
                mjpeg_process.wait(timeout=2)
            except:
                mjpeg_process.kill()
            mjpeg_process = None
        
        print("[INFO] Stopped mjpg_streamer")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"[ERROR] Could not stop mjpeg-streamer: {e}")
        return False

def start_mjpeg_streamer(width, height):
    """Start mjpeg-streamer with specified resolution"""
    global mjpeg_process
    
    try:
        cmd = [
            'mjpg_streamer',
            '-i', f'{MJPEG_INPUT_PLUGIN} -d /dev/video0 -r {width}x{height} -f {MJPEG_FRAMERATE}',
            '-o', f'{MJPEG_OUTPUT_PLUGIN} -w {MJPEG_WWW_PATH} -p {MJPEG_PORT}'
        ]
        
        print(f"[INFO] Starting mjpg_streamer at {width}x{height}...")
        
        mjpeg_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        time.sleep(2)
        
        if mjpeg_process.poll() is None:
            print(f"[INFO] mjpg_streamer started successfully (PID: {mjpeg_process.pid})")
            return True
        else:
            stderr = mjpeg_process.stderr.read().decode()
            print(f"[ERROR] mjpg_streamer failed to start: {stderr}")
            mjpeg_process = None
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not start mjpeg-streamer: {e}")
        mjpeg_process = None
        return False

# -------------------- RESOLUTION FUNCTIONS --------------------
def calculate_aspect_ratio(width, height):
    """Calculate aspect ratio"""
    from math import gcd
    divisor = gcd(width, height)
    ar_w = width // divisor
    ar_h = height // divisor
    
    # Map to common aspect ratio names
    ratio_map = {
        (16, 9): "16:9",
        (4, 3): "4:3",
        (5, 4): "5:4",
        (16, 10): "16:10",
        (17, 10): "16:10",
        (8, 5): "16:10",
        (3, 2): "3:2"
    }
    
    return ratio_map.get((ar_w, ar_h), "16:9")

def find_closest_resolution(target_width, target_height, aspect_ratio, quality):
    """Find the closest supported resolution matching aspect ratio and quality"""
    
    max_res = QUALITY_PRESETS[quality].get(aspect_ratio)
    
    if not max_res:
        max_res = QUALITY_PRESETS[quality]["16:9"]
    
    max_width, max_height = max_res
    
    candidates = []
    target_ar_name = aspect_ratio
    
    for res_w, res_h in SUPPORTED_RESOLUTIONS:
        res_ar = calculate_aspect_ratio(res_w, res_h)
        
        if res_ar == target_ar_name and res_w <= max_width and res_h <= max_height:
            candidates.append((res_w, res_h))
    
    if not candidates:
        print(f"[WARN] No matching resolution found, using fallback")
        return max_res
    
    candidates.sort(key=lambda x: x[0] * x[1], reverse=True)
    chosen = candidates[0]
    
    print(f"[INFO] Chose {chosen[0]}x{chosen[1]} from {len(candidates)} candidates")
    return chosen

def choose_stream_resolution(target_width, target_height, quality):
    """Choose best stream resolution based on target aspect ratio and quality"""
    aspect_ratio = calculate_aspect_ratio(target_width, target_height)
    print(f"[INFO] Target: {target_width}x{target_height} | Aspect: {aspect_ratio} | Quality: {quality}")
    
    stream_w, stream_h = find_closest_resolution(target_width, target_height, aspect_ratio, quality)
    print(f"[INFO] Selected stream resolution: {stream_w}x{stream_h}")
    
    return stream_w, stream_h

def apply_resolution(target_w, target_h, quality):
    """Apply resolution based on aspect ratio matching and quality preset"""
    global current_quality
    current_quality = quality
    
    stream_w, stream_h = choose_stream_resolution(target_w, target_h, quality)
    
    print(f"[INFO] Applying capture resolution {stream_w}x{stream_h}")
    
    stop_mjpeg_streamer()
    start_mjpeg_streamer(stream_w, stream_h)
    
    return target_w, target_h, stream_w, stream_h

# -------------------- HELPER --------------------
def send_uart(data: str):
    """Send the string over UART using pigpio's wave_add_serial."""
    if not data:
        return

    pi.wave_clear()
    pi.wave_add_serial(TX_GPIO, BAUD, data.encode())
    wid = pi.wave_create()
    if wid >= 0:
        pi.wave_send_once(wid)
        while pi.wave_tx_busy():
            time.sleep(0.001)
        pi.wave_delete(wid)

# -------------------- CLIENT HANDLER --------------------
def handle_client(conn, addr):
    """Handle a single client connection"""
    global target_w, target_h, stream_w, stream_h, current_quality
    
    print(f"[INFO] Client connected: {addr}")
    
    try:
        # Send initial resolution to client
        conn.send(f"RESOLUTION:{target_w}:{target_h}\n".encode())
        conn.send(f"STREAM_RESOLUTION:{stream_w}:{stream_h}\n".encode())
        print(f"[INFO] Sent target: {target_w}x{target_h}, stream: {stream_w}x{stream_h}")
        
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[INFO] Client {addr} disconnected")
                break
            
            buffer += data.decode()
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                text = line.strip()
                
                if not text:
                    continue
                
                print(f"[RECV] {text}")
                
                # Handle resolution change command
                if text.startswith("SET_RESOLUTION:"):
                    parts = text.split(':')
                    if len(parts) >= 3:
                        new_width = int(parts[1])
                        new_height = int(parts[2])
                        print(f"[INFO] Client requested resolution change to {new_width}x{new_height}")
                        target_w, target_h, stream_w, stream_h = apply_resolution(new_width, new_height, current_quality)
                        conn.send(f"RESOLUTION:{target_w}:{target_h}\n".encode())
                        conn.send(f"STREAM_RESOLUTION:{stream_w}:{stream_h}\n".encode())
                        print("[INFO] Resolution change complete")
                
                # Handle quality change command
                elif text.startswith("SET_QUALITY:"):
                    parts = text.split(':')
                    if len(parts) >= 2:
                        new_quality = parts[1]
                        if new_quality in QUALITY_PRESETS:
                            print(f"[INFO] Client requested quality change to {new_quality}")
                            target_w, target_h, stream_w, stream_h = apply_resolution(target_w, target_h, new_quality)
                            conn.send(f"STREAM_RESOLUTION:{stream_w}:{stream_h}\n".encode())
                            print("[INFO] Quality change complete")
                
                else:
                    # Forward to UART
                    send_uart(text + "\n")
    
    except Exception as e:
        print(f"[ERROR] Client handler error: {e}")
    
    finally:
        conn.close()
        print(f"[INFO] Connection closed for {addr}")

# -------------------- STARTUP --------------------
print("[INFO] Starting up...")

# Start with default quality
stream_w, stream_h = choose_stream_resolution(target_w, target_h, current_quality)
start_mjpeg_streamer(stream_w, stream_h)

# -------------------- SOCKET SERVER --------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.listen(1)
print(f"[INFO] Event server running on port {PORT}...")
print(f"[INFO] Waiting for client connections...")

try:
    while True:
        # Wait for new client connection
        conn, addr = sock.accept()
        
        # Handle the client (blocking - one client at a time)
        handle_client(conn, addr)
        
        # After client disconnects, loop continues and waits for next client
        print("[INFO] Ready for new connection...")

except KeyboardInterrupt:
    print("\n[INFO] Keyboard interrupt received, shutting down...")

finally:
    print("[INFO] Cleaning up...")
    stop_mjpeg_streamer()
    sock.close()
    pi.stop()
    print("[INFO] Server stopped.")