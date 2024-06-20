# -*- coding: utf-8 -*-
"""
Created the 31/08/2023, updated the 19/06/2024

@author: Sebastien Weber, Sebastien Guerrero
"""
import os
from pathlib import Path
from pymodaq.utils.logger import set_logger
from pymodaq.utils.config import BaseConfig, USER
import pymodaq_plugins_keithley as plugin
logger = set_logger('plugin.utils', add_to_console=False)

class Config(BaseConfig):
    """Main class to deal with configuration values for this plugin"""
    config_template_path = Path(__file__).parent.joinpath('resources/config_template.toml')
    config_name = f"config_{__package__.split('pymodaq_plugins_')[1]}"

class Config_keithley(BaseConfig):
    """Main class to deal with configuration values for this plugin"""
    config_template_path = Path(__file__).parent.joinpath(f"resources/config_{__package__.split('pymodaq_plugins_')[1]}.toml")
    config_name = f"config_{__package__.split('pymodaq_plugins_')[1]}"

resources_path = plugin.__path__[0]+"/resources"
toml_modules = [f for f in os.listdir(resources_path) if "module" in f and ".toml" in f]
print("--- Modules conf files:",toml_modules)
logger.info("--- Modules conf files: {}" .format(toml_modules))

for file in toml_modules:
    class ConfigModule(BaseConfig):
        config_template_path = Path(__file__).parent.joinpath("resources/config_module" + str(file[-9:-5]) + ".toml")
        config_name = f"config_module" + str(file[-9:-5])

    exec("class Config_k" + str(file[-9:-5]) + "(ConfigModule): pass")