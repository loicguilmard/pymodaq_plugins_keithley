import os
from pathlib import Path
from pymodaq.utils.logger import set_logger
import pymodaq_plugins_keithley as plugin
import pymodaq_plugins_keithley.utils as utils
logger = set_logger('plugin.__init__', add_to_console=False)

from pymodaq_plugins_keithley.utils import Config_keithley
config = utils.Config()
config_keithley = utils.Config_keithley()

resources_path = plugin.__path__[0]+"/resources"
toml_modules = [f for f in os.listdir(resources_path) if "module" in f and ".toml" in f]
for file in toml_modules:
    exec("config_k" + str(file[-9:-5]) + " = " + "utils.Config_k" + str(file[-9:-5]) + "()")

with open(str(Path(__file__).parent.joinpath('resources/VERSION')), 'r') as fvers:
    __version__ = fvers.read().strip()