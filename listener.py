import socket
import threading
import os
import json
from datetime import datetime
from collections import deque
import mysql.connector   # pip install mysql-connector-python

# ---------------- CONFIG ----------------
LOG_FOLDER = "Logs"
LOG_FILE = os.path.join(LOG_FOLDER, "UdpLog.txt")
LATEST_FILE = "latest.json"
CONFIG_FILE = "config.json"

lane_timers = {}
timer_lock = threading.Lock()
transactions = deque(maxlen=10)   # last 10 for UI
txn_counter = 0  # will be initialized from DB

# ---------------- MYSQL CONFIG ----------------
DB_CONFIG = {
    "host": "localhost",
    "user": "metro",
    "password": "password123",
    "database": "metro_vasd"
}

# ---------------- DATABASE INIT ----------------
def init_db():
    global txn_counter
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS radr_trancetion (
                id INT AUTO_INCREMENT PRIMARY KEY,
                txn_no INT,
                lane VARCHAR(10),
                speed INT,
                timestamp DATETIME,
                overspeed BOOLEAN
            )
        """)
        conn.commit()

        # fetch last txn_no
        cur.execute("SELECT COALESCE(MAX(txn_no), 0) FROM radr_trancetion")
        txn_counter = cur.fetchone()[0]
        print(f"✅ MySQL table ready. Last txn_no = {txn_counter}")
        conn.close()
    except Exception as e:
        print("DB init error:", e)

def insert_mysql(entry):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO radr_trancetion (txn_no, lane, speed, timestamp, overspeed) VALUES (%s,%s,%s,%s,%s)",
            (entry["txn"], entry["lane"], entry["speed"], entry["timestamp"], entry["overspeed"])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB insert error:", e)

# ---------------- LOAD CONFIG ----------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "radarIP": "192.168.77.131",
            "radarPort": 62206,
            "ufdPort": 4001,
            "displays": [
                {"lane": "1", "ip": "192.168.77.132", "port": 4001},
                {"lane": "2", "ip": "192.168.77.133", "port": 4001},
                {"lane": "3", "ip": "192.168.78.134", "port": 4001},
                {"lane": "4", "ip": "192.168.78.135", "port": 4001}
            ]
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

config = load_config()
RADAR_UDP_IP = config.get("radarIP", "0.0.0.0")
RADAR_UDP_PORT = int(config.get("radarPort", 5000))
UFD_TCP_PORT = int(config.get("ufdPort", 4001))
LANE_IPS = {d["lane"]: d for d in config.get("displays", [])}

print(f"Radar UDP: {RADAR_UDP_IP}:{RADAR_UDP_PORT}")
for lane, display in LANE_IPS.items():
    print(f"Lane {lane} UFD: {display['ip']}:{display['port']}")

# ---------------- HELPERS ----------------
def log_to_file(message: str):
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

def save_transaction(lane, speed, dt):
    """Save into JSON (last10) + MySQL with persistent txn_no"""
    global txn_counter, transactions
    txn_counter += 1
    entry = {
        "txn": txn_counter,
        "lane": lane,
        "speed": speed,
        "timestamp": dt,
        "overspeed": speed > 80
    }
    transactions.appendleft(entry)

    # save JSON for UI
    data = {"latest": entry, "last10": list(transactions)}
    with open(LATEST_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # save to MySQL
    insert_mysql(entry)

def send_tcp_message(ip, port, message):
    try:
        if not message.endswith("\r\n"):
            message += "\r\n"
        with socket.create_connection((ip, port), timeout=5) as s:
            s.sendall(message.encode("ascii"))
        tag = "CLEAR" if "|C|" in message else "DISPLAY"
        log = f"[{tag}] Sent to {ip}:{port} => {message.strip()}"
        print(log)
        log_to_file(log)
    except Exception as e:
        error = f"TCP send error to {ip}:{port} => {e}"
        print(error)
        log_to_file(error)

def reset_lane_timer(lane, ip, port, clear_msg, duration=5.0):
    with timer_lock:
        if lane in lane_timers:
            lane_timers[lane].cancel()
        timer = threading.Timer(duration, send_tcp_message, args=(ip, port, clear_msg))
        lane_timers[lane] = timer
        timer.start()

# ---------------- CORE HANDLER ----------------
def handle_packet(text, addr=None):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {addr}: {text}" if addr else f"[{timestamp}] {text}"
        print(log_entry)
        log_to_file(log_entry)

        parts = text.split(",")
        if len(parts) < 4:
            return
        lane = parts[2].strip()
        try:
            speed = int(parts[3])
        except:
            return
        dt = parts[4] if len(parts) > 4 else timestamp

        save_transaction(lane, speed, dt)

        # UFD display duration
        if speed <= 50: duration = 4.0
        elif speed <= 60: duration = 3.0
        elif speed <= 80: duration = 2.0
        else: duration = 1.5

        # UFD message
        if speed > 80:
            show_msg = f"|T|22-18|{speed}|7|1|1|1|"  # Red flashing
        else:
            show_msg = f"|T|22-18|{speed}|7|2|1|1|"  # Green flashing

        clear_msg = "|C|0-0|128-128|"
        display = LANE_IPS.get(lane)
        if display:
            send_tcp_message(display["ip"], display["port"], show_msg)
            reset_lane_timer(lane, display["ip"], display["port"], clear_msg, duration)

    except Exception as e:
        print("Handle error:", e)
        log_to_file(f"Handle error: {e}")

# ---------------- UDP LISTENER ----------------
def udp_listener():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((RADAR_UDP_IP, RADAR_UDP_PORT))
        print(f"Listening for UDP packets on {RADAR_UDP_IP}:{RADAR_UDP_PORT}...")
    except Exception as e:
        print("UDP Listener failed:", e)
        return

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            text = data.decode("utf-8").strip()
            threading.Thread(target=handle_packet, args=(text, addr), daemon=True).start()
        except Exception as e:
            print("UDP Error:", e)

# ---------------- MANUAL INPUT ----------------
def manual_input():
    print("Manual input mode. Type 'exit' to quit.\n")
    while True:
        try:
            lane = input("Enter Lane number (1-4): ").strip()
            if lane.lower() == "exit":
                break
            if lane not in LANE_IPS:
                print("Invalid lane! Must be 1-4.")
                continue
            speed_input = input("Enter Speed (km/h): ").strip()
            try:
                speed = int(speed_input)
            except:
                print("Invalid speed! Must be a number.")
                continue

            dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            packet = f"MZ,0,{lane},{speed},{dt},1,"
            handle_packet(packet)
            print(f"Lane {lane} speed {speed} km/h sent at {dt}\n")

        except KeyboardInterrupt:
            print("\nExiting manual mode.")
            break

# ---------------- MAIN ----------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Radar UDP Listener + Manual Input + MySQL + JSON")
    parser.add_argument("--manual", action="store_true", help="Enable manual input mode")
    args = parser.parse_args()

    # Initialize DB & get last txn_no
    init_db()

    if args.manual:
        threading.Thread(target=udp_listener, daemon=True).start()
        manual_input()
    else:
        udp_listener()
