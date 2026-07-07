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
DEFAULT_NUM_BEATS = 20


def run_pipeline(input_csv=DEFAULT_ECG_CSV, fs=dsp.DEFAULT_FS, send=True,
                  num_beats=DEFAULT_NUM_BEATS, start_row=0):
    # ecg.csv stores one pre-segmented heartbeat per row (plus a label
    # column). Reading just row 0 forever was why the pipeline only ever
    # produced 1-2 beats before going quiet - there was no code path that
    # touched any other row. Read a run of rows and stitch them into one
    # continuous stream instead.
    rows = csv.read_ecg_rows(input_csv, start=start_row, count=num_beats)
    row_duration_ms = (len(rows[0]) / fs) * 1000.0

    combined_results = []
    for row_index, row_samples in enumerate(rows):
        # apply DSP
        filtered_ecg = dsp.bandpass_ecg(row_samples, fs=fs)

        # pass filtered ECG
        model1_results = model1.process(filtered_ecg, fs=fs)

        # pass model1 results to model2
        model2_results = model2.process(model1_results)

        # Each row's beat(s) come back with r_time_ms local to that single
        # ~1.4s row. Offset by the row's own position in the stream so
        # beats form one continuous timeline instead of all restarting
        # at t=0 - this is what lets serialcomms pace beats by real time
        # instead of collapsing every row back to the same instant.
        row_offset_ms = row_index * row_duration_ms
        for beat in model2_results:
            beat = dict(beat)
            beat["r_time_ms"] = beat.get("r_time_ms", 0) + row_offset_ms
            combined_results.append(beat)

    # pass results serially to ESP32/ArdUNO
    if send:
        comms.send_results(combined_results)

    return combined_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ECG PQRST pipeline")
    parser.add_argument("--input", default=DEFAULT_ECG_CSV, help="ECG CSV path")
    parser.add_argument("--fs", type=float, default=dsp.DEFAULT_FS, help="Sampling rate in Hz")
    parser.add_argument("--beats", type=int, default=DEFAULT_NUM_BEATS,
                         help="Number of CSV rows/heartbeats to stitch into the stream")
    parser.add_argument("--start-row", type=int, default=0, help="First CSV row to read")
    parser.add_argument("--dry-run", action="store_true", help="Print packet instead of opening serial")
    args = parser.parse_args()

    results = run_pipeline(
        input_csv=args.input, fs=args.fs, send=not args.dry_run,
        num_beats=args.beats, start_row=args.start_row,
    )
    if args.dry_run:
        for packet in comms.format_packets(results):
            print(packet.strip())
