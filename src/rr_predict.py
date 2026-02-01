def compute_rr(peaks):
    R_times = [p[0] for p in peaks]
    RR = []

    for i in range(1, len(R_times)):
        RR.append(R_times[i] - R_times[i-1])

    return R_times, RR


def predict_next(R_times, RR):
    if len(RR) == 0:
        return None

    t_curr = R_times[-1]
    RR_last = RR[-1]
    t_next = t_curr + RR_last

    return t_next, RR_last
