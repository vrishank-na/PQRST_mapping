
# figure_generation_helpers.py
"""
Inference helper template for R3/R6 figure generation.

NOTE:
This file was generated from the conversation context. It is intended to be
pasted into your notebook or adapted alongside it. Since the notebook itself
was not fully available in this environment, a few helper symbols must already
exist in memory (PRE, DATA_DIR, LUDB_DIR, records, train_records, etc.).

Sections:
1. Model definitions (RPeakGuidedML2 / RPeakTimeML2)
2. Rebuild QTDB/LUDB beat datasets
3. Load checkpoints
4. Generate R3/R6 predictions
5. Plot Figure 3 and Figure 4

Fill in any missing helper imports from your notebook if Python reports a
NameError.
"""

# === Paste the model definitions from your notebook here ===
# CNNFeatureExtractor
# BiLSTMBlock
# RPeakGuidedML2
# RPeakTimeML2ForReport

# === Reuse build_qtdb_beats() and build_ludb_beats() from your notebook ===

# === Recompute ===
# X_r5, Y_r5, ids_r5 = build_qtdb_beats(R5_POST)
# X_ludb_r5, Y_ludb_r5, ludb_ids_r5 = build_ludb_beats(R5_POST)

# === Normalization ===
# r5_mean = X_r5[r5_train_mask].mean()
# r5_std = X_r5[r5_train_mask].std()

# === Load checkpoints ===
# r3_model.load_state_dict(torch.load(R3_MODEL_SAVE_PATH, map_location=device))
# r6_qtdb_model.load_state_dict(torch.load(R6_MODEL_SAVE_PATH, map_location=device))
# r6_ludb_model.load_state_dict(torch.load(R6_ADAPTED_MODEL_SAVE_PATH, map_location=device))

# === Predict ===
# Reuse predict_in_small_batches() and add_r6_time_channel() from analytics cell.

# === Plot ===
# Figure 3:
#   QTDB ECG / Ground Truth / R3 Prediction
#
# Figure 4:
#   LUDB ECG / Ground Truth / Baseline (R3) / Proposed Framework (R6)
