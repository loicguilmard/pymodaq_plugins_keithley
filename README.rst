pymodaq_plugins_keithley (Keithley)
###################################

.. image:: https://img.shields.io/pypi/v/pymodaq_plugins_keithley.svg
   :target: https://pypi.org/project/pymodaq_plugins_physical_measurements/
   :alt: Latest Version

.. image:: https://readthedocs.org/projects/pymodaq/badge/?version=latest
   :target: https://pymodaq.readthedocs.io/en/stable/?badge=latest
   :alt: Documentation Status

.. image:: https://github.com/PyMoDAQ/pymodaq_plugins_keithley/workflows/Upload%20Python%20Package/badge.svg
    :target: https://github.com/PyMoDAQ/pymodaq_plugins_keithley

'Set of PyMoDAQ plugins for various physical measurements from keithley'


Authors
=======

* Sebastien J. Weber
* Sébastien Guerrero  (sebastien.guerrero@insa-lyon.fr)

Contributors
============

* Nicolas Bruyant
* Loïc Guilmard (loic.guilmard@insa-lyon.fr)
* Anthony Buthod (anthony.buthod@insa-lyon.fr)

Instruments
===========
Below is the list of instruments included in this plugin


Actuator
++++++++

* **Keithley2400**: Sourcemeter Keithley  2400 (using pymeasure intermediate package)

Viewer0D
++++++++

* **Keithley_Pico**: Pico-Amperemeter Keithley 648X Series, 6430 and 6514
* **Keithley2110**: Multimeter Keithley  2110
* **Keithley27XX**: Keithley 27XX Multimeter/Switch System using switching modules from the 7700

Usage instructions
==================

Starting with the Keithley 27XX, you need to setup the toml to describe your Keithley setup in the `config_keithley.toml` file.
There is a sample in the resources directory.

You need at least 3 parts :

* an instrument
* a module
* a channel

A tool is available `here<https://github.com/loicguilmard/Toml-Generator-for-PyMoDaq-Applications>` to generate a correct toml file.

Here is an example for a network keithley with a module 7706 with a termocouple type K on the first channel.

.. code-block:: toml

   [Keithley.27XX.INSTRUMENT01]
    title = "Instrument in wich is plugged the switching module used for data acquisition"
    #rsrc_name_example = [ "ASRL1::INSTR", "TCPIP::192.168.01.01::1394::SOCKET",]
    rsrc_name = "TCPIP::192.168.1.1::1394::SOCKET"
    model_name = "2701"
    panel = "rear"
    [Keithley.27XX.INSTRUMENT01.MODULE01]
    module_name = "7706"
    [Keithley.27XX.INSTRUMENT01.MODULE01.CHANNELS.101]
    mode = "temp"
    transducer = "tc"
    type = "K"
    ref_junc = "int"
    resolution = 6
    nplc = 5