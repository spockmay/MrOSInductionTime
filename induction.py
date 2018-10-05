import random

from patient import Patient
from helper import get_sleep_times, \
    create_even_chunks, \
    get_NSVT_times, \
    chunk_times, \
    get_control_windows,\
    get_study_start_time,\
    any_during,\
    get_during,\
    count_during,\
    plms_type,\
    resp_type
from datetime import datetime

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
nsvt_times = get_NSVT_times(RESULTS_DIR + '\\NSVTtimes_allPLMI_clean_noAF.csv')
study_times = get_study_start_time(RESULTS_DIR + '\\NSVTtimes_allPLMI_clean_noAF.csv')
pt_ids = nsvt_times.keys()  # we only need to look at patients with NSVT events

# create an array of Patients
patients = []

#pt_ids = ['MN2361']

# < OPTIONAL >
nsvt_clock = []  # list of NSVT event clock time
nsvt_sleep = []  # list of NSVT event time since sleep onset

pts_events = []
pts_sleepevents = []
# < /OPTIONAL >

for pt in pt_ids:
    patients.append(Patient(pt, sleep_times[pt], study_times[pt], nsvt_times[pt], XML_DIRECTORY))

# create output file and write header
fout = open(RESULTS_DIR + OUTPUT_FILE, 'w')
fout.writelines("ID,patient_event_number,case_control,period_start_time,sleep_stage,PLMS_event,PLMS,PLMA,LMrespWASM,LMrespWink1,resp_event,apnea,hypopnea,RESPlmWASM,RESPlmWink1,minsat,arousal,AResp,APLMS,AAPLMS,ABPLMS,NSVT_start,NSVT_duration,NSVT_beats,NSVT_sstage,segment_duration,segment_start\n")
out_format = "{},"*26 + "{}\n"

# Do the actual work here...
# for each patient
stratum = 0
for pt in patients:
    print pt.id
    n_nsvt = 0

    # generate approx 30 minute partitions from [sleep onset, lights on]
    dt_chunk = create_even_chunks(pt.sleep_onset,pt.lights_on)

    # for each NSVT event
    for nsvt in pt.nsvt_times:
        ctrl_periods = []

        # < OPTIONAL >
        if pt.id not in pts_events:
            pts_events.append(pt.id)
        # < /OPTIONAL >

        # ignore any NVST during wake
        if not pt.is_sleep_time(nsvt):
            continue

        # < OPTIONAL >
        if pt.id not in pts_sleepevents:
            pts_sleepevents.append(pt.id)
        # < /OPTIONAL >

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

        # update counters
        n_nsvt += 1
        stratum += 1

        # < OPTIONAL >
        # generate data to drive a histogram of the timing of the NSVT events evaluated
        nsvt_clock.append((nsvt-datetime(2000,1,1)).total_seconds())  # list of NSVT event clock time
        nsvt_sleep.append((nsvt-pt.sleep_onset).total_seconds())  # list of NSVT event time since sleep onset
        # < /OPTIONAL >

        # prepare output
        plms = get_during(pt.plm_events, hazard_period)
        resp = get_during(pt.resp_events, hazard_period)
        outline = [out_format.format(pt.id,      # pt ID
                                     n_nsvt,     # NSVT number for this patient
                                     1,          # this is for the HP
                                     hazard_period[0].strftime('%H:%M:%S'),     # start of HP
                                     pt.get_sleep_stage(nsvt),      # sleep stage at start of NSVT
                                     count_during(pt.plm_events, hazard_period),  # number of PLMS events during period
                                     0,  # number of PLMS with no arousals
                                     0,  # number of PLMS associated with arousals
                                     0,  # number of respiratory-associated LIMB MOVEMENT/PLMS [-0.5, 0.5] sec
                                     0,  # number of respiratory-associated LIMB MOVEMENT/PLMS [-2.5, 2.5]sec
                                     count_during(pt.resp_events, hazard_period),  # number of resp. events
                                     0,  # number of apneas
                                     0,  # number of hypopneas
                                     0,  # number of PLMS-associated RESPIRATORY EVENT [-0.5, 0.5] sec
                                     0,  # number of PLMS-associated RESPIRATORY EVENT [-2.5, 2.5] sec
                                     pt.get_min_O2sat(hazard_period),  # min saturation
                                     count_during(pt.arousal_events, hazard_period),  # number of arousals during CP
                                     count_during(pt.arousal_resp, hazard_period), # resp_assos - number of resp associated arousals
                                     count_during(pt.arousal_plm, hazard_period),  # number of arousals associated to PLM during HP
                                     0,  # number of arousals starting after or at same time as associated PLMS
                                     0,  # number of arousals starting before assocaited PLMS
                                     nsvt.strftime('%H:%M:%S'),
                                     0,      # duration of NSVT, sec
                                     0,  # beats in arythmia
                                     pt.get_sleep_stage(nsvt),
                                     (chunk[1] - chunk[0]).seconds / 60.0,
                                     chunk[0].strftime('%H:%M:%S')
                                     )]

        for ctrl in ctrl_periods:
            ctrl = ctrl[0]
            plms = get_during(pt.plm_events, ctrl)
            resp = get_during(pt.resp_events, ctrl)
            outline.append(out_format.format(pt.id,  # pt ID
                                             n_nsvt,  # NSVT number for this patient
                                             0,  # this is for the control periods
                                             ctrl[0].strftime('%H:%M:%S'),  # start of CP
                                             pt.get_sleep_stage(ctrl[0]),  # sleep stage at start of CP
                                             count_during(pt.plm_events, ctrl),  # number of PLMS events in period
                                             0, # number of PLMS with no arousals
                                             0, # number of PLMS associated with arousals
                                             0, # number of respiratory-associated LIMB MOVEMENT/PLMS [-0.5, 0.5] sec
                                             0, # number of respiratory-associated LIMB MOVEMENT/PLMS [-2.5, 2.5]sec
                                             count_during(pt.resp_events, ctrl), # number of resp. events
                                             0, # number of apneas
                                             0, # number of hypopneas
                                             0, # number of PLMS-associated RESPIRATORY EVENT [-0.5, 0.5] sec
                                             0,  # number of PLMS-associated RESPIRATORY EVENT [-2.5, 2.5] sec
                                             pt.get_min_O2sat(ctrl),  # min saturation
                                             count_during(pt.arousal_events, ctrl),  # number of arousals during CP
                                             count_during(pt.arousal_resp, ctrl),   # resp_assos - number of resp associated arousals
                                             count_during(pt.arousal_plm, ctrl),  # number of arousals associated with PLM during CP
                                             0, # number of arousals starting after or at same time as associated PLMS
                                             0, # number of arousals starting before assocaited PLMS
                                             nsvt.strftime('%H:%M:%S'),
                                             0,  # duration of NSVT, sec
                                             0, # beats in arythmia
                                             pt.get_sleep_stage(nsvt), # sleep stage of epoch during nsvt
                                             (chunk[1] - chunk[0]).seconds / 60.0,
                                             chunk[0].strftime('%H:%M:%S')
                                             ))
        fout.writelines(outline)

fout.close()

# < OPTIONAL >
fout_a = open('nsvt_clock.csv', 'w')
for i in nsvt_clock:
    fout_a.write("%s,\n" % i)
fout_a.close()

fout_a = open('nsvt_sleep.csv', 'w')
for i in nsvt_sleep:
    fout_a.write("%s,\n" % i)
fout_a.close()

print '---------------------------'
print pts_events
print '---------------------------'
print pts_sleepevents

# < /OPTIONAL >