import time
from send_to_esp import send_phase

def execute_phases(phases):
    ordered = sorted(phases.items(), key=lambda x: x[1])

    for phase, t_event in ordered:
        # Recompute against "now" each iteration. Using a single snapshot
        # taken before the loop started meant each phase's wait re-included
        # time already spent sleeping for earlier phases, so timing drifted
        # later and later as a beat progressed.
        wait_time = t_event - time.time()
        if wait_time > 0:
            time.sleep(wait_time)

        if phase == 'P':
            send_phase('P')
        elif phase == 'QRS':
            send_phase('Q')
        elif phase == 'T_start':
            send_phase('T')
