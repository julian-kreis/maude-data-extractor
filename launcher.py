import sys
import os
import time
import subprocess
import threading
import webbrowser
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer
import streamlit.web.cli as stcli

# Settings
STREAMLIT_PORT = 8501
HEARTBEAT_PORT = 8502
TIMEOUT_SECONDS = 300 # The streamlit process will end after 5 minutes without pings
HOST_IP = "127.0.0.1"
FLAG_WORKER = "run-streamlit-worker" # Internal flag to distinguish worker process

# == PATH DEFINITIONS == 
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    target_cwd = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
    target_cwd = base_path

app_path = os.path.join(base_path, "app.py")

# Submode 1: Runs Streamlit
def run_streamlit_internal():
    """
    This function is called when the EXE detects that it is running as a subprocess.
    It simulates a terminal command: 'streamlit run app.py ...'
    """
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.headless=true",
        f"--server.port={STREAMLIT_PORT}",
        f"--server.address={HOST_IP}",
        "--global.developmentMode=false"
    ]
    sys.exit(stcli.main())

# Submode 2: Watchdog / Launcher
last_heartbeat = time.time()

# Request Handler: Listens for pings coming from the browser
class HeartbeatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global last_heartbeat
        if self.path.startswith('/ping'):
            last_heartbeat = time.time()
            # Returns a transparent 1x1 GIF to satisfy the request efficiently
            self.send_response(200)
            self.send_header('Content-type', 'image/gif')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b')
        
    def log_message(self, format, *args):
        pass # Suppress HTTP logs to keep console clean

def start_heartbeat_server():
    server = HTTPServer((HOST_IP, HEARTBEAT_PORT), HeartbeatHandler)
    server.serve_forever()

def main_launcher():
    global last_heartbeat
    
    # Starts the heartbeat server in the background
    t = threading.Thread(target=start_heartbeat_server, daemon=True)
    t.start()

    # Starts the Streamlit worker process
    print("Starting Streamlit Worker process...")
    
    # Hides the terminal window for the subprocess on Windows
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = [sys.executable, FLAG_WORKER]
    
    proc = subprocess.Popen(
        cmd,
        cwd=target_cwd,
        startupinfo=startupinfo
    )

    # Opens the browser
    time.sleep(5)
    webbrowser.open(f"http://{HOST_IP}:{STREAMLIT_PORT}")
    
    # Activity Check Loop
    try:
        # Initial grace period for the browser to open
        last_heartbeat = time.time() + 25 
        
        while True:
            elapsed = time.time() - last_heartbeat
            if elapsed > TIMEOUT_SECONDS:
                print(f"Session timed out ({elapsed}s). Closing...")
                break 
            time.sleep(1)
    finally:
        # Cleanup: Kill the streamlit process before exiting
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except:
                proc.kill()

# Entry Point
if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Check if this process was triggered as the Worker
    if len(sys.argv) > 1 and sys.argv[1] == FLAG_WORKER:
        run_streamlit_internal()
    else:
        # If no arguments, it's the user double-clicking the EXE
        main_launcher()