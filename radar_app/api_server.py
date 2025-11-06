from flask import Flask, render_template, jsonify
import os, json

app = Flask(__name__)
LATEST_FILE = "latest.json"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/latest")
def latest():
    """
    Returns the latest transaction per lane plus lastTxn.
    Ensures lane boxes update with the newest transaction.
    """
    if os.path.exists(LATEST_FILE):
        try:
            with open(LATEST_FILE, "r") as f:
                data = json.load(f)

            # Initialize lanes 1-4 with defaults
            lane_dict = {str(i): {"speed": 0, "timestamp": "--", "overspeed": False, "txn": 0} for i in range(1,5)}

            # Pick latest transaction per lane based on txn
            last10 = data.get("last10", [])
            last10_sorted = sorted(last10, key=lambda x: x["txn"], reverse=True)
            seen_lanes = set()
            for entry in last10_sorted:
                lane = entry["lane"]
                if lane not in seen_lanes:
                    lane_dict[lane] = entry
                    seen_lanes.add(lane)

            # Include lastTxn separately
            lane_dict["lastTxn"] = data.get("latest", {})

            return jsonify(lane_dict)

        except Exception as e:
            print("Error reading latest.json:", e)
            return jsonify({})
    return jsonify({})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1212, debug=True)
