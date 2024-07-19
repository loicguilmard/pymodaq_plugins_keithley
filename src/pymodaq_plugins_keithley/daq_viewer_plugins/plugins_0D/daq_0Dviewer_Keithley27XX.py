import numpy as np
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataFromPlugins, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.parameter import Parameter
from pymodaq_plugins_keithley import config
from pymodaq_plugins_keithley.hardware.keithley27XX.keithley27XX_VISADriver import Keithley27XXVISADriver as Keithley
from pymodaq.utils.logger import set_logger, get_module_name
logger = set_logger(get_module_name(__file__))


class DAQ_0DViewer_Keithley27XX(DAQ_Viewer_base):
    """ Keithley plugin class for a OD viewer.

    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the keithley27XX_VISADriver.

    :param controller: The particular object that allow the communication with the keithley27XX_VISADriver.
    :type  controller:  object

    :param params: Parameters displayed in the daq_viewer interface
    :type params: dictionary list
    """
    rsrc_name: str
    instr: str
    panel: str
    channels_in_selected_mode: str
    resources_list = []
    
    # Read configuration file
    for instr in config["Keithley", "27XX"].keys():
        if "INSTRUMENT" in instr:
            resources_list += [config["Keithley", "27XX", instr, "rsrc_name"]]
    logger.info("resources list = {}" .format(resources_list))

    params = comon_parameters + [
        {'title': 'Resources', 'name': 'resources', 'type': 'list', 'limits': resources_list,
         'value': resources_list[0]},
        {'title': 'Keithley', 'name': 'Keithley_Params', 'type': 'group', 'children': [
            {'title': 'Panel', 'name': 'panel', 'type': 'list', 'limits': ['select panel to use', 'FRONT', 'REAR'],
             'value': 'select panel to use'},
            {'title': 'ID', 'name': 'ID', 'type': 'text', 'value': ''},
            {'title': 'FRONT panel', 'name': 'frontpanel', 'visible': False, 'type': 'group', 'children': [
                {'title': 'Mode', 'name': 'frontmode', 'type': 'list',
                 'limits': ['VOLT:DC', 'VOLT:AC', 'CURR:DC', 'CURR:AC', 'RES', 'FRES', 'FREQ', 'TEMP'],
                 'value': 'VOLT:DC'},
            ]},
            {'title': 'REAR panel', 'name': 'rearpanel', 'visible': False, 'type': 'group', 'children': [
                {'title': 'Mode', 'name': 'rearmode', 'type': 'list',
                 'limits': ['SCAN_LIST', 'VOLT:DC', 'VOLT:AC', 'CURR:DC', 'CURR:AC', 'RES', 'FRES', 'FREQ', 'TEMP'],
                 'value': 'SCAN_LIST'}
            ]},
        ]},
    ]

    def __init__(self, parent=None, params_state=None):
        super().__init__(parent, params_state)

    def ini_attributes(self):
        """Attributes init when DAQ_0DViewer_Keithley class is instanced"""
        self.controller: Keithley = None
        self.channels_in_selected_mode = None
        self.rsrc_name = None
        self.panel = None
        self.instr = None

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings"""
        if param.name() == 'panel':
            for limit in ['REAR', 'FRONT']:
                if not limit == param.value():
                    if param.value() == 'select panel to use':
                        self.settings.child('Keithley_Params', 'frontpanel').show()
                        self.settings.child('Keithley_Params', 'rearpanel').show()
                    else:
                        self.settings.child('Keithley_Params', param.value().lower() + param.name()).show()
                        self.settings.child('Keithley_Params', limit.lower() + param.name()).hide()
        if 'mode' in param.name():
            """Updates the newly selected measurement mode"""
            # Read the configuration file to determine which mode to use and send corresponding instruction to driver
            if self.panel == 'FRONT':
                value = param.value()
                self.controller.set_mode(value)
            elif self.panel == 'REAR':
                value = 'SCAN_' + param.value()
                self.channels_in_selected_mode = self.controller.set_mode(value)
            current_error = self.controller.get_error()
            if current_error != '0,"No error"':
                logger.error("The following error has been raised by the Keithley:\
                        {} => Please refer to the User Manual to correct it\n\
                        Note: To make sure channels are well configured in the .toml file,\
                        refer to section 15 'SCPI Reference Tables', Table 15-5" .format(current_error))
        if 'CURR' in param.value():
            """Verify if the switching modules support current measurement"""
            if self.controller.non_amp_module["MODULE01"] and self.controller.non_amp_module["MODULE02"]:
                logger.info("Both modules don't support current measurement")
            if self.controller.non_amp_module["MODULE01"] and not self.controller.non_amp_module["MODULE02"]:
                logger.info("Both modules don't support current measurement")
            if self.controller.non_amp_module["MODULE02"] and not self.controller.non_amp_module["MODULE01"]:
                logger.info("Both modules don't support current measurement")

    def ini_detector(self, controller=None):
        """Detector communication initialization

        :param controller: Custom object of a PyMoDAQ plugin (Slave case). None if one actuator/detector by controller.
        :type controller: object

        :return: Initialization status, false if it failed otherwise True
        :rtype: bool
        """
        logger.info("Detector 0D initialized")

        if self.settings.child('controller_status').value() == "Slave":
            if controller is None:
                raise Exception('no controller has been defined externally while this detector is a slave one')
            else:
                self.controller = controller
        else:
            try:
                # Select the resource to connect with and load the dedicated configuration
                for instr in config["Keithley", "27XX"]:
                    if "INSTRUMENT" in instr:
                        if config["Keithley", "27XX", instr, "rsrc_name"] == self.settings["resources"]:
                            self.rsrc_name = config["Keithley", "27XX", instr, "rsrc_name"]
                            self.panel = config["Keithley", "27XX", instr, "panel"].upper()
                            self.instr = instr
                            logger.info("Panel configuration 0D_viewer: {}" .format(self.panel))
                assert self.rsrc_name is not None, "rsrc_name"
                assert self.panel is not None, "panel"
                self.controller = Keithley(self.rsrc_name)
            except AssertionError as err:
                logger.error("{}: {} did not match any configuration".format(type(err), str(err)))
            except Exception as e:
                raise Exception('No controller could be defined because an error occurred \
                while connecting to the instrument. Error: {}'.format(str(e)))

        # Keithley initialization & identification
        self.controller.init_hardware()
        txt = self.controller.get_idn()
        self.settings.child('Keithley_Params', 'ID').setValue(txt)

        # Initialize detector communication and set the default value (SCAN_LIST)
        if self.panel == 'FRONT':
            self.settings.child('Keithley_Params', 'rearpanel').visible = False
            value = self.settings.child('Keithley_Params', 'frontpanel', 'frontmode').value()
            self.controller.current_mode = value
            self.controller.set_mode(value)
        elif self.panel == 'REAR':
            self.settings.child('Keithley_Params', 'frontpanel').visible = False
            self.settings.child('Keithley_Params', 'frontpanel').value = 'REAR'
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

        :param Naverage: Number of hardware averaging (if hardware averaging is possible,
            self.hardware_averaging should be set to True in class preamble, and you should code this implementation)
        :type Naverage: int

        :param kwargs: others optionals arguments
        :type kwargs: dict
        """
        # ACQUISITION OF DATA
        if self.panel == 'FRONT':
            data_tot = self.controller.data()
            data_measurement = data_tot[1]
        elif self.panel == 'REAR':
            channels_in_selected_mode = self.channels_in_selected_mode[1:-1].replace('@', '')
            chan_to_plot = []
            data_tot = self.controller.data()
            data_measurement = data_tot[1]
            for i in range(len(channels_in_selected_mode.split(','))):
                chan_to_plot.append('Channel ' + str(channels_in_selected_mode.split(',')[i]))
            # Affect each value to the corresponding channel
            dict_chan_value = dict(zip(channels_in_selected_mode.split(','), data_measurement))
        # Dictionary linking channel's modes to physical quantities
        dict_label_mode = {'VOLT:DC': 'Voltage', 'VOLT:AC': 'Voltage', 'CURR:DC': 'Current', 'CURR:AC': 'Current',
                           'RES': 'Resistance', 'FRES': 'Resistance', 'FREQ': 'Frequency', 'TEMP': 'Temperature'}
        # EMISSION OF DATA
        # When reading the scan_list, data are displayed and exported grouped by mode
        if not self.controller.reading_scan_list:
            label = dict_label_mode[self.controller.current_mode]
            if self.panel == 'FRONT':
                labels = 'Front input'
            elif self.panel == 'REAR':
                labels = [chan_to_plot[i] for i in range(len(chan_to_plot))]
            dte = DataToExport(name='keithley',
                               data=[DataFromPlugins(name=label,
                                                     data=[np.array([data_measurement[i]]) for i in
                                                           range(len(data_measurement))],
                                                     dim='Data0D',
                                                     labels=labels)])

        # Reading only channels configured in the selected mode
        elif self.controller.reading_scan_list:
            dte = DataToExport(name='keithley',
                               data=[DataFromPlugins(name=dict_label_mode[key],
                                                     data=[np.array([dict_chan_value[str(chan)]]) for chan in
                                                           self.controller.modes_channels_dict.get(key)],
                                                     dim='Data0D',
                                                     labels=['Channel ' + str(chan) for chan in
                                                             self.controller.modes_channels_dict.get(key)]
                                                     ) for key in self.controller.modes_channels_dict.keys() if
                                     self.controller.modes_channels_dict.get(key) != []])
        self.dte_signal.emit(dte)

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        self.emit_status(ThreadCommand('Update_Status', ['Acquisition stopped']))
        return ''


if __name__ == '__main__':
    main(__file__)
