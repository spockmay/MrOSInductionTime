import datetime

from helper import get_sleep_stages, make_after

class Patient:
    id = ""
    lights_on = None
    sleep_onset = None
    start_time = None
    nsvt_times = None

    def __init__(self, id, study_times, start_time, nsvt_times, xml_path):
        self.id = id
        self.start_time = start_time
        self.sleep_onset = make_after(self.start_time, study_times['sleep_onset'])
        self.lights_on = make_after(self.sleep_onset, study_times['lights_on'])
        self.nsvt_times = nsvt_times

        # extract the sleeping stages (based on epoch) from the XML file for the patient
        fname = self.id.lower() + '.edf.XML'
        self.sleep_list = get_sleep_stages(xml_path, fname)

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