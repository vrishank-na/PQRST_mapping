import pickle
import numpy as np
import pandas as pd

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


