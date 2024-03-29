import time
import numpy as np
import scipy
from dateutil import parser

from .module import FigureModule
from .module import Menu
from .module import BetterAxisItem

from ..widgets.plot_widget import Plot, get_value_log
from ..widgets.base_control_widgets import addCrossHairs

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
        self.plot_widget = Plot(x_axis=BetterAxisItem('bottom'))
        self.plot_widget.cull_x_axis = False
        self.plot_widget.show_avg = False
        self.settings = self.plot_widget.settings
        self.init_settings()

        self.plot_widget.get_data = self.get_plot_data
        self.plot_widget.update_values = self.update_plot_values
        self.plot_widget.refresh_from_settings = lambda *_:_

        self.settings._callback = self.update_settings
        self.plot_widget.keys = [['y_value',None,None],['y_2_value',None,None]]

        self.plot_data = [[], [], [], False, 0]
        self.plots = {}

        self.plot_widget.setup()
        def check_key():
            self.update_settings()
        self.plot_widget.tick_callback = check_key

        self.set_saves("Comparison Plotter")

    def init_settings(self):
        self.settings._options_ = {}
        self.settings._option_defaults_ = {}
        self.settings._buttons_ = []
        stale_settings = [key for key in self.settings._names_.keys()]

        for setting in stale_settings:
            if setting in self.settings._names_:
                del self.settings._names_[setting]

        def add_option(key, header, unit=None, default=None, dropdown=False):
            setattr(self.settings, key, default)
            self.settings._names_[key] = header
            if unit is not None:
                self.settings._units_[key] = unit
            if dropdown:
                self.settings._options_[key] = []

        add_option("time_bin", "Time Bin Size", 's', 1.0)
        add_option("x_value", "X Axis Key", dropdown=True)
        add_option("y_value", "Y Axis Key", dropdown=True)
        add_option("y_2_value", "Second Y Axis Key", dropdown=True)

        add_option("x_start", "Start time:", 's, unix, or -(seconds from now)', -60)
        add_option("x_end", "End time:", 's, unix or -1', -1)
        add_option("y_phase", "Y Time Shift:", 's', 0)
        add_option("y_2_phase", "Second Y Time Shift:", 's', 0)

    def get_plot_data(self, key):
        if key in self.plots:
            return self.plots[key]
        return self.plot_data

    def update_plot_values(self, *_):
        # This means we are plotting them live
        if self.settings.x_start < 0:
            self.set_plot_values()
        return
    
    def set_plot_values(self):
        self.plots = {}
        self.plot_widget._has_value = False
        def check_empty(x):
            if x == '':
                return None
            if x == 'None':
                return None
            return x
        x_value = check_empty(self.settings.x_value)
        y_value = check_empty(self.settings.y_value)
        y_2_value = check_empty(self.settings.y_2_value)

        if x_value is None:
            return
        if y_value is None:
            y_value = y_2_value
        if y_value is None:
            return
        
        now = time.time()
        end = self.settings.x_end
        if end < 0:
            end = now + 3600
        last = self.settings.x_start
        if last < 0:
            last = now + last

        _, x_data = get_value_log(x_value, since=last, until=end)
        if len(x_data) == 0:
            return

        x_times = np.array([parser.parse(val[0]).timestamp() for val in x_data])
        x_value = np.array([val[1] for val in x_data])

        _, y_data = get_value_log(y_value, since=last + self.settings.y_phase, until=end + self.settings.y_phase)
        y_times = np.array([parser.parse(val[0]).timestamp() - self.settings.y_phase for val in y_data])
        y_value = np.array([val[1] for val in y_data])

        t_min = np.ceil(max(x_times[0], y_times[0]))
        t_max = np.floor(min(x_times[-1], y_times[-1]))
        
        if y_2_value is not None:
            _, y_2_data = get_value_log(y_2_value, since=last + self.settings.y_2_phase, until=end + self.settings.y_2_phase)
            y_2_times = np.array([parser.parse(val[0]).timestamp() - self.settings.y_2_phase for val in y_2_data])
            y_2_value = np.array([val[1] for val in y_2_data])

            t_min = np.ceil(max(t_min, y_2_times[0]))
            t_max = np.floor(min(t_max, y_2_times[-1]))

        bins = np.arange(t_min, t_max, self.settings.time_bin)
        means_x, _, _ = scipy.stats.binned_statistic(x_times, x_value, bins=bins)
        means_y, _, _ = scipy.stats.binned_statistic(y_times, y_value, bins=bins)

        self.plots["y_value"] = [means_x, means_y, means_y, True, 0]

        if y_2_value is not None:
            means_y2,_ ,_ = scipy.stats.binned_statistic(y_2_times, y_2_value, bins=bins)
            self.plots["y_2_value"] = [means_x, means_y2, means_y2, True, 0]
        self.plot_widget._has_value = True


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
        self.pause_animation(self.settings.paused)
        self.set_plot_values()

    def make_plot(self):
        self.plot_widget.start()

    def post_figure(self):
        self.get_plot_layout().addWidget(addCrossHairs(self.plot_widget.plot_widget))

    def get_menus(self):
        _menu = Menu()

        # Add some options, the value is the function to run on click
        _menu._options["compare_plot"] = self.new_plotter

        _menu._opts_order.append("compare_plot")

        # Adds some help menu text for these as well
        _menu._helps["compare_plot"] = 'Starts a plotter for comparing values'

        # Adds labels for the non-separator values
        _menu._labels["compare_plot"] = "Comparison Plot"

        # Specify a label for the menu
        _menu._label = "Plots"

        # Returns an array of menus (only 1 in this case)
        return [_menu]