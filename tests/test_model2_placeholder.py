import numpy as np

from pipeline import model2_placeholder


def test_process_emits_multiple_beats_for_multiple_r_peaks():
    ecg = np.zeros(1000)
    ecg[150] = 2.0
    ecg[420] = 2.2
    ecg[700] = 1.8

    results = model2_placeholder.process(ecg, fs=100.0)

    assert isinstance(results, list)
    assert len(results) == 3
    assert all(result["type"] == "ecg_pqrst" for result in results)
    assert all(len(result["matrix"]) == 5 for result in results)
