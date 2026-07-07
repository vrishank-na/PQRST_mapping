import pickle
import model1_placeholder

def extract_model(model_path):
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    return model

def read_csv(filename):
    return 1

def write_csv(filename, data):
    return 1

def compute():
    return 1


def process(ecg_data, fs=100.0):
    """Temporary entrypoint until the trained model 1 artefact remover exists."""
    return model1_placeholder.process(ecg_data, fs=fs)
