import datetime
import os
import re

from plm import Plm

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

def plm_from_xml(xml):
    # <ScoredEvent><Name>PLM (Right)</Name><Start>818.4</Start><Duration>1.7</Duration><Input>Leg R</Input></ScoredEvent>
    re_start = re.compile(ur'<Start>(\d*\.*\d*)<\/Start>')
    re_dur = re.compile(ur'<Duration>(\d*\.*\d*)<\/Duration>')
    re_side = re.compile(ur'PLM \((\w+?)\)')

    tstart = float(re.search(re_start,xml).group(1))
    dur = float(re.search(re_dur,xml).group(1))
    tend = tstart + dur
    side = re.search(re_side,xml).group(1)

    event = Plm(tstart, tend, side)
    return event

def simple_event_from_xml(xml):
    # <ScoredEvent><Name>Arousal (ASDA)</Name><Start>5444.5</Start><Duration>4.9</Duration><Input>C3</Input></ScoredEvent>
    re_start = re.compile(ur'<Start>(\d*\.*\d*)<\/Start>')
    re_dur = re.compile(ur'<Duration>(\d*\.*\d*)<\/Duration>')

    tstart = float(re.search(re_start,xml).group(1))
    dur = float(re.search(re_dur,xml).group(1))
    tend = tstart + dur

    event = (tstart, tend)
    return event

def is_associated(event1, event2, constraint=(None,0.5), fixedOrder=False):
    # this method is looking to provide a general test of whether 2 events are associated
    # if fixedOrder is False, then the order in which the events are provided doesn't matter
    # and they will be rearranged so that the earliest starting event is e1.
    # If fixedOrder is True, the order is unchanged.
    #
    # the constraint is a tuple of seconds that generate the conditions for association.
    # condition 1: e2[start] - e1[end] > constraint[0]
    # condition 2: e2[start] - e1[end] < constraint[1]
    # If any element of constraint is None, then that condition will evaluate to True
    # the events are associated iff both conditions are True
    #
    # events can be associated to eachother iff the condition below is true:
    #  the start of later event is strictly < 0.5 seconds of the end of the first event
    if fixedOrder:
        e1 = event1
        e2 = event2
        if e1[0] > e2[0]:
            return False
    else:
        if event1[0] < event2[0]:
            e1 = event1
            e2 = event2
        else:
            e1 = event2
            e2 = event1

    # condition 1
    if constraint[0] is None:
        c1 = True
    else:
        if e2[0] - e1[1] > datetime.timedelta(seconds=constraint[0]):
            c1 = True
        else:
            return False

    # condition 2
    if constraint[1] is None:
        return True # this is basically return c1 and True which is return c1 which has to be True since we are here
    else:
        if e2[0] - e1[1] < datetime.timedelta(seconds=constraint[1]):
            return True
        else:
            return False

