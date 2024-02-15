import time

#  * import due to just being things from Qt
from utils.qt_helper import *

from .device_widget import DeviceController
from .drivers.deflectors import DeflectorSupply, setXV, setYV, setXV_2, setYV_2
from .base_control_widgets import ControlLine, LineEdit, scale

class RickDeflectors(DeviceController):
    """
    Controller for using Tim's power supply to control Rick's deflectors.
    """    
    def __init__(self, parent, port="COM10", name="Rick's Deflector Control"):
        super().__init__(parent, name, fixed_size=True)

        self.X1 = 0
        self.X2 = 0
        self.Y1 = 0
        self.Y2 = 0

        self.X1_O = self.X1
        self.X2_O = self.X2
        self.Y1_O = self.Y1
        self.Y2_O = self.Y2

        self.VX1 = ControlLine(self.set_XV_1, LineEdit(f"{self.X1}"), set_fmt="{:.2f}", min=0, max=500)
        self.VX2 = ControlLine(self.set_XV_2, LineEdit(f"{self.X2}"), set_fmt="{:.2f}", min=0, max=500)
        self.VY1 = ControlLine(self.set_YV_1, LineEdit(f"{self.Y1}"), set_fmt="{:.2f}", min=0, max=500)
        self.VY2 = ControlLine(self.set_YV_2, LineEdit(f"{self.Y2}"), set_fmt="{:.2f}", min=0, max=500)

        self._layout.removeWidget(self.active_button)

        self._frame = QFrame()
        self._frame.setLineWidth(2)
        self._frame.setFrameShape(QFrame.Shape.WinPanel)
        self._frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._frame.setContentsMargins(2,2,2,2)

        # Adjust sizes of the input boxes
        self.VX1.box.setFixedWidth(40)
        self.VX2.box.setFixedWidth(40)
        self.VY1.box.setFixedWidth(40)
        self.VY2.box.setFixedWidth(40)

        w = 160
        h = 120

        w *= scale(self.get_dpi())
        self._frame.setFixedWidth(int(w))
        h *= scale(self.get_dpi())
        self._frame.setFixedHeight(int(h))

        self._layout_ = QVBoxLayout()
        self._layout_.setSpacing(0)

        self._layout_.addWidget(self.active_button)

        layout_1 = QHBoxLayout()
        layout_1.addWidget(QLabel("X1:"))
        layout_1.addWidget(self.VX1.box)
        layout_1.addWidget(QLabel(" V  Y1:"))
        layout_1.addWidget(self.VY1.box)
        layout_1.addWidget(QLabel(" V"))
        layout_1.addStretch(0)
        self._layout_.addLayout(layout_1)

        layout_2 = QHBoxLayout()
        layout_2.addWidget(QLabel("X2:"))
        layout_2.addWidget(self.VX2.box)
        layout_2.addWidget(QLabel(" V  Y2:"))
        layout_2.addWidget(self.VY2.box)
        layout_2.addWidget(QLabel(" V"))
        layout_2.addStretch(0)
        self._layout_.addLayout(layout_2)

        self._frame.setLayout(self._layout_)
        self._layout.addWidget(self._frame)

        self._layout.addStretch(0)
        self.port = port

    def frame_size(self):
        self.resize(180,140)
        
    def collect_saved_values(self, values):
        values['X1'] = self.VX1.box
        values['X2'] = self.VX2.box
        values['Y1'] = self.VY1.box
        values['Y2'] = self.VY2.box

        return super().collect_saved_values(values)
    
    def process_load_saved(self):
        try:
            self.X1 = float(self.VX1.box.text())
            self.X2 = float(self.VX2.box.text())
            self.Y1 = float(self.VY1.box.text())
            self.Y2 = float(self.VY2.box.text())

            self.X1_O = self.X1
            self.X2_O = self.X2
            self.Y1_O = self.Y1
            self.Y2_O = self.Y2
        except Exception as err:
            print(err)
            print(f"failed to load state for {self.name}")

        return super().process_load_saved()

    def open_device(self):
        try:
            self.device = DeflectorSupply()
            self.device.open(self.port)
        except Exception as err:
            print(err)
            print("failed to open deflector controller?")
            self.device = None
        return self.device != None

    def close_device(self):
        if self.device is not None:
            self.device.close()

    def do_device_update(self):
        if self.X1 != self.X1_O:
            setXV(self.device, self.X1)
            self.X1_O = self.X1
        if self.X2 != self.X2_O:
            setXV_2(self.device, self.X2)
            self.X1_O = self.X1
        if self.Y1 != self.Y1_O:
            setYV(self.device, self.Y1)
            self.Y1_O = self.Y1
        if self.Y2 != self.Y2_O:
            setYV_2(self.device, self.Y2)
            self.Y2_O = self.Y2
        time.sleep(0.1)

    def set_XV_1(self):
        try:
            self.X1_O = self.X1
            self.X1 = float(self.VX1.box.text())
            self.saver.on_changed(self.VX1.box)
        except Exception as err:
            print(err)

    def set_XV_2(self):
        try:
            self.X2_O = self.X2
            self.X2 = float(self.VX2.box.text())
            self.saver.on_changed(self.VX2.box)
        except Exception as err:
            print(err)

    def set_YV_1(self):
        try:
            self.Y1_O = self.Y1
            self.Y1 = float(self.VY1.box.text())
            self.saver.on_changed(self.VY1.box)
        except Exception as err:
            print(err)

    def set_YV_2(self):
        try:
            self.Y2_O = self.Y2
            self.Y2 = float(self.VY2.box.text())
            self.saver.on_changed(self.VY2.box)
        except Exception as err:
            print(err)
