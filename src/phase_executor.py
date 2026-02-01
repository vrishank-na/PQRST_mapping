import time
from send_to_esp import send_phase

def execute_phases(phases):
    start = time.time()
    ordered = sorted(phases.items(), key=lambda x: x[1])

    for phase, t_event in ordered:
        wait_time = t_event - start
        if wait_time > 0:
            time.sleep(wait_time)

        if phase == 'P':
            send_phase('P')
        elif phase == 'QRS':
            send_phase('Q')
        elif phase == 'T_start':
            send_phase('T')
