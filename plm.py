###########################################################
# plm.py
# Define class Plm which is a single Periodic Limb Movement
# event defined by a side, start time, and end time
#
# Ryan D May
# Cairn Systems
# January 3rd, 2016
###########################################################


class Plm:
    def __init__(self, tstart=None, tend=None, side=None):
        self.tstart = tstart
        self.tend = tend
        self.side = side

    # returns the duration of the event
    def duration(self):
        return (self.tend - self.tstart).seconds

    # determines if an event SELF is associated with another
    # PLM event PREV_EVENT
    def is_associated(self, prev_event, dt_start=0.5):
        if self.side == prev_event.side:
            return False

        if (self.tstart - prev_event.tstart).seconds < dt_start:
            return True
        else:
            return False
