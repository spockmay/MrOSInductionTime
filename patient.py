import datetime
import re

from helper import get_sleep_stages, make_after, plm_from_xml, simple_event_from_xml, is_associated, plm_arousal_associated
from edf import EDF

class Patient:
    id = ""
    lights_on = None
    sleep_onset = None
    start_time = None
    nsvt_times = None

    plm_events = None       # list of tuples of datetimes
    arousal_events = None   # list of tuples of datetimes
    resp_events = None      # dictionary of list of tuples of datetimes

    plma_events = None      # list of PLMs associated with Arousals
    plm_resp_events = None  # list of PLMs associated with Resp. Events

    arousal_resp = None     # list of Arousals associated with Resp Events
    arousal_plm = None      # list of Arousals associated with PLM Events

    o2_sat = None           # oxygen saturation - from EDF file

    def __init__(self, id, study_times, start_time, nsvt_times, xml_path):
        self.id = id
        self.start_time = start_time
        self.sleep_onset = make_after(self.start_time, study_times['sleep_onset'])
        self.lights_on = make_after(self.sleep_onset, study_times['lights_on'])
        self.nsvt_times = nsvt_times

        # extract the sleeping stages (based on epoch) from the XML file for the patient
        fname = self.id.lower() + '.edf.XML'
        self.sleep_list = get_sleep_stages(xml_path, fname)

        # get the PLM event data
        self.plm_events = self.get_plm(xml_path, fname)

        # get the arousal events
        self.arousal_events = self.get_arousals(xml_path, fname)
        self.resp_events = self.get_respiratory_events(xml_path, fname)

        # find associations with other events
        self.plma_events, self.plm_resp_events = self.find_plm_associations()
        self.arousal_resp = self.find_arousal_association()
        self.arousal_plm = self.find_arousal_plm_assoc()

        # extract the O2 saturation from the EDF file
        self.o2_sat = self.extract_O2_sat(xml_path, self.id.lower())

    def walltime_to_epoch(self, time):
        dt = time - self.start_time

        # epoch 1 starts at dt=0 and is 30 seconds long
        return int(dt.seconds / 30.0) + 1

    def epoch_to_walltime(self, epoch):
        ts = self.start_time + datetime.timedelta(seconds=((epoch - 1) * 30.0))
        return (ts, ts + datetime.timedelta(seconds=30))

    def is_sleep_time(self, time):
        epoch = self.walltime_to_epoch(time)
        return self.is_sleep_epoch(epoch)

    def is_sleep_epoch(self, epoch):
        if self.sleep_list[epoch-1] == 0:
            return False
        else:
            return True

    def get_sleep_stage(self, when):
        if isinstance(when, datetime.datetime):
            epoch = self.walltime_to_epoch(when)
        else:
            epoch = when
        return self.sleep_list[epoch - 1]

    def get_control_periods(self, ctrl_window, ctrl_period_width):
        # find intervals of sleep that are at least ctrl_period_width

        # Find the intervals of sleep during the ctrl_window...
        sleep_times = []
        sleep_time = [0, 0]

        epoch = self.walltime_to_epoch(ctrl_window[0])
        if self.is_sleep_epoch(epoch):
            sleep_time[0] = ctrl_window[0]

        # this will list all epochs interior to the ctrl_window. Need to manually handle the edges
        epochs = range(self.walltime_to_epoch(ctrl_window[0])+1, self.walltime_to_epoch(ctrl_window[1])+1)
        for epoch in epochs:
            if self.is_sleep_epoch(epoch):
                if sleep_time[0] == 0:
                    sleep_time[0] = self.epoch_to_walltime(epoch)[0]
            else:
                if sleep_time[0] != 0:
                    sleep_time[1] = self.epoch_to_walltime(epoch)[0]
                    sleep_times.append((sleep_time[0], sleep_time[1]))
                    sleep_time = [0, 0]

        # handle the last epoch which might run past the edge of the window
        if sleep_time[0] !=0 and sleep_time[1] == 0:
            sleep_times.append((sleep_time[0], ctrl_window[1]))

        if not sleep_times:
            return None

        # Go through each sleep_time to see which are candidate control periods
        ctl_periods = []
        ctrl_period_width = datetime.timedelta(seconds=ctrl_period_width)
        for sleep_time in sleep_times:
            n_ctrl_periods = int((sleep_time[1] - sleep_time[0]).seconds / ctrl_period_width.seconds)
            for i in range(0,n_ctrl_periods):
                ts = sleep_time[0] + i * ctrl_period_width
                tf = ts + ctrl_period_width
                ctl_periods.append((ts, tf))

        return ctl_periods

    def get_hazard_period(self, nsvt_time, ctrl_period_width, nsvt_offset):
        """Compute the hazard period for a given NSVT event

        :param nsvt_time: datetime of the NSVT event
        :param ctrl_period_width: integer number of seconds
        :param nsvt_offset: integer number of seconds
        :return: tuple of datetimes
        """
        ctrl_period_width = datetime.timedelta(seconds=ctrl_period_width)
        nsvt_offset = datetime.timedelta(seconds=nsvt_offset)

        te = nsvt_time - nsvt_offset
        hazard_period = (te - ctrl_period_width, te)
        return hazard_period

    def get_plm(self, xml_path, fname):
        """Find all PLM events that occur for this patient
        PLM is denoted in the .XML file by <ScoredEvent> with <Name> = PLM (Right or Left)

        If the Right and Left start within 5 sec (< 5) then they are counted as a single event.

        :param xml_path: path to the XML files
        :param fname: name of the .XML file for this patient
        :return:
        """
        re_se = re.compile(ur'(<ScoredEvent><Name>PLM.+?<\/ScoredEvent>)')

        plm_events = []
        with open(xml_path + '\\' + fname, 'r') as f:
            data = f.read()
            for se in re.finditer(re_se, data):
                event = plm_from_xml(se.group(0))  # event is of class Plm

                event.tstart = self.start_time + datetime.timedelta(seconds=event.tstart)
                event.tend = self.start_time + datetime.timedelta(seconds=event.tend)

                # skip if awake at start of PLM event
                if not self.is_sleep_time(event.tstart):
                    continue

                # determine if this event is associated with the last event
                if len(plm_events) > 0:
                    if event.is_associated(plm_events[-1], 0.5):
                        # if it is, then extend the tend of the prev event and ignore the new event
                        plm_events[-1].tend = max(event.tend, plm_events[-1].tend)
                        plm_events[-1].side = event.side
                        continue

                plm_events.append(event)

        # Convert all PLM events in plm_events to windows of clock time
        plm_periods = []
        for event in plm_events:
            plm_periods.append((event.tstart, event.tend))

        return plm_periods

    def get_arousals(self, xml_path, fname):
        re_se = re.compile(ur'(<ScoredEvent><Name>Arousal.+?<\/ScoredEvent>)')

        events = []
        with open(xml_path + '\\' + fname, 'r') as f:
            data = f.read()
            for se in re.finditer(re_se, data):
                event = simple_event_from_xml(se.group(0))  # event is a tuple (tstart, tend) in seconds since start of recording

                ts = self.start_time + datetime.timedelta(seconds=event[0])
                te = self.start_time + datetime.timedelta(seconds=event[1])

                events.append((ts, te))

        return events

    def get_respiratory_events(self, xml_path, fname):
        # Central Apnea, Mixed Apena, Obstructive Apnea
        # Obstructive Hypopnea, Central Hypopnea, Mixed Hypopnea, Hypopnea
        events = {}
        map = {'ca': "Central Apnea",
               'ma': "Mixed Apnea",
               'oa': "Obstructive Apnea",
               'h':  "(Central |Mixed |Obstructive)*Hypopnea"
               }

        for k, v in map.iteritems():
            events[k] = []
            pattern = "<ScoredEvent><Name>" + v + ".+?<\/ScoredEvent>"

            re_se = re.compile(pattern)

            with open(xml_path + '\\' + fname, 'r') as f:
                data = f.read()
                for se in re.finditer(re_se, data):
                    event = simple_event_from_xml(se.group(0))  # event is a tuple (tstart, tend) in seconds since start of recording

                    # convert the event to wall time
                    ts = self.start_time + datetime.timedelta(seconds=event[0])
                    te = self.start_time + datetime.timedelta(seconds=event[1])

                    events[k].append((ts, te))
        return events

    def find_plm_associations(self):
        plma = [] # plm associated with arousals
        for plm in self.plm_events:
            for arousal in self.arousal_events:
                if is_associated(plm, arousal):
                    plma.append(plm)

        plm_resp = {} # plm associated with respiratory events
        for k in self.resp_events.keys():
            plm_resp[k] = []
            for event in self.resp_events[k]:
                for plm in self.plm_events:
                    if is_associated(event, plm, constraint=(-0.5, 0.5), fixedOrder=True):
                        plm_resp[k].append(plm)
                        continue  # there can be only 1 PLM associated with a given event

        return plma, plm_resp

    def find_arousal_association(self):
        # We don't care what kind of resp events...so squish them
        a = []
        for k, v in self.resp_events.iteritems():
            for event in v:
                a.append(event)
        resp_events = a

        arousal_resp = [] # arousals associated with Resp events
        for arousal in self.arousal_events:
            for resp in resp_events:
                if is_associated(resp, arousal, constraint=(-3.0, 3.0), fixedOrder=True):
                    arousal_resp.append(arousal)
                    continue # there can be only 1 Resp Event associated with an arousal
        return arousal_resp

    def find_arousal_plm_assoc(self):
        arousal_plm = [] # arousals associated with plm events
        for arousal in self.arousal_events:
            for plm in self.plm_events:
                if plm_arousal_associated(plm, arousal, constraint=(-0.5, 0.5)):
                    arousal_plm.append(arousal)
                    continue # there can be only 1 PLM Event associated with an arousal
        return arousal_plm

    def extract_O2_sat(self, edf_path, fname):
        a = EDF(edf_path + '\\' + fname + '.edf')
        if 'sao2' not in a.channels:
            print "sao2 channel not found in %s.edf" % fname
            return None

        o2 = a.channel_to_tuples('sao2', self.start_time)    # o2 is a list of tuples (t, value)

        return o2

    def get_min_O2sat(self, period):
        min_sat = float('inf')

        for t in self.o2_sat:
            if t[0] >= period[0] and t[0] < period[1]:
                if t[1] < min_sat and t[1] > 20.0:      # for some reason getting values = 0.005 and lower...
                    min_sat = t[1]

        # there are sometimes data dropout which will cause the output == inf but R does not like that
        # simply return an empty string instead
        if min_sat == float('inf'):
            return ""

        return min_sat
