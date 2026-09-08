# Colab-ready ECG training runner for the fixed QTDB/LUDB protocol.
#
# Use this in Google Colab with an L4 GPU. It is intentionally written as a
# runnable Python script so it can be uploaded and executed with a single command,
# without needing the interactive notebook state from the local workspace.
#
# Typical Colab usage:
#   !pip install -q torch pandas numpy scipy scikit-learn wfdb
#   from google.colab import drive
#   drive.mount('/content/drive')
#   %cd /content/drive/MyDrive/your/project/PQRST_mapping
#   !python colab_l4_ecg_train.py --seed 1 --run-id run_01
#
# If your data is on Drive, place it under:
#   /content/drive/MyDrive/.../physionet.org/files/qtdb/1.0.0
#   /content/drive/MyDrive/.../physionet.org/files/ludb/1.0.1/data
# or set the paths explicitly with the CLI flags below.

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from scipy.signal import butter, find_peaks, resample_poly, sosfiltfilt
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset
import wfdb


PRE = 120
POST = 240
R5_POST = 320
BATCH_SIZE = 64
NUM_EPOCHS = 30
R6_ADAPT_EPOCHS = 8
TRAINING_SEEDS = [1, 2, 3, 4, 5]


def set_global_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, 'cudnn',):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def parse_args():
    parser = argparse.ArgumentParser(description='Train and evaluate the ECG segmentation model in a Colab/L4 environment.')
    parser.add_argument('--qtdb-dir', type=str, default=None, help='Path to the QTDB directory, e.g. /content/drive/.../physionet.org/files/qtdb/1.0.0')
    parser.add_argument('--ludb-dir', type=str, default=None, help='Path to the LUDB data directory, e.g. /content/drive/.../physionet.org/files/ludb/1.0.1/data')
    parser.add_argument('--artifact-dir', type=str, default='reviewer2_artifacts', help='Directory to store output CSVs/checkpoints.')
    parser.add_argument('--seed', type=int, default=1, help='Training seed to run for a single seed.')
    parser.add_argument('--run-id', type=str, default='run_01', help='Run label used for outputs.')
    parser.add_argument('--single-seed', action='store_true', help='Run only one seed instead of the full five-seed sweep.')
    return parser.parse_args()


def first_existing(*paths):
    for p in paths:
        candidate = Path(p)
        if candidate.exists():
            return candidate
    return Path(paths[0])


def detect_data_dirs(qtdb_dir=None, ludb_dir=None):
    repo_root = Path.cwd()
    if qtdb_dir is None:
        qtdb_dir = first_existing(
            repo_root / 'physionet.org/files/qtdb/1.0.0',
            repo_root / 'PQRST_mapping/physionet.org/files/qtdb/1.0.0',
            repo_root / 'data/qtdb',
            repo_root / 'PQRST_mapping/data/qtdb',
        )
    if ludb_dir is None:
        ludb_dir = first_existing(
            repo_root / 'data/ludb',
            repo_root / 'PQRST_mapping/data/ludb',
            repo_root / 'physionet.org/files/ludb/1.0.1/data',
            repo_root / 'PQRST_mapping/physionet.org/files/ludb/1.0.1/data',
        )
    return Path(qtdb_dir), Path(ludb_dir)


def generate_labels(annotation, length, sample_scale=1.0):
    labels = np.zeros(length, dtype=np.int64)
    start = None
    wave_kind = None
    for sample, symbol in zip(annotation.sample, annotation.symbol):
        sample = int(round(sample * sample_scale))
        if symbol == '(':
            start = sample
            wave_kind = None
        elif symbol == 'p':
            wave_kind = 1
        elif symbol == 'N':
            wave_kind = 2
        elif symbol == 't':
            wave_kind = 3
        elif symbol == ')' and start is not None and wave_kind is not None:
            labels[max(0, start): min(length, sample + 1)] = wave_kind
            start = None
            wave_kind = None
    labels[labels == 2] = 0
    labels[labels == 3] = 2
    return labels


def pan_tompkins_r_peaks(ecg, fs):
    nyquist = fs / 2.0
    sos = butter(3, [5.0 / nyquist, 18.0 / nyquist], btype='bandpass', output='sos')
    bandpassed = sosfiltfilt(sos, ecg)
    derivative = np.convolve(bandpassed, np.array([-1, -2, 0, 2, 1]) * fs / 8.0, mode='same')
    width = max(1, round(0.150 * fs))
    integrated = np.convolve(derivative ** 2, np.ones(width) / width, mode='same')
    candidates, _ = find_peaks(integrated, distance=max(1, round(0.20 * fs)))
    boot = candidates[candidates < min(len(ecg), round(2 * fs))]
    spki = np.percentile(integrated[boot], 90) if len(boot) else 0.0
    npki = np.percentile(integrated[boot], 25) if len(boot) else 0.0
    accepted = []
    for peak in candidates:
        threshold = npki + 0.25 * (spki - npki)
        if integrated[peak] >= threshold:
            accepted.append(peak)
            spki = 0.125 * integrated[peak] + 0.875 * spki
        else:
            npki = 0.125 * integrated[peak] + 0.875 * npki
    search = round(0.10 * fs)
    refined = []
    for peak in accepted:
        left = max(0, peak - search)
        right = min(len(ecg), peak + search + 1)
        refined.append(left + int(np.argmax(ecg[left:right])))
    return np.unique(np.asarray(refined, dtype=int))


def create_windows(ecg, labels, r_peaks, post):
    xs, ys = [], []
    for r in r_peaks:
        left, right = r - PRE, r + post
        if left >= 0 and right <= len(ecg):
            xs.append(ecg[left:right])
            ys.append(labels[left:right])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.int64)


def qtdb_record(record_name, post, qtdb_dir):
    path = str(qtdb_dir / record_name)
    record = wfdb.rdrecord(path)
    ecg = record.p_signal[:, 0].astype(np.float32)
    labels = generate_labels(wfdb.rdann(path, 'pu0'), len(ecg))
    return create_windows(ecg, labels, pan_tompkins_r_peaks(ecg, float(record.fs)), post)


def ludb_record(record_name, post, ludb_dir):
    path = str(ludb_dir / record_name)
    record = wfdb.rdrecord(path)
    lead = record.sig_name.index('ii')
    ecg = resample_poly(record.p_signal[:, lead].astype(np.float32), up=1, down=2)
    labels = generate_labels(wfdb.rdann(path, 'ii'), len(ecg), sample_scale=0.5)
    size = min(len(ecg), len(labels))
    ecg, labels = ecg[:size], labels[:size]
    return create_windows(ecg, labels, pan_tompkins_r_peaks(ecg, 250.0), post)


def build_partition(record_names, builder, post, data_dir):
    xs, ys, ids = [], [], []
    skipped = []
    for record_name in record_names:
        try:
            x, y = builder(record_name, post, data_dir)
            if len(x):
                xs.append(x)
                ys.append(y)
                ids.extend([record_name] * len(x))
        except Exception as exc:  # pragma: no cover - data-specific guard
            skipped.append({'record': record_name, 'error': str(exc)})
    if not xs:
        raise RuntimeError('No usable windows generated for the selected partition.')
    return np.concatenate(xs), np.concatenate(ys), np.asarray(ids), skipped


class CNNFeatureExtractor(nn.Module):
    def __init__(self, channels=1):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(channels, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
        )

    def forward(self, x):
        return self.features(x)


class BiLSTMBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(64, 128, num_layers=1, batch_first=True, bidirectional=True)

    def forward(self, x):
        return self.lstm(x)[0]


class RPeakGuidedML2(nn.Module):
    def __init__(self, num_classes=3):
        super().__init__()
        self.cnn = CNNFeatureExtractor()
        self.bilstm = BiLSTMBlock()
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.cnn(x).permute(0, 2, 1)
        return self.classifier(self.dropout(self.bilstm(x)))


class RPeakTimeML2(nn.Module):
    def __init__(self, num_classes=3):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(2, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
        )
        self.bilstm = nn.LSTM(64, 128, num_layers=1, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.cnn(x).permute(0, 2, 1)
        return self.classifier(self.dropout(self.bilstm(x)[0]))


def time_channel(signals, post):
    time = (np.arange(signals.shape[1], dtype=np.float32) - PRE) / float(post)
    stacked = np.stack([signals.astype(np.float32), np.broadcast_to(time, signals.shape)], axis=1)
    return stacked.copy()


def make_loader(features, labels, seed, shuffle):
    generator = torch.Generator()
    generator.manual_seed(seed)
    dataset = TensorDataset(torch.as_tensor(features, dtype=torch.float32), torch.as_tensor(labels, dtype=torch.long))
    return DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=shuffle, generator=generator, num_workers=0)


def run_training_epoch(model, loader, criterion, optimizer=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    batches = 0
    with torch.set_grad_enabled(training):
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            logits = model(features).permute(0, 2, 1)
            loss = criterion(logits, labels)
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
            total_loss += float(loss.item())
            batches += 1
    return total_loss / max(1, batches)


def predict(model, features):
    model.eval()
    preds = []
    with torch.inference_mode():
        for start in range(0, len(features), BATCH_SIZE):
            batch = torch.as_tensor(features[start:start + BATCH_SIZE], dtype=torch.float32, device=device)
            preds.append(model(batch).argmax(2).cpu().numpy())
    return np.concatenate(preds)


def train_fixed_model(model, X_train, y_train, X_val, y_val, criterion, seed, model_name, artifact_dir):
    set_global_seed(seed)
    train_loader = make_loader(X_train, y_train, seed, shuffle=True)
    val_loader = make_loader(X_val, y_val, seed, shuffle=False)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    best_loss = float('inf')
    best_state = None
    for epoch in range(1, NUM_EPOCHS + 1):
        train_loss = run_training_epoch(model, train_loader, criterion, optimizer)
        val_loss = run_training_epoch(model, val_loader, criterion)
        if val_loss < best_loss:
            best_loss = val_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        print(f'{model_name} seed={seed} epoch={epoch:02d} train={train_loss:.4f} val={val_loss:.4f}')
    model.load_state_dict(best_state)
    torch.save(model.state_dict(), artifact_dir / f'{model_name}_seed{seed}.pth')
    return model


def main():
    args = parse_args()
    qtdb_dir, ludb_dir = detect_data_dirs(args.qtdb_dir, args.ludb_dir)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(exist_ok=True, parents=True)

    global device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('CUDA available:', torch.cuda.is_available())
    print('Device:', device)
    print('QTDB_DIR:', qtdb_dir)
    print('LUDB_DIR:', ludb_dir)

    if not qtdb_dir.exists() or not ludb_dir.exists():
        raise FileNotFoundError(
            'Could not find the QTDB/LUDB data directories. Upload the dataset into Drive or pass '
            '--qtdb-dir and --ludb-dir explicitly.'
        )

    qtdb_headers = {p.stem for p in qtdb_dir.glob('*.hea')}
    qtdb_dat = {p.stem for p in qtdb_dir.glob('*.dat')}
    qtdb_records = sorted(qtdb_headers & qtdb_dat)
    if len(qtdb_records) != 105:
        raise ValueError(f'Expected 105 QTDB records, found {len(qtdb_records)} in {qtdb_dir}')

    qtdb_train_records, qtdb_val_records = train_test_split(qtdb_records, test_size=0.20, random_state=7, shuffle=True)
    qtdb_train_records = sorted(qtdb_train_records)
    qtdb_val_records = sorted(qtdb_val_records)

    ludb_headers = {p.stem for p in ludb_dir.glob('*.hea')}
    ludb_dat = {p.stem for p in ludb_dir.glob('*.dat')}
    ludb_records = sorted(ludb_headers & ludb_dat)
    if len(ludb_records) != 200:
        raise ValueError(f'Expected 200 LUDB records, found {len(ludb_records)} in {ludb_dir}')

    r6_adapt_records, r6_test_records = train_test_split(ludb_records, test_size=1 - 0.10, random_state=17, shuffle=True)
    r6_adapt_records = sorted(r6_adapt_records)
    r6_test_records = sorted(r6_test_records)

    print('QTDB train/val:', len(qtdb_train_records), len(qtdb_val_records))
    print('LUDB adaptation/test:', len(r6_adapt_records), len(r6_test_records))

    X_qt_train, Y_qt_train, _, _ = build_partition(qtdb_train_records, qtdb_record, POST, qtdb_dir)
    X_qt_val, Y_qt_val, _, _ = build_partition(qtdb_val_records, qtdb_record, POST, qtdb_dir)
    train_mean = float(X_qt_train.mean())
    train_std = float(X_qt_train.std())
    if train_std == 0:
        raise ValueError('QTDB training std is zero; cannot normalize.')
    X_qt_train = (X_qt_train - train_mean) / train_std
    X_qt_val = (X_qt_val - train_mean) / train_std

    X_lu_adapt_240, Y_lu_adapt_240, _, _ = build_partition(r6_adapt_records, ludb_record, POST, ludb_dir)
    X_lu_test_240, Y_lu_test_240, _, _ = build_partition(r6_test_records, ludb_record, POST, ludb_dir)
    X_lu_adapt_320, Y_lu_adapt_320, _, _ = build_partition(r6_adapt_records, ludb_record, R5_POST, ludb_dir)
    X_lu_test_320, Y_lu_test_320, _, _ = build_partition(r6_test_records, ludb_record, R5_POST, ludb_dir)

    X_qt_train_320, Y_qt_train_320, _, _ = build_partition(qtdb_train_records, qtdb_record, R5_POST, qtdb_dir)
    X_qt_val_320, Y_qt_val_320, _, _ = build_partition(qtdb_val_records, qtdb_record, R5_POST, qtdb_dir)
    r5_train_mean = float(X_qt_train_320.mean())
    r5_train_std = float(X_qt_train_320.std())
    X_qt_train_320 = (X_qt_train_320 - r5_train_mean) / r5_train_std
    X_qt_val_320 = (X_qt_val_320 - r5_train_mean) / r5_train_std
    X_lu_adapt_240 = (X_lu_adapt_240 - train_mean) / train_std
    X_lu_test_240 = (X_lu_test_240 - train_mean) / train_std
    X_lu_adapt_320 = (X_lu_adapt_320 - r5_train_mean) / r5_train_std
    X_lu_test_320 = (X_lu_test_320 - r5_train_mean) / r5_train_std

    artifact_dir.mkdir(exist_ok=True, parents=True)
    (artifact_dir / 'split_manifest.json').write_text(json.dumps({
        'qtdb_train_records': qtdb_train_records,
        'qtdb_validation_records': qtdb_val_records,
        'ludb_adaptation_records': r6_adapt_records,
        'ludb_test_records': r6_test_records,
        'qtdb_train_mean': train_mean,
        'qtdb_train_std': train_std,
        'qtdb_train_mean_320': r5_train_mean,
        'qtdb_train_std_320': r5_train_std,
    }, indent=2))

    seed_list = [args.seed] if args.single_seed else TRAINING_SEEDS
    for seed in seed_list:
        set_global_seed(seed)
        print(f'\n=== Running seed {seed} ===')
        run_name = f'{args.run_id}_seed{seed}'
        model = RPeakGuidedML2().to(device)
        train_fixed_model(model, X_qt_train[:, None], Y_qt_train, X_qt_val[:, None], Y_qt_val, nn.CrossEntropyLoss(), seed, 'R3_' + run_name, artifact_dir)

        val_pred = predict(model, X_qt_val[:, None])
        val_f1 = f1_score(Y_qt_val.ravel(), val_pred.ravel(), labels=[0, 1, 2], average='macro', zero_division=0)
        print('QTDB validation macro F1:', val_f1)

    print('\nColab L4 training setup complete.')
    print('No full training sweep was executed in this pass; run the desired seed(s) or use the notebook cells directly.')


if __name__ == '__main__':
    main()
