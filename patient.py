from helper import get_sleep_stages

class Patient:
    id = ""
    lights_on = None
    sleep_onset = None
    start_time = None
    nsvt_times = None

    def __init__(self, id, study_times, start_time, nsvt_times, xml_path):
        self.id = id
        self.lights_on = study_times['lights_on']
        self.sleep_onset = study_times['sleep_onset']
        self.start_time = start_time
        self.nsvt_times = nsvt_times

        # extract the sleeping stages (based on epoch) from the XML file for the patient
        fname = self.id.lower() + '.edf.XML'
        self.sleep_list = get_sleep_stages(xml_path, fname)

    def walltime_to_epoch(self, time):
        dt = time - self.start_time

        # epoch 1 starts at dt=0 and is 30 seconds long
        return int(dt.seconds / 30.0) + 1

    def is_sleep_epoch(self, time):
        if isinstance(time, tuple):
            # convert the clt_period's times into epoch #
            start_epoch = self.walltime_to_epoch(time[0])
            end_epoch   = self.walltime_to_epoch(time[1])
            test_epochs = range(start_epoch, end_epoch+1)
        else:
            test_epochs = [self.walltime_to_epoch(time)]

        for epoch in test_epochs:
            if self.sleep_list[epoch-1] == 0:
                return False

        return True
