from .module import FigureModule
from .module import Menu

from ..widgets.plot_widget import Plot
from ..widgets.base_control_widgets import addCrossHairs

# These are default axis titles and scaling factors for the live plots
_option_defaults_ = {
    'Pressure_HV_Source': ('Source Pressure (mbar)', 1, '{:.2e}', True),
    'Pressure_HV_Section 1': ('Section 1 Pressure (mbar)', 1, '{:.2e}', True),
    'Pressure_HV_Section 2': ('Section 2 Pressure (mbar)', 1, '{:.2e}', True),

    'Temperature_Source Flange': ('Source Flange Temperature (K)', 1, '{:.1f}'),
    'Temperature_Section 1': ('Section 1 Temperature (K)', 1, '{:.1f}'),
    'Temperature_Section 2': ('Section 2 Temperature (K)', 1, '{:.1f}'),

    'Temperature_Water_DI_Out': ('DI Supply Temperature (K)', 1, '{:.1f}'),
    'Temperature_Water_DI_In': ('DI Return Temperature (K)', 1, '{:.1f}'),
    'Temperature_Water_Condenser_Supply': ('Condenser Supply Temperature (K)', 1, '{:.1f}'),
    'Temperature_Water_Condenser_Return': ('Condenser Return Temperature (K)', 1, '{:.1f}'),

    'Temperature_Cryo_S1': ('Cryo Stage 1 (K)', 1, '{:.1f}'),
    'Temperature_Cryo_S2': ('Cryo Stage 2 (K)', 1, '{:.1f}'),
    'Temperature_Cryo_SW': ('Cryo Switch (K)', 1, '{:.1f}'),
    'Temperature_Cryo_MA': ('Cryo Magnet A (K)', 1, '{:.1f}'),
    'Temperature_Cryo_MB': ('Cryo Magnet B (K)', 1, '{:.1f}'),

    'Anode_Current': ('Anode Current (uA)', 1, '{:.2f}'),
    'Cathode_Emission': ('Cathode Emission (mA)', 1, '{:.2f}'),

    'FC1_Value' : ('FC1 Current (pA)', 1e12),
    'FC2_Value': ('FC2 Current (pA)', 1e12),
    'Bend_Magnet_Field': ('Bending Field Strength (mT)', 1e3),
}

# These are what get added to the drop-down menu for live plot settings
_options_ = {}
_options_['source_key'] = [x for x in _option_defaults_.keys()]

class PlotModule(FigureModule):

    def __init__(self, root):
        super().__init__(root)

        if root.init_call is None:
            root.init_call = self.new_plotter

        self.start_index = 0
        self.initialised = False
        self._has_value = False
        self.data_raw = None
        self.data_avg = None
        self.last_stamp = 0.0
        self.plot_widget = Plot()
        self.settings = self.plot_widget.settings
        self.settings._options_ = _options_

        # These allow only changing the key, and having everything else update accordingly.
        self.settings._option_defaults_ = _option_defaults_

        self.settings._callback = self.update_settings
        self.plot_widget.keys = [[self.settings.source_key, "Raw Value", "Smoothed"]]

        self.plot_widget.setup()
        def check_key():
            self.update_settings()
        self.plot_widget.tick_callback = check_key

        self.set_saves("Live Plotter")

    def populate_save_values(self, values):
        values['settings'] = self.settings

    def make_dummy_plotter(root):
        plotter = PlotModule(root)
        plotter.dummy = True
        root._modules.append(plotter)
        plotter.get_menus() # Init menus
        plotter.on_start()
        return plotter

    def new_plotter(self):
        plotter = PlotModule.make_dummy_plotter(self._root)
        plotter.start_plotting()

    def on_stop(self):
        if self.dummy:
            self._root.remove_module(self)
        self.initialised = False
        return super().on_stop()

    def get_settings(self):
        # Return an array or collection of settings here
        # Module can have more than 1 set of settings.
        return [self.settings]

    def update_settings(self):
        if self.plot_widget is not None:
            self.plot_widget.keys[0][0] = self.settings.source_key
        self.pause_animation(self.settings.paused)

    def make_plot(self):
        self.plot_widget.start()

    def post_figure(self):
        self.get_plot_layout().addWidget(self.plot_widget.plot_widget._coord_label)

    def get_menus(self):
        _menu = Menu()

        # Add some options, the value is the function to run on click
        _menu._options["live_plot"] = self.new_plotter

        _menu._opts_order.append("live_plot")

        # Adds some help menu text for these as well
        _menu._helps["live_plot"] = 'Starts a live plot of values'

        # Adds labels for the non-separator values
        _menu._labels["live_plot"] = "Live Plot"

        # Specify a label for the menu
        _menu._label = "Plots"

        # Returns an array of menus (only 1 in this case)
        return [_menu]