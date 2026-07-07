import argparse
import os

try:
    from . import csvhandler as csv
    from . import dsp
    from . import model1
    from . import model2
    from . import serialcomms as comms
except ImportError:  # pragma: no cover - supports running as a script
    import csvhandler as csv
    import dsp
    import model1
    import model2
    import serialcomms as comms


DEFAULT_ECG_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ecg.csv")


def run_pipeline(input_csv=DEFAULT_ECG_CSV, fs=dsp.DEFAULT_FS, send=True):
    # read ECG data from CSV/thingstreamer
    ecg_data = csv.read_ecg_csv(input_csv)

    # apply DSP
    filtered_ecg = dsp.bandpass_ecg(ecg_data, fs=fs)

    # pass filtered ECG
    model1_results = model1.process(filtered_ecg, fs=fs)

    # pass model1 results to model2
    model2_results = model2.process(model1_results)

    # pass results serially to ESP32/ArdUNO
    if send:
        comms.send_results(model2_results)

    return model2_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ECG PQRST pipeline")
    parser.add_argument("--input", default=DEFAULT_ECG_CSV, help="ECG CSV path")
    parser.add_argument("--fs", type=float, default=dsp.DEFAULT_FS, help="Sampling rate in Hz")
    parser.add_argument("--dry-run", action="store_true", help="Print packet instead of opening serial")
    args = parser.parse_args()

    results = run_pipeline(input_csv=args.input, fs=args.fs, send=not args.dry_run)
    if args.dry_run:
        for packet in comms.format_packets(results):
            print(packet.strip())
