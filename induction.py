import random

from plm import Plm
from plmseries import PlmSeries

from patient import Patient
from helper import get_sleep_times, \
    create_even_chunks, \
    get_NSVT_times, \
    chunk_times, \
    get_control_windows,\
    get_study_start_time

ROOT_DIR = 'F:\\MrOS PLM case-cross\\other'
DATA_DIR = ROOT_DIR + '\\may-hrv'
RESULTS_DIR = ROOT_DIR + '\\results'
XML_DIRECTORY = DATA_DIR + '\\edfs'
MSACCESS_DIRECTORY = DATA_DIR + '\\hrv'
SOMTE_DIRECTORY = DATA_DIR + '\\shhs1-csv'

DT_CONTROL_WINDOW  = 2.5*60 # 10 min - width of control window
DT_INTERVAL        = 5*60   # 10 min - intervals from NSVT onset
DT_CONTROL_PERIOD  = 30     # seconds
DT_HAZARD_OFFSET   = 0      # seconds between the end of the hazard period and the NSVT event

N_CTRL_PERIODS     = 3      # number of control periods to downselect to.  Set to None for no downselect
MIN_N_CTRL_PERIODS = 0      # minimum number of control periods to consider for inclusion

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

# Do the actual work here...
# for each patient
i = 0
n_nsvt = 0
for pt in patients:
#    print pt.id

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

        # silly output code for v&v
        print pt.id, pt.walltime_to_epoch(nsvt), len(ctrl_periods), len(ctrl_windows)
        if len(ctrl_periods) > 2:
            i += 1
        n_nsvt += 1

print i
print n_nsvt