import random
import time

# QT Widgets
from ...utils.qt_helper import *

from ...widgets.base_control_widgets import SingleInputWidget, SubControlWidget, try_init_value, get_tracked_value, make_client, _red_, _green_
from ...widgets.device_widget import DeviceReader
from ...modules import module

class TestDevice(DeviceReader):
    '''Pretends to be a device that responds with numbers'''
    def __init__(self, parent, id=0, data_key=None):
        super().__init__(parent, data_key, name=f"TEST_{id}", axis_title=f"??? (units)")

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3f}} ???'
        else:
            self.settings.title_fmt = f'Latest: {{:.3f}} ???'

        # Add some options to the settings
        self.settings.test_scale = 1.0
        self.settings._names_["test_scale"] = "Test Scale"

    def make_file_header(self):
        # Adjust the header to indicate ???
        return "Local Time\tValue (???)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We "read" only every 50ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        # We don't actually have a device, so we pretend to open something
        self.device = 1
        self.valid = True
        return self.device != None

    def read_device(self):
        if self.device is None:
            return False, 0
        # Report some random value
        var = random.random()
        # Sleep to emulate a read delay in the device
        time.sleep(0.05 + var * 1e-3)
        return True, var * self.settings.test_scale

    def close_device(self):
        if self.device is None:
            return
        # nothing was opened to close earlier
        self.device = None

class ControlTestWidget(SubControlWidget):
    def __init__(self, parent, name, label='', add_to_frame=True, **kargs):
        super().__init__(**kargs)
        self.parent = parent
        self.client = self.parent.client
        
        # Make the controls for sweeping
        # IV Curve controls
        self.outer_layout = QVBoxLayout()
        self.outer_layout.setSpacing(0)
        self.inner_layout = QHBoxLayout()
        self.inner_layout.setSpacing(0)

        if add_to_frame:
            self.frame.setLayout(self.outer_layout)
            self.dock.setTitle(name)

        self.active = False

        self.active_btn = QCheckBox("Active")
        header = QHBoxLayout()
        header.addWidget(QLabel(label))
        header.addWidget(self.active_btn)
        self.outer_layout.addLayout(header)

        self.active_btn.clicked.connect(self.activate)

    def set_locked_texture(self, button):
        button.setStyleSheet(f"background-color : {_red_}")

    def set_unlocked_texture(self, button):
        button.setStyleSheet(f"background-color : {_green_}")

    def on_deactivate(self):
        self.active_btn.setChecked(False)
        self.active = False

    def on_activate(self):
        self.active_btn.setChecked(True)
        self.active = True

    def activate(self):
        for mode in self.parent.modes:
            if mode is not self and mode.is_active():
                mode.on_deactivate()
        self.on_activate()

    def is_active(self):
        return self.active

class ShiftScaleWidget(ControlTestWidget):
    def __init__(self, parent, **kargs):
        super().__init__(parent, f'{parent.name} Shift/Scale', "Shift Scale", **kargs)

        self.shift_key = f'{parent.name}_SHIFT'
        self.scale_key = f'{parent.name}_SCALE'

        # If we are using MQTT, then we will translate the ctrl value to the non ctrl one
        if module.USE_MQTT:
            def on_shift(key, stamp, value):
                module.publish_mqtt_data(key, value, stamp)
            def on_scale(key, stamp, value):
                module.publish_mqtt_data(key, value, stamp)
            module.register_ctrl_handler(self.shift_key, on_shift)
            module.register_ctrl_handler(self.scale_key, on_scale)

        # Then call init of the values
        try_init_value(self.shift_key, 0.0)
        try_init_value(self.scale_key, 1.0)
        
        line = SingleInputWidget(self, self.shift_key, "{:.2f}")
        self.inner_layout.addWidget(line)
        self._modules.append(line)
        
        line = SingleInputWidget(self, self.scale_key, "{:.2f}")
        self.inner_layout.addWidget(line)
        self._modules.append(line)

        self.inner_layout.addStretch(0)

        self.outer_layout.addLayout(self.inner_layout)

    def on_run_loop(self):
        _, self.parent.shift = get_tracked_value(self.shift_key)
        _, self.parent.scale = get_tracked_value(self.scale_key)

class ControlTestDevice(TestDevice):
    def __init__(self, parent, id=0, data_key=None):
        super().__init__(parent, id, data_key)
        self.scale = 1
        self.shift = 0

        self.client = make_client()

        self.modes = []
        
        mode = ShiftScaleWidget(self)
        self._modules.append(mode)
        self.modes.append(mode)

    def post_added_to_dockarea(self):
        module = None
        print("Adding sub docks")
        for mode in self.modes:
            if module is None:
                self.parent.plot_widget.addDock(mode.dock, 'top', self.dock)
            else:
                self.parent.plot_widget.addDock(mode.dock, 'above', module.dock)
            module = mode
        # self.modes[0].dock.raiseDock()
        self.modes[0].activate()
        return super().post_added_to_dockarea()

    def do_device_update(self):
        # Run whichever mode is active
        for mode in self.modes:
            if mode.is_active():
                mode.on_run_loop()
                break
        # We then also do the super class's update, as we otherwise act like a device reader
        return super().do_device_update()

    def read_device(self):
        if self.device is None:
            return False, 0
        # Report some random value
        var = random.random()
        # Sleep to emulate a read delay in the device
        time.sleep(0.05 + var * 1e-3)
        return True, var * self.settings.test_scale * self.scale + self.shift