def schedule_phases(t_next, RR):
    phases = {}

    phases['P'] = t_next - 0.15 * RR
    phases['QRS'] = t_next
    phases['T_start'] = t_next + 0.30 * RR
    phases['T_end'] = t_next + 0.60 * RR

    return phases
