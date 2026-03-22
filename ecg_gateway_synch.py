#!/usr/bin/env python3

import csv
import time
import threading
import serial
import numpy as np
from flask import Flask, jsonify, render_template
from scipy.signal import butter, lfilter

# ==========================================================
# CONFIG
# ==========================================================
CSV_FILE = "processed_ecg.csv"
FILTERED_CSV_FILE = "filtered.csv"
SERIAL_PORT = "/dev/ttyUSB0"   # change if needed
BAUD_RATE = 115200

FS = 100.0                   # ECG sampling rate (Hz)
SAMPLE_DELAY = 1.0 / FS
FLASK_PORT = 5000

# ==========================================================
# SHARED STATE (SYNC SOURCE OF TRUTH)
# ==========================================================
ecg_buffer = []        # [{idx, value}]
pqrst_buffer = []      # last few PQRST markers
sample_index = 0

buffer_lock = threading.Lock()
filtered_csv = open(FILTERED_CSV_FILE, "w", newline="")
filtered_writer = csv.writer(filtered_csv)
filtered_writer.writerow(["idx", "ecg"])
filtered_csv.flush()

# ==========================================================
# CSV LOADER
# ==========================================================
def load_ecg_csv():
    ecg = []
    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ecg.append(float(row["ecg"]))
    return np.array(ecg)

# ==========================================================
# BUTTERWORTH FILTERS
# ==========================================================
def butter_highpass(cutoff, fs, order=2):
    nyq = 0.5 * fs
    return butter(order, cutoff / nyq, btype='high')

def butter_lowpass(cutoff, fs, order=2):
    nyq = 0.5 * fs
    return butter(order, cutoff / nyq, btype='low')

def bandpass_ecg(ecg):
    b_hp, a_hp = butter_highpass(0.5, FS)
    b_lp, a_lp = butter_lowpass(40.0, FS)
    ecg = lfilter(b_hp, a_hp, ecg)
    ecg = lfilter(b_lp, a_lp, ecg)
    return ecg

# ==========================================================
# R-PEAK DETECTION (Pan–Tompkins lite)
# ==========================================================
def detect_r_peaks(ecg):
    diff = np.diff(ecg)
    squared = diff ** 2

    window = int(0.15 * FS)
    integrated = np.convolve(
        squared, np.ones(window) / window, mode="same"
    )

    threshold = np.mean(integrated) * 1.5
    candidates = np.where(integrated > threshold)[0]

    r_peaks = []
    refractory = int(0.2 * FS)
    last = -refractory

    for c in candidates:
        if c - last >= refractory:
            r_peaks.append(c)
            last = c

    return r_peaks

# ==========================================================
# PQRST LOCALIZATION
# ==========================================================
def detect_pqrst(ecg, r_peaks):
    results = []
    for r in r_peaks:
        try:
            q = np.argmin(ecg[r-int(0.05*FS):r]) + r-int(0.05*FS)
            s = np.argmin(ecg[r:r+int(0.05*FS)]) + r
            p = np.argmax(ecg[r-int(0.2*FS):q]) + r-int(0.2*FS)
            t = np.argmax(ecg[s:s+int(0.4*FS)]) + s

            results.append({
                "P": int(p),
                "Q": int(q),
                "R": int(r),
                "S": int(s),
                "T": int(t)
            })
        except:
            continue
    return results

# ==========================================================
# ECG PIPELINE (MASTER CLOCK)
# ==========================================================
def ecg_pipeline():
    global ecg_buffer, pqrst_buffer, sample_index

    raw = load_ecg_csv()
    filtered = bandpass_ecg(raw)

    r_peaks = detect_r_peaks(filtered)
    pqrst = detect_pqrst(filtered, r_peaks)

    idx = 0
    while True:
        with buffer_lock:
            value = float(filtered[idx])
            ecg_buffer.append({
                 "idx": sample_index,
                 "value": value
            })
            # Keep buffer size manageable
            ecg_buffer[:] = ecg_buffer[-1000:]
            pqrst_buffer[:] = pqrst[-10:]

            # SAVE FILTERED ECG
            filtered_writer.writerow([sample_index, value])
            filtered_csv.flush()

            sample_index += 1

        idx = (idx + 1) % len(filtered)
        time.sleep(SAMPLE_DELAY)

# ==========================================================
# ESP32 SERIAL STREAM (SYNCED)
# ==========================================================
def esp32_sender():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("[INFO] ESP32 connected")
    except Exception as e:
        print("[ERROR] ESP32 not connected:", e)
        return

    last_processed_idx = -1
    while True:
        with buffer_lock:
            # Check if there's new data we haven't sent yet
            if ecg_buffer and ecg_buffer[-1]['idx'] > last_processed_idx:
                # Find the first sample in ecg_buffer that is newer than last_processed_idx
                for pkt in ecg_buffer:
                    if pkt['idx'] > last_processed_idx:
                        ser.write(f"{pkt['idx']},{pkt['value']}\n".encode())
                        last_processed_idx = pkt['idx']
        time.sleep(0.001)

# ==========================================================
# FLASK SERVER (SYNCED UI)
# ==========================================================
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ecg")
def ecg():
    with buffer_lock:
        return jsonify({
            "samples": ecg_buffer[-500:],
            "pqrst": pqrst_buffer
        })

def run_flask():
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)

# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    print("[INFO] Starting ECG Gateway (Synced)")

    threading.Thread(target=ecg_pipeline, daemon=True).start()
    threading.Thread(target=esp32_sender, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()

    while True:
        time.sleep(1)
