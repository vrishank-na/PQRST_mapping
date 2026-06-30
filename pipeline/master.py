import dsp as dsp
import model1 as model1
import model2 as model2
import serialcomms as comms
import csvhandler as csv


def run_pipeline():
    # read ECG data from CSV/thingstreamer
    ecg_data = csv.read_ecg_csv("data/filtered_ecg.csv")

    # apply DSP
    filtered_ecg = dsp.bandpass_ecg(ecg_data)

    # pass filtered ECG
    model1_results = model1.process(filtered_ecg)

    # pass model1 results to model2
    model2_results = model2.process(model1_results)

    # pass results serially to ESP32/ArdUNO
    comms.send_results(model2_results)


if __name__ == "__main__":
    run_pipeline()
