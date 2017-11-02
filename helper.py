import datetime
import os
import re


def clock_to_datetime(clock_str):
    [h, m, s] = clock_str.split(':')
    return datetime.datetime(2000, 1, 1, int(h), int(m), int(s))

def make_after(before, after):
    if after < before:
        return after + datetime.timedelta(days=1)
    else:
        return after

def get_study_start_time(file):
    """For some reason the study start times are stored in NSVT times file as the first element"""
    result = {}
    with open(file) as fin:
        for line in fin:
            csv = line.split(',')
            pt_id = csv[0].upper()

            result[pt_id] = clock_to_datetime(csv[1])
    return result

def get_sleep_times(file):
    result = {}

    with open(file) as fin:
        for line in fin:
            csv = line.split(',')
            if csv[0] == 'PPTID':
                continue

            light_off = clock_to_datetime(csv[1])
            light_on = make_after(light_off,clock_to_datetime(csv[5]))
            sleep_latency = float(csv[2])
            sleep_onset = light_off + datetime.timedelta(minutes=sleep_latency)

            a = {'sleep_onset': sleep_onset,
                 'lights_on': light_on}
            result[csv[0].upper()] = a
    return result

def create_even_chunks(ts, tf):
    dt = float((tf - ts).seconds)        # how many seconds is the sleep period
    ideal_chunk = 30 * 60           # ideal chunk is 30 min long
    n_chunks = int(dt / ideal_chunk)
    dt_chunk = dt / n_chunks
    return datetime.timedelta(seconds=dt_chunk)

def getFileNames(searchdir, fileType):
    filelist = []
    for file in os.listdir(searchdir):
        if file.endswith(fileType.upper()) or file.endswith(fileType.lower()):
            filelist.append(file)
    return filelist

def get_patient_ids(searchdir):
    pt_id = []
    files = getFileNames(searchdir, '.edf')
    for file in files:
        pt_id.append(file.split('.')[0].upper())
    return pt_id

def get_NSVT_times(file):
    result = {}
    with open(file) as fin:
        for line in fin:
            times = []
            csv = line.split(',')
            pt_id = csv[0].upper()
            for i in range(1, len(csv)):
                times.append(clock_to_datetime(csv[i]))
                if i > 1:
                    times[i-1] = make_after(times[i-2], times[i-1])
            times.pop(0)    # for some reason the first "time" is actually the sleep study start time

            # remove NSVT events that are too close to each other temporaly
            new_times = []
            new_times.append(times[0])
            for i in range(1, len(times)):
                dt = times[i] - times[i-1]
                if dt.seconds >= 5*60:
                    new_times.append(times[i])

            result[pt_id] = new_times

    return result

def chunk_times(time, ts, tf, dt_chunk):
    chunk = (ts, ts + dt_chunk)
    if time < ts or time > tf:
        return None
    while chunk[1] <= tf+datetime.timedelta(seconds=1):
        if time < chunk[1]:
            return chunk
        chunk = (chunk[0]+dt_chunk, chunk[1]+dt_chunk)

def make_fit_within(small, big):
    result = small
    if small[0] < big[0]:
        result = (big[0], result[1])
    if small[1] > big[1]:
        result = (result[0], big[1])
    return result

def get_control_windows(nsvt_onset, chunk_times, window_width, interval):
    windows = []
    half_width = datetime.timedelta(seconds=float(window_width / 2))
    interval = datetime.timedelta(seconds=interval)

    # work backwards in time from nsvt_onset
    t = nsvt_onset - interval
    while t >= chunk_times[0]-half_width:
        window = make_fit_within((t-half_width, t+half_width), chunk_times)
        windows.append(window)
        t = t - interval

    # work forwards in time from nsvt_onset
    t = nsvt_onset + interval
    while t <= chunk_times[1]+half_width:
        window = make_fit_within((t-half_width, t+half_width), chunk_times)
        windows.append(window)
        t = t + interval

    return windows

def get_sleep_stages(xml_path, fname):
    re_ss = re.compile(ur'<SleepStage>(\d+?)<\/SleepStage>')
    sleep_list = []
    with open(xml_path + '\\' + fname, 'r') as f:
        data = f.read()
        for ss in re.finditer(re_ss, data):
            sleep_list.append(int(ss.group(1)))

    return sleep_list


