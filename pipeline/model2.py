try:
    from . import model2_placeholder
except ImportError:  # pragma: no cover - supports running as a script
    import model2_placeholder


def process(model1_results, fs=None):
    """Temporary entrypoint until the trained model 2 recognizer exists."""
    return model2_placeholder.process(model1_results, fs=fs)
