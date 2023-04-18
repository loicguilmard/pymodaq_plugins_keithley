from easydict import EasyDict as edict
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.adapters import VISAAdapter, PrologixAdapter

from pymodaq.control_modules.move_utility_classes import DAQ_Move_base  # base class
from pymodaq.control_modules.move_utility_classes import comon_parameters, main  # common set of parameters for all actuators
from pymodaq.utils.daq_utils import ThreadCommand, getLineInfo
from pymodaq.utils.logger import set_logger, get_module_name  # object used to send info back to the main thread
from pymodaq.utils.parameter.utils import iter_children
from pyvisa import ResourceManager


logger = set_logger(get_module_name(__file__))

rm = ResourceManager()

VISA_RESSOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)
SOURCE_MODES = ['Current', 'Voltage']
EPSILON_CURRENT = 1e-5
EPSILON_VOLTAGE = 1e-3


class DAQ_Move_Keithley2400(DAQ_Move_base):
    """
        Wrapper object to access the Mock fonctionnalities, similar wrapper for all controllers.

        =============== ==============
        **Attributes**    **Type**
        *params*          dictionnary
        =============== ==============
    """
    _controller_units = 'A'
    is_multiaxes = False  # set to True if this plugin is controlled for a multiaxis controller (with a unique communication link)
    stage_names = []  # "list of strings of the multiaxes
    _epsilon = 1e-5

    params = [   {'title': 'Adapter:', 'name': 'adapter', 'type': 'list', 'limits': list(ADAPTERS.keys())},
                 {'title': 'VISA Ressources:', 'name': 'visa_ressource', 'type': 'list', 'limits': VISA_RESSOURCES},
                 {'title': 'Info:', 'name': 'info', 'type': 'str', 'value': '', 'readonly': True},
                 {'title': 'Source Mode:', 'name': 'source_mode', 'type': 'list', 'limits': SOURCE_MODES},
                 {'title': 'Enabled:', 'name': 'enabled', 'type': 'led_push', 'value': False},
                 {'title': 'Current Mode:', 'name': 'current_mode', 'type': 'group', 'children': [
                     {'title': 'Current Range:', 'name': 'current_range', 'type': 'float', 'value': 10e-3, 'min': 0.},
                     {'title': 'Compliance Voltage:', 'name': 'voltage_compliance', 'type': 'float',
                      'value': 10, 'min': 0.}]},
                 {'title': 'Voltage Mode:', 'name': 'voltage_mode', 'type': 'group', 'visible': True, 'children': [
                     {'title': 'Voltage Range:', 'name': 'voltage_range', 'type': 'float', 'value': 10, 'min': 0.,
                      'max': 210.},
                     {'title': 'Compliance Current:', 'name': 'current_compliance', 'type': 'float',
                      'value': 5e-1, 'min': 0.}]},

                 {'title': 'MultiAxes:', 'name': 'multiaxes', 'type': 'group', 'visible': is_multiaxes, 'children': [
                     {'title': 'is Multiaxes:', 'name': 'ismultiaxes', 'type': 'bool', 'value': is_multiaxes,
                      'default': False},
                     {'title': 'Status:', 'name': 'multi_status', 'type': 'list', 'value': 'Master',
                      'limits': ['Master', 'Slave']},
                     {'title': 'Axis:', 'name': 'axis', 'type': 'list', 'limits': stage_names},

                 ]}] + comon_parameters

    def __init__(self, parent=None, params_state=None):
        """
            Initialize the the class

            ============== ================================================ ==========================================================================================
            **Parameters**  **Type**                                         **Description**

            *parent*        Caller object of this plugin                    see DAQ_Move_main.DAQ_Move_stage
            *params_state*  list of dicts                                   saved state of the plugins parameters list
            ============== ================================================ ==========================================================================================

        """

        super().__init__(parent, params_state)
        self._enabled = False

    def check_position(self):
        """Get the current position from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        # if self.enabled:
        #     if self.settings.child('source_mode').value() == 'Current':
        #         self.controller.measure_current()
        #         pos = self.controller.current
        #     else:
        #         self.controller.measure_voltage()
        #         pos = self.controller.voltage
        #     if isinstance(pos, list):
        #         logger.debug(f"Got multiple return values for {self.settings.child('source_mode').value()}"
        #                      f": {pos}")
        #         pos = pos[0]
        # else:
        #     pos = 0.
        pos = self.current_position  # bypass checking
        pos = self.get_position_with_scaling(pos)

        self.emit_status(ThreadCommand('check_position', [pos]))
        return pos

    def close(self):
        """
        Terminate the communication protocol
        """
        self.controller.shutdown()

    @property
    def enabled(self):
        return self._enabled

    def enable_source(self, enable=True):
        self._enabled = enable
        if enable:
            self.controller.enable_source()
        else:
            self.controller.disable_source()
        self.settings.child('enabled').setValue(enable)

    def set_source(self, source_mode='Current', range=None, compliance=None):
        if source_mode == 'Current':
            if compliance is None:
                compliance = 0.1
            self.controller.apply_current(current_range=range, compliance_voltage=compliance)
            self.settings.child('epsilon').setValue(EPSILON_CURRENT)
        else:
            if compliance is None:
                compliance = 10
            self.controller.apply_voltage(voltage_range=range, compliance_current=compliance)
            self.settings.child('epsilon').setValue(EPSILON_VOLTAGE)
    def get_range_compliance(self):
        if self.settings.child('source_mode').value() == 'Current':
            range = self.settings.child('current_mode', 'current_range').value()
            compliance = self.settings.child('current_mode', 'voltage_compliance').value()
        else:
            range = self.settings.child('voltage_mode', 'voltage_range').value()
            compliance = self.settings.child('voltage_mode', 'current_compliance').value()
        return range, compliance

    def commit_settings(self, param):
        if param.name() == "source_mode" or \
            param.name() in iter_children(self.settings.child('current_mode'), []) or \
                param.name() in iter_children(self.settings.child('voltage_mode'), []):

            if self.enabled:  # if was enabled, disabled it
                self.enable_source(False)
            self.set_source(param.value(), *self.get_range_compliance())
            if param.name() == "source_mode":
                self.settings.child('current_mode').show(param.value() == 'Current')
                self.settings.child('voltage_mode').show(param.value() != 'Current')
                if param.value() == 'Current':
                    self.controller.source_current = 0
                    self.controller.measure_voltage()
                else:
                    self.controller.source_voltage = 0.
                    self.controller.measure_current()

        elif param.name() == 'enabled':
            self.enable_source(param.value())

    def ini_stage(self, controller=None):
        """Actuator communication initialization

        Parameters
        ----------
        controller: (object) custom object of a PyMoDAQ plugin (Slave case). None if only one actuator by controller (Master case)

        Returns
        -------
        self.status (edict): with initialization status: three fields:
            * info (str)
            * controller (object) initialized controller
            *initialized: (bool): False if initialization failed otherwise True
        """
        try:
            # initialize the stage and its controller status
            # controller is an object that may be passed to other instances of DAQ_Move_Mock in case
            # of one controller controlling multiactuators (or detector)

            self.status.update(edict(info="", controller=None, initialized=False))

            # check whether this stage is controlled by a multiaxe controller (to be defined for each plugin)
            # if multiaxes then init the controller here if Master state otherwise use external controller
            if self.settings.child('multiaxes', 'ismultiaxes').value() and self.settings.child('multiaxes',
                                   'multi_status').value() == "Slave":
                if controller is None:
                    raise Exception('no controller has been defined externally while this axe is a slave one')
                else:
                    self.controller = controller
            else:  # Master stage

                adapter = \
                    ADAPTERS[self.settings.child('adapter').value()](self.settings.child('visa_ressource').value())
                self.controller = Keithley2400(adapter)  # when writing your own plugin replace this line
                self.commit_settings(self.settings.child('source_mode'))

                #####################################

            self.status.info = self.controller.id
            self.settings.child('info').setValue(self.status.info)
            self.status.controller = self.controller
            self.status.initialized = True
            return self.status

        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [getLineInfo() + str(e), 'log']))
            self.status.info = getLineInfo() + str(e)
            self.status.initialized = False
            return self.status

    def move_Abs(self, position):
        """ Move the actuator to the absolute target defined by position

        Parameters
        ----------
        position: (flaot) value of the absolute target positioning
        """

        position = self.check_bound(position)  #if user checked bounds, the defined bounds are applied here
        position = self.set_position_with_scaling(position)  # apply scaling if the user specified one
        if self.settings.child('source_mode').value() == 'Current':
            self.controller.source_current = position
        else:
            self.controller.source_voltage = position

        if self.enabled:
            if self.settings.child('source_mode').value() == 'Current':
                self.controller.measure_voltage()
                pos = self.controller.voltage
            else:
                self.controller.measure_current()
                pos = self.controller.current


        self.target_position = position
        self.current_position = self.target_position #bypass checking

    def move_Rel(self, position):
        """ Move the actuator to the relative target actuator value defined by position

        Parameters
        ----------
        position: (flaot) value of the relative target positioning
        """
        position = self.check_bound(self.current_position+position)-self.current_position
        self.target_position = position + self.current_position
        self.move_Abs(self.target_position)
        ##############################

    def move_Home(self):
        """
          Send the update status thread command.
            See Also
            --------
            daq_utils.ThreadCommand
        """

        self.move_Abs(0)

    def stop_motion(self):
        """
        Call the specific move_done function (depending on the hardware).

        See Also
        --------
        move_done
        """
        self.move_done()  # to let the interface know the actuator stopped


if __name__ == '__main__':
    main(__file__, init=False)
