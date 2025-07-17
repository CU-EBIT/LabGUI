import time

#  * import due to just being things from Qt
from ..utils.qt_helper import *

from .device_widget import DeviceController
from .drivers.glassman_controller import GlassmanController
from .device_types.devices import BasicVoltageSource
from .base_control_widgets import ControlLine, LineEdit, scale

class DualGlassman(DeviceController, BasicVoltageSource):
    """
    This controls 2 analog glassman power supplies, a 3kV and a 5kV one, using a usb NIDAQ
    """
    def __init__(self, parent, name="Dual Glassman", set_keys=[None,None]):
        """

        Args:
            parent (FigureModule): the module we are made from
        """
        super().__init__(parent, name, fixed_size=True)

        self.set_keys = set_keys
        self.V5kV = 0
        self.V5kV_O = self.V5kV

        self.O5kV = False
        self.O5kV_O = self.O5kV

        self.hv_5kV_button = QCheckBox("HV Output")
        self.hv_5kV_button.setChecked(False)
        self.hv_5kV_button.clicked.connect(self.toggle_HV_5kV)
        self.output_entry_5kV = ControlLine(self.set_voltage_5kV, LineEdit(f"{self.V5kV}"), min=0, max=5000)

        layout_1 = QHBoxLayout()
        layout_1.addWidget(self.hv_5kV_button)
        layout_1.addWidget(self.output_entry_5kV.box)
        layout_1.addWidget(QLabel("V"))
        layout_1.addStretch(0)
        
        self.V3kV = 0
        self.V3kV_O = self.V3kV

        self.O3kV = False
        self.O3kV_O = self.O3kV

        self.hv_3kV_button = QCheckBox("HV Output")
        self.hv_3kV_button.setChecked(False)
        self.hv_3kV_button.clicked.connect(self.toggle_HV_3kV)
        self.output_entry_3kV = ControlLine(self.set_voltage_3kV, LineEdit(f"{self.V3kV}"), min=0, max=3000)

        layout_2 = QHBoxLayout()
        layout_2.addWidget(self.hv_3kV_button)
        layout_2.addWidget(self.output_entry_3kV.box)
        layout_2.addWidget(QLabel("V"))
        layout_2.addStretch(0)
        
        self._frame = QFrame()
        self._frame.setLineWidth(2)
        self._frame.setFrameShape(QFrame.Shape.WinPanel)
        self._frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._frame.setContentsMargins(2,2,2,2)
        
        self.output_entry_5kV.box.setFixedWidth(50)
        self.output_entry_3kV.box.setFixedWidth(50)

        w = 160
        h = 120

        w *= scale(self.get_dpi())
        self._frame.setFixedWidth(int(w))
        h *= scale(self.get_dpi())
        self._frame.setFixedHeight(int(h))

        self._layout.removeWidget(self.active_button)

        self._layout_ = QVBoxLayout()
        self._layout_.setSpacing(0)
        self._layout_.addWidget(self.active_button)
        self._layout_.addWidget(QLabel("5kV Controller"))
        self._layout_.addLayout(layout_1)

        self._layout_.addWidget(QLabel("3kV Controller"))
        self._layout_.addLayout(layout_2)

        self._frame.setLayout(self._layout_)

        self._layout.addWidget(self._frame)
        self._layout.addStretch(0)

    def frame_size(self):
        self.resize(180,140)

    def collect_saved_values(self, values):
        values['V5kV'] = self.output_entry_5kV.box
        values['O5kV'] = self.hv_5kV_button

        values['V3kV'] = self.output_entry_3kV.box
        values['O3kV'] = self.hv_3kV_button

        return super().collect_saved_values(values)

    def process_load_saved(self):
        try:
            self.V5kV = float(self.output_entry_5kV.box.text())
            self.O5kV = self.hv_5kV_button.isChecked()

            self.V5kV_O = self.V5kV
            self.O5kV_O = self.O5kV

            self.V3kV = float(self.output_entry_3kV.box.text())
            self.O3kV = self.hv_3kV_button.isChecked()

            self.V3kV_O = self.V3kV
            self.O3kV_O = self.O3kV
        except Exception as err:
            print(err)
            print(f"failed to load state for {self.name}")
        return super().process_load_saved()

    def open_device(self):
        self.device = None
        try:
            self.device = GlassmanController()
        except Exception as err:
            print(err)
            print("failed to open glassman controller?")
            self.device = None
        return self.device != None
    
    def close_device(self):
        if self.device is not None:
            del self.device
            self.device = None
    
    def do_device_update(self):
        if self.device is None:
            return
        if self.set_keys[1] != None:
            vars = self.client.get_float(self.set_keys[1])
            if vars != None and self.V3kV != vars[1]:
                self.output_entry_3kV.box.setText(f'{vars[1]:.2f}')
                self.V3kV = vars[1]
        if self.set_keys[0] != None:
            vars = self.client.get_float(self.set_keys[0])
            if vars != None and self.V5kV != vars[1]:
                self.output_entry_5kV.box.setText(f'{vars[1]:.2f}')
                self.V5kV = vars[1]

        if self.V5kV != self.V5kV_O:
            print(f"Setting Voltage 5: {self.V5kV}")
            self.device.set_voltage(self.V5kV, channel=0)
            self.V5kV_O = self.V5kV
        if self.O5kV != self.O5kV_O:
            print(f"Setting HV 5: {self.O5kV}")
            self.device.toggle_HV(1 if self.O5kV else 0, channel=0)
            self.O5kV_O = self.O5kV
        if self.V3kV != self.V3kV_O:
            print(f"Setting Voltage 3: {self.V3kV}")
            self.device.set_voltage(self.V3kV, channel=1)
            self.V3kV_O = self.V3kV
        if self.O3kV != self.O3kV_O:
            print(f"Setting HV 3: {self.O3kV}")
            self.device.toggle_HV(1 if self.O3kV else 0, channel=1)
            self.O3kV_O = self.O3kV
        time.sleep(0.05)

    def set_voltage_5kV(self):
        try:
            self.V5kV_O = self.V5kV
            self.V5kV = float(self.output_entry_5kV.box.text())
            if self.set_keys[0] != None:
                self.client.set_float(self.set_keys[0], self.V5kV)
                print("Updated", self.set_keys[0])
            self.saver.on_changed(self.output_entry_5kV.box)
        except Exception as err:
            print(err)

    def toggle_HV_5kV(self):
        self.O5kV_O = self.O5kV
        self.O5kV = self.hv_5kV_button.isChecked()
        self.saver.on_changed(self.hv_5kV_button)

    def set_voltage_3kV(self):
        try:
            self.V3kV_O = self.V3kV
            self.V3kV = float(self.output_entry_3kV.box.text())
            if self.set_keys[1] != None:
                self.client.set_float(self.set_keys[1], self.V3kV)
                print("Updated", self.set_keys[1])
            self.saver.on_changed(self.output_entry_3kV.box)
        except Exception as err:
            print(err)

    def toggle_HV_3kV(self):
        self.O3kV_O = self.O3kV
        self.O3kV = self.hv_3kV_button.isChecked()
        self.saver.on_changed(self.hv_3kV_button)

    def set_voltage(self, voltage:float, channel:int):
        if channel == 0:
            self.set_voltage_5kV(voltage)
        elif channel == 1:
            self.set_voltage_3kV(voltage)

    def is_output_enabled(self, channel:int):
        if channel == 0:
            return self.O5kV
        elif channel == 1:
            return self.O3kV
        
    def toggle_output(self, channel:int):
        if channel == 0:
            self.toggle_HV_5kV()
        elif channel == 1:
            self.toggle_HV_3kV()

    def get_set_voltage(self, channel:int):
        if channel == 0:
            return self.V5kV
        elif channel == 1:
            return self.V3kV