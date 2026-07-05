from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

FILE = "locations.json"

# Ensure file exists
if not os.path.exists(FILE):
    with open(FILE, "w") as f:
        json.dump([], f)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/save", methods=["POST"])
def save():
    data = request.json
    with open(FILE, "w") as f:
        json.dump(data, f)
    return jsonify({"status": "saved"})

@app.route("/get", methods=["GET"])
def get_locations():
    with open(FILE, "r") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)