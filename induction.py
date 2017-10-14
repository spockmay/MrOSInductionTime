import random
import datetime

from plm import Plm
from plmseries import PlmSeries

from patient import Patient
from helper import get_sleep_times, \
    create_even_chunks, \
    get_NSVT_times, \
    chunk_times, \
    get_control_windows,\
    get_control_periods,\
    get_study_start_time

HOME_DIR = 'F:\\MrOS Case Cross\\may-hrv'
RESULTS_DIR = 'F:\\MrOS Case Cross\\results'
XML_DIRECTORY = HOME_DIR + '\\edfs'
MSACCESS_DIRECTORY = HOME_DIR + '\\hrv'
SOMTE_DIRECTORY = HOME_DIR + '\\shhs1-csv'

DT_CONTROL_WINDOW = 10*60 # 10 min - width of control window
DT_INTERVAL       = 10*60 # 10 min - intervals from NSVT onset
DT_CONTROL_PERIOD = 45    # seconds

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
i  =0
for pt in patients:
    print pt.id

    # generate approx 30 minute partitions from [sleep onset, lights on]
    dt_chunk = create_even_chunks(pt.sleep_onset,pt.lights_on)

    # for each NSVT event
    for nsvt in pt.nsvt_times:
        ctrl_periods = []

        # ignore any NVST during wake
        if not pt.is_sleep_epoch(nsvt):
            continue

        i += 1
        print pt.walltime_to_epoch(nsvt)

        # find chunk start and chunk end for this NSVT event
        chunk = chunk_times(nsvt, pt.sleep_onset, pt.lights_on, dt_chunk)
        if chunk:
            # build a control window for each  +/-10 minute interval from NSVT offset
            ctrl_windows = get_control_windows(nsvt, chunk, DT_CONTROL_WINDOW, DT_INTERVAL)

            # divide each window into control periods
            for window in ctrl_windows:
                poss_ctl_periods = get_control_periods(window, DT_CONTROL_PERIOD)
                if poss_ctl_periods:
                    # remove any possible ctl periods with wake
                    poss_ctl_periods[:] = [x for x in poss_ctl_periods if pt.is_sleep_epoch(x)]

                    if poss_ctl_periods:
                        # select one of the possible control periods
                        selected = random.sample(poss_ctl_periods, 1)
                        ctrl_periods.append(selected)

            #print pt.id, pt.walltime_to_epoch(nsvt), len(ctrl_periods)

print i