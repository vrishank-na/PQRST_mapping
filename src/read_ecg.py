import pandas as pd
import matplotlib.pyplot as plt
from r_detect import detect_r_peaks
from rr_predict import compute_rr, predict_next
from phase_scheduler import schedule_phases
from phase_executor import execute_phases

# Load ECG
data = pd.read_csv("../data/filtered_ecg.csv")
time_vals = data['time'].values
volt_vals = data['voltage'].values

print("First 10 samples:")
for i in range(min(10, len(time_vals))):
    print(time_vals[i], volt_vals[i])

# Detect R-peaks
peaks = detect_r_peaks(time_vals, volt_vals)

print("\nDetected R-peaks:")
for p in peaks:
    print("R at time:", p[0], "voltage:", p[1])

# Compute RR and predict next beat
R_times, RR = compute_rr(peaks)

print("\nRR intervals:", RR)

result = predict_next(R_times, RR)
if result:
    t_next, RR_last = result
    print("\nPredicted next R at:", t_next)
    print("Last RR:", RR_last)

    # Schedule phases
    phases = schedule_phases(t_next, RR_last)

    print("\nScheduled phases:")
    for k, v in phases.items():
        print(k, "at", v)

    # Execute phases in real time
    print("\nExecuting phases in real time...\n")
    execute_phases(phases)

# Plot ECG + peaks
plt.figure()
plt.plot(time_vals, volt_vals, label="Filtered ECG")

if len(peaks) > 0:
    plt.scatter([p[0] for p in peaks],
                [p[1] for p in peaks],
                color='red', label="R-peaks")

plt.xlabel("Time (s)")
plt.ylabel("Voltage")
plt.title("ECG with R-peaks")
plt.legend()
plt.show()
