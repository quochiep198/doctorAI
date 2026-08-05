import os
import time
import socket
import webbrowser
import threading
import uvicorn
from dotenv import load_dotenv

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def open_browser(url, port):
    # Wait for the server to bind and start listening
    for _ in range(40):
        if not is_port_open(port):
            print(f"Opening web browser to {url}")
            webbrowser.open(url)
            break
        time.sleep(0.5)

if __name__ == "__main__":
    # Load .env variables before launching uvicorn
    load_dotenv()
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "9621"))
    
    # If host is 0.0.0.0, the browser should open 127.0.0.1
    browser_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{browser_host}:{port}/"
    
    print(f"Launching Doctor AI Backend on {host}:{port}...")
    
    # Start the browser thread
    threading.Thread(target=open_browser, args=(url, port), daemon=True).start()
    
    # Run uvicorn server pointing to index.py
    uvicorn.run("index:app", host=host, port=port, log_level="info")
