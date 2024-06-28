import os
import numpy as np
from easydict import EasyDict as edict
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataFromPlugins, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.parameter import Parameter
from pymodaq.utils.logger import set_logger, get_module_name
logger = set_logger(get_module_name(__file__))

import pymodaq_plugins_keithley as plugin
from pymodaq_plugins_keithley.hardware.keithley27XX.keithley27XX_VISADriver import Keithley27XXVISADriver as Keithley


class DAQ_0DViewer_Keithley27XX(DAQ_Viewer_base):
    """ Keithley plugin class for a OD viewer.

    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a the keithley 2700.

    * Keithley 27XX should be compatible with this plugin
    * Tested with Keithley Multimeter/Switch System 2700 - 2701
    * PyMoDAQ version = 4.0.11 during the test

    :param controller: The particular object that allow the communication with the hardware, in general a python wrapper around the hardware library.
    :type  controller:  object

    :param params: Parameters displayed in the daq_viewer interface
    :type params: dictionnary list

    :param x_axis: Daq_0Dviewer doesn't have axis, data acquired sample by sample
    :type x_axis: Nonetype
    """
    all_config = {}
    current_config = None
    resources_path = plugin.__path__[0] + "/resources"

    # Configurations for supported Keithley instruments
    toml_keithley = [f for f in os.listdir(resources_path) if "keithley.toml" in f]
    all_config["base"] = plugin.config_keithley

    # Configurations for supported Keithley switching modules
    toml_modules = [f for f in os.listdir(resources_path) if "module" in f and ".toml" in f]
    for file in toml_modules:
        exec("all_config[" + str(file[-9:-5]) + "] = plugin.config_k" + str(file[-9:-5]))
        if current_config == None:
            current_config = all_config.get(int(file[-9:-5]))

    # Read configuration file
    panel = all_config["base"]('INSTRUMENT').get('panel').upper()
    resources_list = [rsrc("INSTRUMENT").get("rsrc_name") for key, rsrc in list(all_config.items()) if key != "base"]
    logger.info("resources list = {}" .format(resources_list))

    if panel == 'FRONT':
        params = comon_parameters + [
            {'title': 'Resources', 'name': 'resources', 'type': 'list', 'limits': resources_list,
             'value': resources_list[0]},
            {'title': 'Keithley', 'name': 'Keithley_Params', 'type': 'group', 'children': [
                {'title': 'ID', 'name': 'ID', 'type': 'text', 'value': ''},
                {'title': 'FRONT panel', 'name': 'frontpanel', 'type': 'group', 'children': [
                    {'title': 'Mode', 'name': 'frontmode', 'type': 'list',
                     'limits': ['VOLT:DC', 'VOLT:AC', 'CURR:DC', 'CURR:AC', 'RES', 'FRES', 'FREQ', 'TEMP'],
                     'value': 'VOLT:DC'}]}
            ]}
        ]
    elif panel == 'REAR':
        params = comon_parameters + [
            {'title': 'Resources', 'name': 'resources', 'type': 'list', 'limits': resources_list,
             'value': resources_list[0]},
            {'title': 'Keithley', 'name': 'Keithley_Params', 'type': 'group', 'children': [
                {'title': 'ID', 'name': 'ID', 'type': 'text', 'value': ''},
                {'title': 'REAR panel', 'name': 'rearpanel', 'type': 'group', 'children': [
                    {'title': 'Mode', 'name': 'rearmode', 'type': 'list',
                     'limits': ['SCAN_LIST', 'VOLT:DC', 'VOLT:AC', 'CURR:DC', 'CURR:AC', 'RES', 'FRES', 'FREQ', 'TEMP'],
                     'value': 'SCAN_LIST'}
                ]}
            ]}
        ]

    def __init__(self, parent=None, params_state=None):
        super(DAQ_0DViewer_Keithley27XX, self).__init__(parent, params_state)

    def ini_attributes(self):
        """Attributes init when DAQ_0DViewer_Keithley class is instancied"""
        logger.info("Panel configuration 0D_viewer: " .format(self.panel))
        self.channels_in_selected_mode = None

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        :param Parameter: A given parameter (within detector_settings) whose value has been changed by the user
        """
        if 'mode' in param.name():
            """Updates the newly selected measurement mode"""
            # Read the configuration file to determine which mode to use and send corresponding instruction to driver
            if self.panel == 'FRONT':
                value = param.value()
                self.controller.set_mode(value)
            elif self.panel == 'REAR':
                value = 'SCAN_' + param.value()
                self.channels_in_selected_mode = self.controller.set_mode(value)

    def ini_detector(self, controller=None):
        """Detector communication initialization

        :param controller: Custom object of a PyMoDAQ plugin (Slave case). None if only one actuator/detector by controller (Master case)
        :type controller: object

        :return: Initialization status, false if it failed otherwise True
        :rtype: bool
        """
        logger.info("Detector 0D initialized")

        self.status.update(edict(initialized=False, info="", x_axis=None, y_axis=None, controller=None))
        if self.settings.child(('controller_status')).value() == "Slave":
            if controller is None:
                raise Exception('no controller has been defined externally while this detector is a slave one')
            else:
                self.controller = controller
        else:
            try:
                # Select the resource to connect with and load the dedicated configuration
                self.resource = self.settings["resources"]
                for config in self.all_config:
                    if self.all_config[config]("INSTRUMENT").get("rsrc_name") == self.settings["resources"]:
                        self.current_config = self.all_config[config]
                self.rsrc_name = self.current_config("INSTRUMENT").get("rsrc_name")
                self.channels = self.current_config('CHANNELS').keys()
                self.controller = Keithley(self.rsrc_name)
            except Exception as e:
                raise Exception('No controller could be defined because an error occurred\
                 while connecting to the instrument. Error: {}'.format(str(e)))

        # Remove current measurement from parameters when non-amps modules
        if Keithley(self.rsrc_name).non_amp_module == True:
            self.params[1]['children'][1]['children'][0]['limits'] = [i for i in
                                                                      self.params[1]['children'][1]['children'][0][
                                                                          'limits'] if
                                                                      not 'CURR:AC' in i and not 'CURR:DC' in i]

        # Keithley initialization & identification
        self.controller.init_hardware()
        txt = self.controller.get_idn()
        self.settings.child('Keithley_Params', 'ID').setValue(txt)

        # Initilize detector communication and set the default value (SCAN_LIST)
        if self.panel == 'FRONT':
            value = self.settings.child('Keithley_Params', 'frontpanel', 'frontmode').value()
            self.controller.current_mode = value
            self.controller.set_mode(value)
        elif self.panel == 'REAR':
            self.controller.configuration_sequence()
            value = 'SCAN_' + self.settings.child('Keithley_Params', 'rearpanel', 'rearmode').value()
            self.channels_in_selected_mode = self.controller.set_mode(value)
            logger.info("Channels to plot : {}" .format(self.channels_in_selected_mode))
        logger.info("DAQ_viewer command sent to keithley visa driver : {}" .format(value))

        self.status.initialized = True
        self.status.controller = self.controller

        return self.status

    def close(self):
        """Terminate the communication protocol"""
        self.controller.close()
        logger.info("communication ended successfully")

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        :param Naverage: Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        :type Naverage: int

        :param kwargs: others optionals arguments
        :type kwargs: dict
        """
        # ACQUISITION OF DATA
        if self.panel == 'FRONT':
            data_tot = self.controller.data()
            data_measurement = data_tot[1]
        elif self.panel == 'REAR':
            # print('current mode', self.controller.current_mode)
            channels_in_selected_mode = self.channels_in_selected_mode[1:-1].replace('@', '')
            Chan_to_plot = []
            data_tot = self.controller.data()
            data_measurement = data_tot[1]
            for i in range(len(channels_in_selected_mode.split(','))):
                Chan_to_plot.append('Channel ' + str(channels_in_selected_mode.split(',')[i]))
            # Affect each value to the corresponding channel
            dict_chan_value = dict(zip(channels_in_selected_mode.split(','), data_measurement))

            #     print('Chan :', Chan_to_plot)
            #     print('dict chan value : ', dict_chan_value)
            # print('Data tot :', data_tot)
            # print('Data measurement :', data_measurement)

        # Dictionary linking channel's modes to physical quantities
        dict_label_mode = {'VOLT:DC': 'Voltage', 'VOLT:AC': 'Voltage', 'CURR:DC': 'Current', 'CURR:AC': 'Current',
                           'RES': 'Resistance', 'FRES': 'Resistance', 'FREQ': 'Frequency', 'TEMP': 'Temperature'}

        # EMISSION OF DATA
        # When reading the scan_list, data are displayed and exported grouped by mode
        if self.controller.reading_scan_list == False:
            Label = dict_label_mode[self.controller.current_mode]
            if self.panel == 'FRONT':
                labels = 'Front input'
            elif self.panel == 'REAR':
                labels = [Chan_to_plot[i] for i in range(len(Chan_to_plot))]
            data = DataToExport(name='keithley',
                                data=[DataFromPlugins(name=Label,
                                                      data=[np.array([data_measurement[i]]) for i in
                                                            range(len(data_measurement))],
                                                      dim='Data0D',
                                                      labels=labels)])

        # Reading only channels configured in the selected mode
        elif self.controller.reading_scan_list == True:
            # print('\n***************** DEBUG IN ********************')
            # print('Modes + channels: ', self.controller.modes_channels_dict)
            # print(' Channels + value ', dict_chan_value)
            # for key in self.controller.modes_channels_dict.keys():
            #     if self.controller.modes_channels_dict.get(key) != []:
            #         print('key = ',key)
            #         for chan in self.controller.modes_channels_dict.get(key):
            #             print('chan = ', chan)
            #             print(' dict chan value[str(chan)]', dict_chan_value[str(chan)])
            # print('***************** DEBUG OUT ********************\n')

            data = DataToExport(name='keithley',
                                data=[DataFromPlugins(name=dict_label_mode[key],
                                                      data=[np.array([dict_chan_value[str(chan)]]) for chan in
                                                            self.controller.modes_channels_dict.get(key)],
                                                      dim='Data0D',
                                                      labels=['Channel ' + str(chan) for chan in
                                                              self.controller.modes_channels_dict.get(key)]
                                                      ) for key in self.controller.modes_channels_dict.keys() if
                                      self.controller.modes_channels_dict.get(key) != []])

        self.dte_signal.emit(data)

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        self.emit_status(ThreadCommand('Update_Status', ['Acquisition stoped']))
        return ''


if __name__ == '__main__':
    main(__file__)