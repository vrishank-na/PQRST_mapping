# creation and deletion of appropriate csv files at critical junctures of the pipeline
# should be called before and after each stage of the pipeline is run
# 

def create_csv():
    with open("intermediate_results.csv", "w") as f:
        f.write("timestamp,ecg_value\n")

def read_ecg_csv(filename):
    with open(filename, "r") as f:
        lines = f.readlines()
        ecg_data = []
        for line in lines[1:]:  # skip header
            timestamp, ecg_value = line.strip().split(",")
            ecg_data.append(float(ecg_value))
    return ecg_data

def delete_csv():
    import os
    if os.path.exists("intermediate_results.csv"):
        os.remove("intermediate_results.csv")
    else:
        print("The file does not exist")

