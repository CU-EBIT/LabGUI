def copy_driver_methods(driver, holder, allowed=lambda method:method != 'open_device' and method != 'close_device' and not method.startswith("_")):
    object_methods = [method_name for method_name in dir(driver)
                    if callable(getattr(driver, method_name))]
    for method in object_methods:
        if allowed(method):
            setattr(holder, method, getattr(driver, method))

class BaseDevice:

    def __init__(self) -> None:
        self.device = None

    def open_device(self):
        """
        Handles opening the device to read. Here implementers should also handle any exceptions which may occur!

        Returns:
            bool: whether device opened
        """
        raise RuntimeWarning("Not implemented in base class")

    def close_device(self):
        """
        Handles closing the device. Any exceptions thrown will be printed to console and otherwise ignored.
        """
        raise RuntimeWarning("Not implemented in base class")
    
    def write(self, cmd):
        raise RuntimeWarning("Not implemented in base class")
    
    def query(self, cmd):
        raise RuntimeWarning("Not implemented in base class")
    
    def read(self):
        raise RuntimeWarning("Not implemented in base class")
    
    def read_raw(self):
        raise RuntimeWarning("Not implemented in base class")

class BaseSourceDevice:
    def is_output_enabled(self):
        """
        Returns:
            bool: whether output is enabled
        """
        raise RuntimeWarning("Not implemented in base class")

    def enable_output(self, output:bool):
        """Enables the device

        Args:
            output (bool): output state to set

        Returns:
            bool: whether new output matches the argument
        """
        raise RuntimeWarning("Not implemented in base class")
    
    def toggle_output(self):
        """Toggles the state of the output
        """
        output = self.is_output_enabled()
        self.enable_output(not output)

class BasicVoltageSource(BaseSourceDevice):
    
    def get_set_voltage(self):
        """returns the voltage setpoint for the device

        Returns:
            float: set value for voltage
        """
        raise RuntimeWarning("Not implemented in base class")
    
    def set_voltage(self, voltage:float):
        """changes the voltage setpoint for the device

        Args:
            voltage (float): voltage to set.

        Returns:
            bool: whether the voltage setpoint was changed
        """
        raise RuntimeWarning("Not implemented in base class")

class BasicCurrentSource(BaseSourceDevice):
    
    def get_set_current(self):
        """returns the current setpoint for the device

        Returns:
            float: set value for current
        """
        raise RuntimeWarning("Not implemented in base class")
    
    def set_current(self, current:float):
        """changes the current setpoint for the device

        Args:
            current (float): current to set.

        Returns:
            bool: whether the current setpoint was changed
        """
        raise RuntimeWarning("Not implemented in base class")
    
class BasicVoltageMeasure:
    def get_voltage(self):
        """returns the voltage measured by the device

        Returns:
            float: measured voltage
        """
        raise RuntimeWarning("Not implemented in base class")
    
class BasicCurrentMeasure:
    def get_current(self):
        """returns the current measured by the device

        Returns:
            float: measured current
        """
        raise RuntimeWarning("Not implemented in base class")