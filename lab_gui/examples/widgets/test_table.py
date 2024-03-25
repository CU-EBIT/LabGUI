import random
import math
from datetime import timedelta
from datetime import datetime

from ...widgets.base_control_widgets import SubControlWidget, TableDisplayWidget
from ...utils.qt_helper import QVBoxLayout, QHBoxLayout


class TableDisplay(SubControlWidget):
    def __init__(self, parent, **args):
        super().__init__(**args)
        self.client = parent.data_client

        self.table = self.make_table()
        
        self._layout = QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.addStretch(1)

        holder = QHBoxLayout()
        holder.setContentsMargins(0,0,0,0)

        holder.addWidget(self.table)
        holder.addStretch(1)

        self.table.verticalHeader().setVisible(False)

        self._modules.append(self.table)
        self._layout.addLayout(holder)
        self._layout.addStretch(1)
        self.frame.setLayout(self._layout)
    
    def make_table(self):
        headers = ["", "HV", "RV"]
        rows = [
            ["Section A", "Pressure_HV_A", "{:.2e} mbar", "Pressure_RV_A", "{:.2e} mbar"],
            ["Section B", "Pressure_HV_B", "{:.2e} mbar", "Pressure_RV_B", "{:.2e} mbar"],
            ["Section C", "Pressure_HV_C", "{:.2e} mbar", "Pressure_RV_C", "{:.2e} mbar"],
        ]
        table = TableDisplayWidget(self, headers, rows).no_clicky()
        return table

    def frame_size(self):
        h = self.table.horizontalHeader().height()
        w = self.table.verticalHeader().width()
        for i in range(self.table.rowCount()):
            h += self.table.rowHeight(i)
        for i in range(self.table.columnCount()):
            w += self.table.columnWidth(i)
        self.w = w
        self.h = h
            
        m = self.frame.contentsMargins()
        mw = m.left() + m.right()
        mh = m.top() + m.bottom()
        m = self._layout.contentsMargins()
        mw += m.left() + m.right()
        mh += m.top() + m.bottom()
        
        h += mh
        w += mw

        self.resize(w, h)

    def on_update(self):
        rect = self.table.rect()
        h = rect.height()
        w = rect.width()
        if h != self.h or w != self.w:
            self.frame_size()
        # We make the values ourself as this is a test.

        self.client.set_float("Pressure_HV_A", (1 + random.random()*0.05) * 1e-9)
        self.client.set_float("Pressure_RV_A", (1 - random.random()*0.05) * 1e-4)

        self.client.set_float("Pressure_HV_B", (1 + random.random()*0.05) * 1e-9)
        self.client.set_float("Pressure_RV_B", (1 - random.random()*0.05) * 1e-4)

        self.client.set_float("Pressure_HV_C", (1 + random.random()*0.05) * 1e-9)
        self.client.set_float("Pressure_RV_C", (1 - random.random()*0.05) * 1e-4)

        return super().on_update()

class ColourHelper:
        
    def colour_scale(value, timestamp, low, high, timeout=10, off=1e-11, log=True):
        '''    
        This scales the colour of a box so that things above high are red, below low are green.

        values between high and low enx up a shade of green - yellow - orange - red depending on
        how close they are to high or low.

        If a value has not updated for 10s, it is shaded dark red.
        It also goes dark red if the value is not valid, due to gauge being off.
        '''

        # Default is bright red
        r = 1.0
        g = 0.0
        b = 0.0

        # This is set false if not a valid reading
        valid = True

        # convert to logs for the colouring for pressures.
        if log:
            low = math.log(low)
            high = math.log(high)
            value = math.log(value)
            off = math.log(off)

        now = datetime.now()
        # This is where the 10s timer is defined.
        max_dt = timedelta(seconds=timeout)
        dt = now - timestamp
        
        # If below the "off" threshold, just turn a dark red
        if value <= off:
            r = 0.25
            g = 0.1
            b = 0.1
            # this counts as an invalid reading
            valid = False
        elif dt > max_dt:
            # If exceeded timeout, go dark red
            r = 0.5
            # this counts as an invalid reading
            valid = False
        elif value < low:
            # If below low pressure, just green
            r = 0.0
            g = 1.0
        elif value < high:
            # Otherwise, pick how close we are to high
            dp = value - low
            dm = high - low
            dm /= 2
            dh = low + dm

            if value < dh:
            # increase red amount from green for first half
                g = 1.0
                r = dp / dm
            else:
            # Then decrease green for second half
                r = 1.0
                g = 1.0 - (dp - dm) / dm
        r = int(255.0 * r)
        g = int(255.0 * g)
        b = int(255.0 * b)
        return (r, g, b), valid

    def colour_uhv(pressure, timestamp):
        '''Default settings for UHV'''
        return ColourHelper.colour_scale(pressure, timestamp, 2e-10, 1e-8)

    def colour_hv(pressure, timestamp):
        '''Default settings for HV'''
        return ColourHelper.colour_scale(pressure, timestamp, 2e-7, 1e-5)
    
    def colour_rv(pressure, timestamp):
        '''Default settings for RV'''
        return ColourHelper.colour_scale(pressure, timestamp, 1e-4, 1e-3)
    

class ColourTableDisplay(TableDisplay):

    def __init__(self, parent, **args):
        super().__init__(parent, **args)

    def make_table(self):
        table = super().make_table()

        self.colourers = {}
        self.times = {}
        # A row
        self.colourers[f'0,1'] = ColourHelper.colour_uhv
        self.colourers[f'0,2'] = ColourHelper.colour_rv
        # B row
        self.colourers[f'1,1'] = ColourHelper.colour_uhv
        self.colourers[f'1,2'] = ColourHelper.colour_rv
        # C row
        self.colourers[f'2,1'] = ColourHelper.colour_uhv
        self.colourers[f'2,2'] = ColourHelper.colour_rv

        return table
    
    def update_values(self):
        # First update the values
        super().update_values()
        # Then recolour accordingly
        for key, colourer in self.colourers.items():
            cell = self.table.cells[key]
            val = cell[1]
            cell = cell[0]
            valid = val is not None
            colour = (64, 25, 25)
            if valid:
                timestamp = val[0]
                if not key in self.times:
                    self.times[key] = [timestamp, datetime.now()]

                old_stamp = self.times[key]
                if old_stamp[0] != timestamp:
                    old_stamp[0] = timestamp
                    old_stamp[1] = datetime.now()
                timestamp = old_stamp[1]

                pressure = val[1]
                colour, valid = colourer(pressure, timestamp)
            rgb = f"{colour[0]},{colour[1]},{colour[2]}"
            cell.setStyleSheet(f'background-color: rgb({rgb})')