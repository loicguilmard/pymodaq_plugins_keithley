from collections import OrderedDict


from easydict import EasyDict as edict
import numpy as np
from pyvisa import ResourceManager
from qtpy.QtCore import Signal

from pymodaq.utils.daq_utils import ThreadCommand, getLineInfo
from pymodaq.utils.data import  DataFromPlugins, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, main, comon_parameters
from pymodaq.utils.enums import BaseEnum



VISA_rm = ResourceManager()
COM_PORTS = []
for name, rinfo in VISA_rm.list_resources_info().items():
    if rinfo.alias is not None:
        COM_PORTS.append(rinfo.alias)
    else:
        COM_PORTS.append(name)

class DAQ_0DViewer_Keithley_Pico_type(BaseEnum):
    """
        Enum class of Keithley_Pico_type

        =============== =========
        **Attributes**  **Type**
        *Pico_648X*     int
        *Pico_6430*     int
        *Pico_6514*     int
        =============== =========
    """
    Pico_648X = 0
    Pico_6430 = 1
    Pico_6514 = 2


class DAQ_0DViewer_Keithley_Pico(DAQ_Viewer_base):
    """
        ==================== ========================
        **Attributes**        **Type**
        *data_grabed_signal*  instance of Signal
        *VISA_rm*             ResourceManager
        *com_ports*           
        *params*              dictionnary list
        *keithley*
        *settings*
        ==================== ========================
    """
    data_grabed_signal = Signal(list)

    ##checking VISA ressources

#    import serial.tools.list_ports;
#    com_ports=[comport.device for comport in serial.tools.list_ports.comports()]

    params = comon_parameters + [
        {'title': 'VISA:', 'name': 'VISA_ressources', 'type': 'list', 'limits': COM_PORTS},
        {'title': 'Keithley Type:', 'name': 'keithley_type', 'type': 'list',
         'limits': DAQ_0DViewer_Keithley_Pico_type.names()},
        {'title': 'Id:', 'name': 'id', 'type': 'text', 'value': ""},
        {'title': 'Timeout (ms):', 'name': 'timeout', 'type': 'int', 'value': 10000, 'default': 10000, 'min': 2000},
        {'title': 'Configuration:', 'name': 'config', 'type': 'group', 'children': [
            {'title': 'Meas. type:', 'name': 'meas_type', 'type': 'list', 'value': 'CURR', 'default': 'CURR',
             'limits': ['CURR', 'VOLT', 'RES', 'CHAR']},

        ]},
    ]

    def ini_attributes(self):
        pass

    def ini_detector(self, controller=None):
        """
            Initialisation procedure of the detector.

            Returns
            -------

                The initialized status.

            See Also
            --------
            daq_utils.ThreadCommand
        """

        self.controller = self.ini_detector_init(old_controller=controller,
                                                 new_controller=
                                                 VISA_rm.open_resource(
                                                     self.settings['VISA_ressources'], read_termination='\r'))

        self.controller.timeout = self.settings['timeout']

        self.controller.write("*rst; status:preset; *cls;")
        txt = self.controller.query('*IDN?')
        self.settings.child(('id')).setValue(txt)
        self.controller.write('CONF:' + self.settings.child('config', 'meas_type').value())
        self.controller.write(':FORM:ELEM READ;DATA ASC;')
        self.controller.write('ARM:SOUR IMM;')
        self.controller.write('ARM:COUNt 1;')
        self.controller.write('TRIG:SOUR IMM;')
        # %%
        data = self.controller.query_ascii_values('READ?')

        self.status.initialized = True
        self.status.controller = self.controller
        return self.status


    def commit_settings(self, param):
        """
            Activate the parameters changes in the hardware.

            =============== ================================= ============================
            **Parameters**   **Type**                         **Description**
            *param*         instance of pyqtgraph.parameter   The parameter to be checked.
            =============== ================================= ============================

            See Also
            --------
            daq_utils.ThreadCommand
        """
        try:
            if param.name() == 'timeout':
                self.controller.timeout = self.settings.child(('timeout')).value()
            elif param.name() == 'meas_type':
                self.controller.write('CONF:' + param.value())


        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [getLineInfo() + str(e), 'log']))

    def close(self):
        """
            close the current instance of Keithley viewer.
        """
        if self.controller is not None:
            self.controller.close()

    def grab_data(self, Naverage=1, **kwargs):
        """
            | Start new acquisition.
            | grab the current values with keithley profile procedure.
            | Send the data_grabed_signal once done.

            =============== ======== ===============================================
            **Parameters**  **Type**  **Description**
            *Naverage*      int       Number of values to average
            =============== ======== ===============================================
        """
        data_tot = []
        self.controller.write('ARM:SOUR IMM;')
        self.controller.write('ARM:COUNt 1;')
        self.controller.write('TRIG:SOUR IMM;')
        self.controller.write('TRIG:COUN {:};'.format(Naverage))
        data_tot = self.controller.query_ascii_values('READ?')
        # for ind in range(Naverage):
        #    data_tot.append(self.controller.query_ascii_values('READ?')[0])
        dwa = DataFromPlugins(name='Keithley', data=[np.array([np.mean(np.array(data_tot))])])
        self.dte_signal.emit(DataToExport('Keithley', data=[dwa]))

    def stop(self):
        """
            not implemented?
        """
        return ""


if __name__ == '__main__':
    main(__file__, init=False)
