import random

from patient import Patient
from helper import get_sleep_times, \
    create_even_chunks, \
    get_NSVT_times, \
    chunk_times, \
    get_control_windows,\
    get_study_start_time,\
    any_during,\
    count_during

ROOT_DIR = 'F:\\MrOS PLM case-cross\\other'
DATA_DIR = ROOT_DIR + '\\may-hrv'
RESULTS_DIR = ROOT_DIR + '\\results'
XML_DIRECTORY = DATA_DIR + '\\edfs'
MSACCESS_DIRECTORY = DATA_DIR + '\\hrv'
SOMTE_DIRECTORY = DATA_DIR + '\\shhs1-csv'

OUTPUT_FILE = '\\results.csv'

DT_CONTROL_WINDOW  = 2.5*60 # seconds - width of control window
DT_INTERVAL        = 5*60   # seconds - intervals from NSVT onset
DT_CONTROL_PERIOD  = 30     # seconds - width of the control periods
DT_HAZARD_OFFSET   = 0      # seconds - difference between the end of the hazard period and the NSVT event

N_CTRL_PERIODS     = 3      # number of control periods to downselect to.  Set to None for no downselect
MIN_N_CTRL_PERIODS = 1      # minimum number of control periods to consider for inclusion

random.seed(123456)

# setup stuff
sleep_times = get_sleep_times(RESULTS_DIR + '\\Sleep_period_lights_on_off.csv')
nsvt_times = get_NSVT_times(RESULTS_DIR + '\\NSVTtimes_removeAF_clean.csv')
study_times = get_study_start_time(RESULTS_DIR + '\\NSVTtimes_removeAF_clean.csv')
pt_ids = nsvt_times.keys()  # we only need to look at patients with NSVT events

# create an array of Patients
patients = []
for pt in pt_ids:
    patients.append(Patient(pt, sleep_times[pt], study_times[pt], nsvt_times[pt], XML_DIRECTORY))

# create output file and write header
fout = open(RESULTS_DIR + OUTPUT_FILE, 'w')
fout.writelines("ID,patient_event_number,case_control,period_start_time,sleep_stage,PLMS_event,PLMS_type1,PLMS_type2,PLMS_type3,PLMS_type4,PLMS_type5,resp_event,resp_type1,resp_type2,arousal,PLMS_assos,resp_assos,PLMSresp,RESPplms,NSVT_start,NSVT_duration,NSVT_sstage,segment_duration,segment_start,segment_end\n")
out_format = "{},"*24 + "{}\n"

# Do the actual work here...
# for each patient
for pt in patients:
    print pt.id
    n_nsvt = 0

    # generate approx 30 minute partitions from [sleep onset, lights on]
    dt_chunk = create_even_chunks(pt.sleep_onset,pt.lights_on)

    # for each NSVT event
    for nsvt in pt.nsvt_times:
        ctrl_periods = []

        # ignore any NVST during wake
        if not pt.is_sleep_time(nsvt):
            continue

        # find chunk start and chunk end for this NSVT event
        chunk = chunk_times(nsvt, pt.sleep_onset, pt.lights_on, dt_chunk)

        # build a control window for each  +/-10 minute interval from NSVT offset
        ctrl_windows = get_control_windows(nsvt, chunk, DT_CONTROL_WINDOW, DT_INTERVAL)

        # divide each window into control periods
        for window in ctrl_windows:
            poss_ctl_periods = pt.get_control_periods(window, DT_CONTROL_PERIOD)

            if poss_ctl_periods:
                # select one of the possible control periods
                selected = random.sample(poss_ctl_periods, 1)
                ctrl_periods.append(selected)

        # skip this NSVT event if there are not sufficient number of control periods
        if len(ctrl_periods) < MIN_N_CTRL_PERIODS:
            continue

        # downselect number of control periods
        if N_CTRL_PERIODS is not None:
            if len(ctrl_periods) >= N_CTRL_PERIODS:
                ctrl_periods = random.sample(ctrl_periods, N_CTRL_PERIODS)
            else:
                continue

        # determine the hazard period for the NSVT
        hazard_period = pt.get_hazard_period(nsvt, DT_CONTROL_PERIOD, DT_HAZARD_OFFSET)

        # update counter
        n_nsvt += 1

        # prepare output
        outline = [out_format.format(pt.id,      # pt ID
                                         n_nsvt,     # NSVT number for this patient
                                         1,          # this is for the HP
                                         hazard_period[0].strftime('%H:%M:%S'),     # start of HP
                                         pt.get_sleep_stage(hazard_period[0]),      # sleep stage at start of HP
                                         1 if any_during(pt.plm_events, hazard_period) else 0,  # PLMS_event
                                         "?",
                                         "?",
                                         "?",
                                         "?",
                                         "?",
                                         1 if any_during(pt.resp_events, hazard_period) else 0,
                                         "?",       # resp_type1
                                         "?",       # resp_type2
                                         count_during(pt.arousal_events, hazard_period),    # number of arousals during HP
                                         "?",       # number of arousals associated to PLM during HP
                                         "?",       # resp_assos - number of resp associated arousals
                                         count_during(pt.plm_resp_events, hazard_period),    # number of resp-associated PLM
                                         "?",
                                         nsvt.strftime('%H:%M:%S'),
                                         "?",      # duration of NSVT, sec
                                         pt.get_sleep_stage(nsvt),
                                         (chunk[1] - chunk[0]).seconds / 60.0,
                                         chunk[0].strftime('%H:%M:%S'),
                                         chunk[1].strftime('%H:%M:%S')
                                         )]

        for ctrl in ctrl_periods:
            ctrl = ctrl[0]
            outline.append(out_format.format(pt.id,  # pt ID
                                             n_nsvt,  # NSVT number for this patient
                                             0,  # this is for the control periods
                                             ctrl[0].strftime('%H:%M:%S'),  # start of CP
                                             pt.get_sleep_stage(ctrl[0]),  # sleep stage at start of HP
                                             1 if any_during(pt.plm_events, ctrl) else 0,
                                             "?",
                                             "?",
                                             "?",
                                             "?",
                                             "?",
                                             1 if any_during(pt.resp_events, ctrl) else 0,
                                             "?",  # resp_type1
                                             "?",  # resp_type2
                                             count_during(pt.arousal_events, ctrl),       # number of arousals during CP
                                             "?",  # number of arousals associated with PLM during CP
                                             "?",  # resp_assos - number of resp associated arousals
                                             count_during(pt.plm_resp_events, ctrl),     # number of resp-associated PLM
                                             "?",
                                             nsvt.strftime('%H:%M:%S'),
                                             "?",  # duration of NSVT, sec
                                             pt.get_sleep_stage(nsvt),
                                             (chunk[1] - chunk[0]).seconds / 60.0,
                                             chunk[0].strftime('%H:%M:%S'),
                                             chunk[1].strftime('%H:%M:%S')
                                             ))
        fout.writelines(outline)

fout.close()