# PQRST Mapping

ML Model architecture for PQRST wave detection and time-seriesification

## Pipeline approach
- Single file handler `master.py` takes funcs from rest of the files to create an executable pipeline.
- DSP -> Model1 -> Model2 -> Comms to board -> Then to LED circuit
- `dsp.py` handles initial DSP filtering and noise subtraction and generation.
- `csvhandler.py` handles intermediate file creation for model1, model2 and serial inputs.
- `model1.py` and `model2.py` handle the pkl unpacking and data inouts.
- `serialcomms.py` handles end communication with microcontroller.


## Functions
#### `dsp.py`
- Define `butter_highpass`, `butter_lowpass` and `bandpass_ecg` for filtering.
- Subtract out the noise using `subtract_noise` method, taking initial unaltered ECG value and post-filter ECG value. They are subtracted array-wise by appropriate timestamp.
- Obtained noise array is added to intermediate CSV that is handled by `csv_handler.py`
---
#### `csv_handler.py`
- Create intermediate CSV for data update into pipeline.
- Be aware of all processes that are going on. Calls should be accurately done, without any loss of data.
- Must be able to capture all of the outward streams of data from the pickles/PyTorch weight files (`.pth`/`.pkl` files).
- `create_csv` and `delete_csv` can be defined. 
- Steps can be defined in the file to also delete the CSV iff the filename is `intermediate` or contains such a substring, as final CSV should not be deleted.
---
#### `model1.py` and `model2.py`
- Extract model files and pass data from generated intermediate CSV.
- `extract_model`, `read_csv`, `write_csv`, `compute` can be implemented here.
- As the format for both models are different, both files will be different. However `extract_model`, `read_csv` will still be the same.
---
#### `serialcomms.py` 
- Pass data from last generated CSV to microcontroller.
- `send_datastream`, `connect_usb_interface` can be implemented here.
---
#### `master.py`
- Complete definition of the pipeline, will call all the functions and sequence them.
- One large `main` function will suffice here for all the function calls.
---
> [!NOTE]
> Each file will have its respective error handling methods, these functions can be assumed to be naturally included along with all the other functions as mentioned above.
---

## Builders:
- Vrishank N Amembal (owner of this repo)
- Vishwambhara R Hebbalalu

