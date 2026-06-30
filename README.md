# PQRST_mapping

ML Model architecture for PQRST wave detection and time-seriesification

## Pipeline approach
- Single file handler `pipeline/master.py` takes funcs from rest of the files to create an executable pipeline.
- DSP -> Model1 -> Model2 -> Comms to board
- `csvhandler.py` handles intermediate file creation for model1, model2 and serial inputs.
- `model1.py` and `model2.py` handle the pkl unpacking and data inouts.


