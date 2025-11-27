import tkinter as tk
from tkinter import Menu
from PIL import Image, ImageTk
import requests
from io import BytesIO
import socket
import threading
import time

# ---------------- CONFIGURATION ----------------
PI_IP = "192.168.137.242"
EVENT_PORT = 5000
STREAM_URL = f"http://{PI_IP}:8080/?action=stream"

# Mouse keyboard control settings
MOUSE_SPEED_SLOW = 5      # pixels per key press
MOUSE_SPEED_FAST = 15     # pixels when holding Shift

# Resolution tracking
target_resolution = (1920, 1080)  # Default, will be updated
stream_resolution = (1280, 720)   # Default, will be detected
resolution_detected = False
current_quality = "720p"  # Default quality preset

# Stream control
stream_active = True
stream_reconnect_flag = False

# ---------------- TCP SENDER ----------------
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((PI_IP, EVENT_PORT))
    print("[DEBUG] Connected to Pi event server")
except Exception as e:
    print("[ERROR] Could not connect to Pi:", e)
    exit(1)

def send(cmd):
    try:
        sock.send((cmd + "\n").encode())
        print(f"[SEND] {cmd}")
    except Exception as e:
        print("[ERROR] Failed to send:", e)

# ---------------- RESOLUTION LISTENER ----------------
def listen_for_resolution():
    """Listen for resolution info from Pi Zero"""
    global target_resolution, stream_resolution, resolution_detected, stream_reconnect_flag
    try:
        while True:
            data = sock.recv(1024)
            if not data:
                break
            
            message = data.decode().strip()
            print(f"[RECV] {message}")
            
            if message.startswith("RESOLUTION:"):
                parts = message.split(':')
                if len(parts) >= 3:
                    width = int(parts[1])
                    height = int(parts[2])
                    target_resolution = (width, height)
                    print(f"[INFO] Target PC resolution set to: {width}x{height}")
                    update_resolution_display()
            elif message.startswith("STREAM_RESOLUTION:"):
                parts = message.split(':')
                if len(parts) >= 3:
                    width = int(parts[1])
                    height = int(parts[2])
                    old_resolution = stream_resolution
                    stream_resolution = (width, height)
                    resolution_detected = True
                    print(f"[INFO] Stream resolution changed to: {width}x{height}")
                    
                    # Trigger stream reconnection if resolution actually changed
                    if old_resolution != stream_resolution:
                        print("[INFO] Triggering stream reconnection...")
                        stream_reconnect_flag = True
                    
                    update_resolution_display()
    except Exception as e:
        print(f"[ERROR] Resolution listener error: {e}")

# Start resolution listener thread
threading.Thread(target=listen_for_resolution, daemon=True).start()

# ---------------- TKINTER GUI ----------------
root = tk.Tk()
root.title("Remote Pi Zero Viewer")
root.geometry("1280x768")

# Create menu bar
menubar = Menu(root)
root.config(menu=menubar)

# Resolution menu
resolution_menu = Menu(menubar, tearoff=0)
menubar.add_cascade(label="Target Resolution", menu=resolution_menu)

def set_resolution(width, height):
    """Set target resolution and notify Pi Zero"""
    global target_resolution
    target_resolution = (width, height)
    send(f"SET_RESOLUTION:{width}:{height}")
    print(f"[INFO] Manually set target resolution to {width}x{height}")
    update_resolution_display()

# Common target resolutions
resolution_menu.add_command(label="1920x1080 (16:9)", command=lambda: set_resolution(1920, 1080), accelerator="Ctrl+1")
resolution_menu.add_command(label="1280x720 (16:9)", command=lambda: set_resolution(1280, 720), accelerator="Ctrl+2")
resolution_menu.add_command(label="2560x1440 (16:9)", command=lambda: set_resolution(2560, 1440), accelerator="Ctrl+3")
resolution_menu.add_command(label="3840x2160 (16:9)", command=lambda: set_resolution(3840, 2160), accelerator="Ctrl+4")
resolution_menu.add_separator()
resolution_menu.add_command(label="1024x768 (4:3)", command=lambda: set_resolution(1024, 768), accelerator="Ctrl+5")
resolution_menu.add_command(label="1280x1024 (5:4)", command=lambda: set_resolution(1280, 1024), accelerator="Ctrl+6")
resolution_menu.add_command(label="1600x1200 (4:3)", command=lambda: set_resolution(1600, 1200), accelerator="Ctrl+7")

# Quality menu
quality_menu = Menu(menubar, tearoff=0)
menubar.add_cascade(label="Stream Quality", menu=quality_menu)

def set_quality(quality_preset):
    """Set stream quality preset"""
    global current_quality, stream_reconnect_flag
    current_quality = quality_preset
    send(f"SET_QUALITY:{quality_preset}")
    print(f"[INFO] Set quality to {quality_preset}")
    update_resolution_display()
    
    # Trigger stream reconnection after brief delay
    def delayed_reconnect():
        time.sleep(1)  # Give Pi time to reconfigure
        global stream_reconnect_flag
        stream_reconnect_flag = True
        print("[INFO] Triggering stream reconnection for quality change...")
    
    threading.Thread(target=delayed_reconnect, daemon=True).start()

quality_menu.add_command(label="720p (Best Quality)", command=lambda: set_quality("720p"), accelerator="F1")
quality_menu.add_command(label="480p (Balanced)", command=lambda: set_quality("480p"), accelerator="F2")
quality_menu.add_command(label="360p (Low Latency)", command=lambda: set_quality("360p"), accelerator="F3")

# Bind keyboard shortcuts for resolution
root.bind('<Control-Key-1>', lambda e: set_resolution(1920, 1080))
root.bind('<Control-Key-2>', lambda e: set_resolution(1280, 720))
root.bind('<Control-Key-3>', lambda e: set_resolution(2560, 1440))
root.bind('<Control-Key-4>', lambda e: set_resolution(3840, 2160))
root.bind('<Control-Key-5>', lambda e: set_resolution(1024, 768))
root.bind('<Control-Key-6>', lambda e: set_resolution(1280, 1024))
root.bind('<Control-Key-7>', lambda e: set_resolution(1600, 1200))

# Bind keyboard shortcuts for quality
root.bind('<F1>', lambda e: set_quality("720p"))
root.bind('<F2>', lambda e: set_quality("480p"))
root.bind('<F3>', lambda e: set_quality("360p"))

# Create a frame to hold the label
frame = tk.Frame(root, bg='black')
frame.pack(fill=tk.BOTH, expand=True)

# Label with black background to reduce flicker
label = tk.Label(frame, bg='black')
label.pack(fill=tk.BOTH, expand=True)

# Status label for resolution info
status_label = tk.Label(root, text="", bg='gray20', fg='white', anchor='w')
status_label.pack(side=tk.BOTTOM, fill=tk.X)

def update_resolution_display():
    """Update the status bar with resolution info"""
    status_text = f"Quality: {current_quality} | Target: {target_resolution[0]}x{target_resolution[1]} | Stream: {stream_resolution[0]}x{stream_resolution[1]}"
    if target_resolution != stream_resolution:
        scale_x = target_resolution[0] / stream_resolution[0]
        scale_y = target_resolution[1] / stream_resolution[1]
        status_text += f" | Scale: {scale_x:.2f}x, {scale_y:.2f}y"
    status_label.config(text=status_text)

# Set focus to ensure keyboard events are captured
label.focus_set()

# Store current image dimensions
current_img = None
current_aspect_ratio = 16/9

# ---------------- KEY MAPPING ----------------
key_map = {
    "Return": "ENTER",
    "Escape": "ESC",
    "BackSpace": "BACKSPACE",
    "Tab": "TAB",
    "space": "SPACE",
    "Left": "LEFT",
    "Right": "RIGHT",
    "Up": "UP",
    "Down": "DOWN",
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
    "Super_L": "WIN",
    "Super_R": "RWIN",
    "Shift_L": "SHIFT",
    "Shift_R": "SHIFT",
    "Control_L": "CTRL",
    "Control_R": "CTRL",
    "Alt_L": "ALT",
    "Alt_R": "ALT",
}

# Keep track of currently pressed modifiers
pressed_modifiers = set()
backtick_pressed = False

# Track last mouse position for relative movement
last_mouse_x = 0
last_mouse_y = 0

# ---------------- RESPONSIVE RESIZE ----------------
def calculate_fit_size(img_width, img_height, container_width, container_height):
    """Calculate size to fit image in container while maintaining aspect ratio"""
    img_aspect = img_width / img_height
    container_aspect = container_width / container_height
    
    if img_aspect > container_aspect:
        new_width = container_width
        new_height = int(container_width / img_aspect)
    else:
        new_height = container_height
        new_width = int(container_height * img_aspect)
    
    return new_width, new_height

def on_resize(event):
    """Handle window resize events and update image display"""
    global current_img
    if current_img:
        update_image_display(current_img)

root.bind('<Configure>', on_resize)

def update_image_display(img):
    """Update the image display with proper scaling"""
    global current_img, current_aspect_ratio, stream_resolution, resolution_detected
    current_img = img
    current_aspect_ratio = img.width / img.height
    
    # Detect stream resolution changes
    if (img.width, img.height) != stream_resolution:
        stream_resolution = (img.width, img.height)
        resolution_detected = True
        print(f"[INFO] Stream resolution detected: {img.width}x{img.height}")
        update_resolution_display()
    
    # Get current label dimensions
    label.update_idletasks()
    width = label.winfo_width()
    height = label.winfo_height()
    
    # Calculate fitted size
    if width > 1 and height > 1:
        new_width, new_height = calculate_fit_size(img.width, img.height, width, height)
        
        # Resize image with high-quality resampling
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(img_resized)
        
        # Keep a reference to prevent garbage collection
        label.imgtk = imgtk
        label.configure(image=imgtk)

# ---------------- EVENT HANDLERS ----------------
def on_key(event):
    global backtick_pressed
    
    key = event.keysym
    
    # Track backtick press
    if key == 'grave' or event.char == '`':
        backtick_pressed = True
        return
    
    # If backtick is held, handle arrow keys as mouse movement
    if backtick_pressed:
        speed = MOUSE_SPEED_SLOW if "Shift_L" in pressed_modifiers or "Shift_R" in pressed_modifiers else MOUSE_SPEED_FAST
        
        if key == 'Up':
            send(f"MOUSE:MOVE:0:{-speed}")
            return
        elif key == 'Down':
            send(f"MOUSE:MOVE:0:{speed}")
            return
        elif key == 'Left':
            send(f"MOUSE:MOVE:{-speed}:0")
            return
        elif key == 'Right':
            send(f"MOUSE:MOVE:{speed}:0")
            return
        elif key == 'Return':
            send("MOUSE:CLICK")
            return
        elif key == 'BackSpace':
            send("MOUSE:RCLICK")
            return
        elif key == 'bracketleft' or event.char == '[':
            send("MOUSE:SCROLL:1")
            return
        elif key == 'bracketright' or event.char == ']':
            send("MOUSE:SCROLL:-1")
            return
    
    # Normal keyboard handling
    key_to_send = key_map.get(key, event.char)
    
    if event.char == ' ' and key != 'space':
        key_to_send = 'SPACE'
    
    if not key_to_send:
        return

    if key_to_send in ("CTRL", "SHIFT", "ALT", "WIN", "RWIN"):
        if key not in pressed_modifiers:
            pressed_modifiers.add(key)
            send(f"KEY:{key_to_send}")
        return

    if pressed_modifiers:
        combo = '+'.join([key_map[k] for k in pressed_modifiers] + [key_to_send])
        send(f"KEY:{combo}")
    else:
        send(f"KEY:{key_to_send}")

def on_key_release(event):
    global backtick_pressed
    
    key = event.keysym
    
    if key == 'grave' or event.char == '`':
        backtick_pressed = False
        return
    
    key_to_send = key_map.get(key, None)
    
    if key_to_send in ("CTRL", "SHIFT", "ALT", "WIN", "RWIN"):
        if key in pressed_modifiers:
            pressed_modifiers.remove(key)
            send(f"KEYUP:{key_to_send}")

def on_click(event):
    label.focus_set()
    send("MOUSE:CLICK")

def scale_mouse_movement(dx, dy):
    """Scale mouse movement from stream coordinates to target PC coordinates"""
    global stream_resolution, target_resolution
    
    if stream_resolution == target_resolution:
        return dx, dy
    
    scale_x = target_resolution[0] / stream_resolution[0]
    scale_y = target_resolution[1] / stream_resolution[1]
    
    scaled_dx = int(dx * scale_x)
    scaled_dy = int(dy * scale_y)
    
    return scaled_dx, scaled_dy

def on_move(event):
    global last_mouse_x, last_mouse_y
    
    dx = event.x - last_mouse_x
    dy = event.y - last_mouse_y
    last_mouse_x = event.x
    last_mouse_y = event.y
    
    scaled_dx, scaled_dy = scale_mouse_movement(dx, dy)
    
    if abs(scaled_dx) > 0 or abs(scaled_dy) > 0:
        send(f"MOUSE:MOVE:{scaled_dx}:{scaled_dy}")

def on_right_click(event):
    label.focus_set()
    send("MOUSE:RCLICK")

root.bind("<Button-3>", on_right_click)

root.bind("<KeyPress>", on_key)
root.bind("<KeyRelease>", on_key_release)
root.bind("<Button-1>", on_click)
root.bind("<Motion>", on_move)

# ---------------- MJPEG STREAM ----------------
def mjpeg_loop():
    """Main MJPEG streaming loop with automatic reconnection"""
    global stream_active, stream_reconnect_flag
    
    while stream_active:
        try:
            print("[DEBUG] Connecting to MJPEG stream...")
            r = requests.get(STREAM_URL, stream=True, timeout=5)
            bytes_buffer = b''
            
            for chunk in r.iter_content(chunk_size=1024):
                # Check if reconnection is requested
                if stream_reconnect_flag:
                    print("[INFO] Stream reconnection requested, closing current connection...")
                    stream_reconnect_flag = False
                    r.close()
                    time.sleep(0.5)  # Brief pause before reconnecting
                    break
                
                bytes_buffer += chunk
                a = bytes_buffer.find(b'\xff\xd8')
                b = bytes_buffer.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    img = Image.open(BytesIO(jpg))
                    
                    root.after(0, update_image_display, img)
                    
        except requests.exceptions.Timeout:
            print("[WARNING] Stream connection timeout, retrying...")
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] MJPEG stream failed: {e}")
            if stream_active:
                print("[INFO] Reconnecting in 2 seconds...")
                time.sleep(2)
            else:
                break

threading.Thread(target=mjpeg_loop, daemon=True).start()

def on_closing():
    """Clean shutdown"""
    global stream_active
    print("[DEBUG] Closing application...")
    stream_active = False
    sock.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

print("[DEBUG] Program finished")