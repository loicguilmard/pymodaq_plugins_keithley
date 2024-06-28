import os
import numpy as np
import pyvisa as visa
import pymodaq_plugins_keithley as plugin
from pymodaq.utils.logger import set_logger, get_module_name
logger = set_logger(get_module_name(__file__))

class Keithley27XXVISADriver:
    """VISA class driver for the Keithley 27XX Multimeter/Switch System

    This class relies on pyvisa module to communicate with the instrument via VISA protocol.
    Please refer to the instrument reference manual available at:
    https://download.tek.com/manual/2700-900-01K_Feb_2016.pdf
    https://download.tek.com/manual/2701-900-01G_Feb_2016.pdf
    """
    all_config = {}
    resources_path = plugin.__path__[0]+"/resources"

    # Configurations for supported Keithley instruments
    toml_keithley = [f for f in os.listdir(resources_path) if "keithley.toml" in f]
    all_config["base"] = plugin.config_keithley

    # Configurations for supported Keithley switching modules
    toml_modules = [f for f in os.listdir(resources_path) if "module" in f and ".toml" in f]
    for file in toml_modules:
        exec("all_config[" + str(file[-9:-5]) + "] = plugin.config_k" + str(file[-9:-5]))
        logger.info("*** config rsrcname {}: {}" .format(str(file[-9:-5]), all_config.get(int(file[-9:-5]))('INSTRUMENT').get('rsrc_name')))
    
    K_config = None

    # Non-amps modules
    non_amp_module = False
    non_amp_modules_list = [7701,7703,7706,7707,7708,7709]

    # Channels & modes attributes
    channels_scanlist = ''
    modes_channels_dict = {'VOLT:DC':[],'VOLT:AC':[],'CURR:DC':[],'CURR:AC':[],'RES':[],'FRES':[],'FREQ':[],'TEMP':[]}
    sample_count_1 = False
    reading_scan_list = False
    current_mode = ''

    def __init__(self, rsrc_name):
        """Initialize KeithleyVISADriver class

        :param rsrc_name: VISA Resource name
        :type rsrc_name: string
        """
        self.rsrc_name = rsrc_name

    def init_hardware(self, pyvisa_backend='@ivi'):
        """Initialize the selected VISA resource
        
        :param pyvisa_backend: Expects a pyvisa backend identifier or a path to the visa backend dll (ref. to pyvisa)
        :type pyvisa_backend: string
        """
        logger.info("Hardware initialized")

        # Open connexion with instrument
        rm = visa.highlevel.ResourceManager(pyvisa_backend)
        self._instr = rm.open_resource(self.rsrc_name,
                                       write_termination = "\n",
                                       read_termination = "\n"
                                       )
        self._instr.timeout = 10000

        # Check configuration
        model = int(self.get_idn()[32:36])
        card = int(self.get_card().split(',')[0])
        if not "27" in str(model):
            logger.info("Keithley instrument {} model is not supported" .format(model))
        elif not card in self.all_config.keys():
            logger.info("Switching module {} is not supported" .format(card))
            logger.info("config_module1111 loaded")
            self.K_config = self.all_config.get(1111)
        else:
            self.K_config = self.all_config.get(card)

        logger.info("K_config : {}" .format(self.K_config))

        if self.K_config('MODULE','module_name') in self.non_amp_modules_list:
            self.non_amp_module = True

    def configuration_sequence(self):
        """Configure each channel selected by the user

        Read the configuration file to get the channels used and their configuration, and send the keithley a sequence allowing to set up each channel.
        
        :raises TypeError: Channel section of configuration file not correctly defined, each channel should be a dictionary
        :raises ValueError: Channel not correctly defined, it should at least contain a key called "mode"
        """
        logger.info("\n********** CONFIGURATION SEQUENCE INITIALIZED **********")
        logger.info("Acquisition card = {}" .format(self.K_config('MODULE', 'module_name')))

        self.reset()
        self.clear_buffer()
        channels = ''

        # The following loop set up each channel in the config file
        for key in self.K_config('CHANNELS').keys():

            # Handling user mistakes if the channels configuration section is not correctly set up
            if not type(self.K_config('CHANNELS',key))==dict:
                logger.info("Channel {} not correctly defined, must be a dictionary" .format(key))
                continue
            if not self.K_config('CHANNELS',key):
                continue
            if not "mode" in self.K_config('CHANNELS',key):
                logger.info("Channel {} not fully defined, 'mode' is missing" .format(key))
                continue
            if self.K_config('CHANNELS',key).get('mode').upper() not in self.modes_channels_dict.keys():
                logger.info("Channel {} not correctly defined, mode not recognized" .format(key))
                continue

            # Channel mode
            mode = self.K_config('CHANNELS',key).get('mode').upper()
            self.modes_channels_dict[mode].append(int(key))
            channel = '(@' + key + ')'
            channels += key + ","
            cmd = "FUNC '" + mode + "'," + channel
            self._instr.write(cmd)

            # Config
            if 'range' in self.K_config('CHANNELS',key).keys():
                range = self.K_config('CHANNELS',key).get('range')
                if 'autorange' in str(range):
                    self._instr.write(mode + ':RANG:AUTO ')
                else:
                    self._instr.write(mode + ':RANG ' + str(range))
                    
            if 'resolution' in self.K_config('CHANNELS',key).keys():
                resolution = self.K_config('CHANNELS',key).get('resolution')
                self._instr.write(mode + ':DIG ' + str(resolution))

            if 'nplc' in self.K_config('CHANNELS',key).keys():
                nplc = self.K_config('CHANNELS',key).get('nplc')
                self._instr.write(mode + ':NPLC ' + str(nplc))

            if "TEMP" in mode:
                transducer = self.K_config('CHANNELS',key).get('transducer').upper()
                if "TC" in transducer:
                    tc_type = self.K_config('CHANNELS',key).get('type').upper()
                    ref_junction = self.K_config('CHANNELS',key).get('ref_junction').upper()
                    self.mode_temp_tc(channel,transducer,tc_type,ref_junction)
                elif "THER":
                    ther_type = self.K_config('CHANNELS',key).get('type').upper()
                    self.mode_temp_ther(channel,transducer,ther_type)
                elif "FRTD":
                    frtd_type = self.K_config('CHANNELS',key).get('type').upper()
                    self.mode_temp_frtd(channel,transducer,frtd_type)

            # Console info
            logger.info("Channels {} \n {}".format(key,self.K_config('CHANNELS',key)))
            # Timeout update for long measurement modes such as voltage AC
            if "AC" in mode:
                self._instr.timeout += 4000

            # Handling errors from Keithley
            current_error = self.get_error()
            try:
                if current_error != '0,"No error"':
                    raise ValueError("The following error has been raised by the Keithley: %s => Pease refer to the User Manual to correct it\n\
                                     Note: To make sure channels are well configured in the .toml file, refer to section 15 'SCPI Reference Tables', Table 15-5" % current_error)
            except Exception as err:
                logger.info("{}".format(err))
                pass
        
        self.current_mode = 'scan_list'
        self.channels_scanlist =  channels[:-1]
        logger.info("********** CONFIGURATION SEQUENCE SUCCESSFULLY ENDED **********")

    def clear_buffer(self):
        # Default: auto clear when scan start
        self._instr.write("TRAC:CLE")

    def clear_buffer_off(self):
        # Disable buffer auto clear
        self._instr.write("TRAC:CLE:AUTO OFF")

    def clear_buffer_on(self):
        # Disable buffer auto clear
        self._instr.write("TRAC:CLE:AUTO ON")

    def close(self):
        self._instr.write("ROUT:OPEN:ALL")
        self._instr.close()

    def data(self):
        """Get data from instrument

        Make the Keithley perfom 3 actions: init, trigger, fetch. Then process the answer to return 3 variables:
        - The answer (string)
        - The measurement values (numpy array)
        - The timestamp of each measurement (numpy array)
        """
        if self.sample_count_1 == False:
            # Initiate scan
            self._instr.write("INIT")
            # Trigger scan
            self._instr.write("*TRG")
            # Get data (equivalent to TRAC:DATA? from buffer)
            str_answer = self._instr.query("FETCH?")
        else:
            str_answer = self._instr.query("FETCH?")
        # Split the instrument answer (MEASUREMENT,TIME,READING COUNT) to create a list
        list_split_answer = str_answer.split(",")

        # MEASUREMENT & TIME EXTRACTION
        list_measurements = list_split_answer[::3]
        str_measurements = ''
        list_times = list_split_answer[1::3]
        str_times = ''
        for j in range(len(list_measurements)):
            if not j==0:
                str_measurements += ','
                str_times += ','
            for l in range(len(list_measurements[j])):
                test_carac = list_measurements[j][-(l+1)]
                # Remove non-digit characters (units)
                if test_carac.isdigit() == True:
                    if l==0:   
                        str_measurements += list_measurements[j]
                    else:
                        str_measurements += list_measurements[j][:-l]
                    break
            for l in range(len(list_times[j])):
                test_carac = list_times[j][-(l+1)]
                # Remove non-digit characters (units)
                if test_carac.isdigit() == True:
                    if l==0:   
                        str_times += list_times[j]
                    else:
                        str_times += list_times[j][:-l]
                    break

        # Split created string to access each value
        list_measurements_values = str_measurements.split(",")
        list_times_values = str_times.split(",")
        # Create numpy.array containing desired values (float type)
        array_measurements_values = np.array(list_measurements_values,dtype=float)
        if self.sample_count_1 != True:
            array_times_values = np.array(list_times_values,dtype=float)
        else:
            array_times_values = np.array([0],dtype=float)

        return str_answer,array_measurements_values,array_times_values

    def define_input(self, input):
        return str(input)
    
    def get_card(self):
        # Query switching module
        return self._instr.query("*OPT?")
    
    def get_error(self):
        # Ask the keithley to return the last current error
        return self._instr.query("SYST:ERR?")
    
    def get_idn(self):
        # Query identification
        return self._instr.query("*IDN?")
    
    def initcontoff(self):
        # Disable continuous initiation
        self._instr.write("INIT:CONT OFF")
        
    def initconton(self):
        # Enable continuous initiation
        self._instr.write("INIT:CONT ON")

    def mode_temp_frtd(self,channel,transducer,frtd_type,):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:FRTD:TYPE " + frtd_type + "," + channel)

    def mode_temp_tc(self,channel,transducer,tc_type,ref_junction):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:TC:TYPE " + tc_type + "," + channel)
        self._instr.write("TEMP:RJUN:RSEL " + ref_junction + "," + channel)

    def mode_temp_ther(self,channel,transducer,ther_type,):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:THER:TYPE " + ther_type + "," + channel)
    
    def reset(self):
        # Clear measurement event register
        self._instr.write("*CLS")
        # One-shot measurement mode (Equivalent to INIT:COUNT OFF)
        self._instr.write("*RST")

    def set_mode(self, mode):
        """Define whether the Keithley will scan all the scanlist or only channels in the selected mode

        :param mode: Measurement configuration ('SCAN_LIST', 'VDC', 'VAC', 'IDC', 'IAC', 'R2W', 'R4W', 'FREQ' and 'TEMP' modes are supported)
        :type mode: string
        """
        mode = mode.upper()
        
        # FRONT panel
        if "SCAN" not in mode:
            self.initconton()
            self.sample_count_1 = True
            self.reading_scan_list = False
            self._instr.write("FUNC '" + mode + "'")

        # REAR panel
        else:
            self.clear_buffer()
            # Init contiuous disabled
            self.initcontoff()
            mode = mode[5:]
            self.current_mode = mode
            if 'SCAN_LIST' in mode:
                self.reading_scan_list = True
                self.sample_count_1 = False
                channels = '(@' + self.channels_scanlist + ')'
                # Set to perform 1 to INF scan(s)
                self._instr.write("TRIG:COUN 1")
                # Trigger immediately after previous scan end if IMM
                self._instr.write("TRIG:SOUR BUS")
                # Set to scan <n> channels
                samp_count = 1 + channels.count(',')
                self._instr.write("SAMP:COUN "+str(samp_count))
                # Disable scan if currently enabled
                self._instr.write("ROUT:SCAN:LSEL NONE")
                # Set scan list channels
                self._instr.write("ROUT:SCAN " + channels)
                # Start scan immediately when enabled and triggered
                self._instr.write("ROUT:SCAN:TSO IMM")
                # Enable scan
                self._instr.write("ROUT:SCAN:LSEL INT")


            else:
                self.reading_scan_list = False
                # Select channels in the channels list (config file) matching the requested mode
                channels = '(@' + str(self.modes_channels_dict.get(mode))[1:-1] + ')'
                # Set to perform 1 to INF scan(s)
                self._instr.write("TRIG:COUN 1")
                # Set to scan <n> channels
                samp_count = 1+channels.count(',')
                self._instr.write("SAMP:COUN "+str(samp_count))
                if samp_count == 1:
                    self.initconton()
                    # Trigger definition
                    self._instr.write("TRIG:SOUR IMM")
                    # Disable scan if currently enabled
                    self._instr.write("ROUT:SCAN:LSEL NONE")
                    self._instr.write("ROUT:CLOS " + channels)
                    
                    self._instr.write("FUNC '" + mode + "'")
                    logger.info("rear sample count: {}".format(self.sample_count_1))
                    if self.sample_count_1 != True:
                        self.sample_count_1 = True
                    self.reading_scan_list = False
                else:
                    self.sample_count_1 = False
                    # Trigger definition
                    self._instr.write("TRIG:SOUR BUS")
                    # Disable scan if currently enabled
                    self._instr.write("ROUT:SCAN:LSEL NONE")
                    # Set scan list channels
                    self._instr.write("ROUT:SCAN " + channels)
                    # Start scan immediately when enabled and triggered
                    self._instr.write("ROUT:SCAN:TSO IMM")
                    # Enable scan
                    self._instr.write("ROUT:SCAN:LSEL INT")
                
            return(channels)
        
    def stop_acquisition(self):
        # If scan in process, stop it
        self._instr.write("ROUT:SCAN:LSEL NONE")

    def user_command(self):
        command = input('Enter here a command you want to send directly to the Keithley [if None, press enter]: ')
        if command != '':
            if command[-1] == "?":
                print(self._instr.query(command))
            else:
                self._instr.write(command)
            command = self.user_command()

if __name__ == "__main__":
    try:
        print("In main")
        
        rm = visa.ResourceManager("@ivi")
        print("list resources",rm.list_resources())

        # K2701 Instance of KeithleyVISADriver class
        k2701 = Keithley27XXVISADriver("TCPIP::192.168.40.41::1394::SOCKET")
        k2701.init_hardware()

        print("IDN?")
        print(k2701.get_idn())

        k2701.close()

        # K2700 Instance of KeithleyVISADriver class
        k2700 = Keithley27XXVISADriver("ASRL3::INSTR")
        k2700.init_hardware()

        print("IDN?")
        print(k2700.get_idn())
        
        # k2700.reset()
        # k2700.configuration_sequence()

        # # Daq_viewer simulation first run
        # k2700.set_mode(str(input('Enter which mode you want to scan [scan_scan_list, scan_volt:dc, scan_r2w, scan_temp...]:')))
        # print('Manual scan example: >init >*trg >trac:data?')
        # k2700.user_command()

        # for i in range(2):
        #     print(k2700.data())
        # print(k2700.data())

        # # Daq_viewer simulation change mode
        # k2700.user_command()
        # k2700.set_mode(str(input('Enter which mode you want to scan [scan_scan_list, scan_volt:dc, scan_r2w, scan_temp...]:')))
        # print('Manual scan example: >init >*trg >trac:data?')

        # for i in range(2):
        #     print(k2700.data())
        # print(k2700.data())

        # k2700.clear_buffer()
        k2700.close()

        print("Out")

    except Exception as e:
        print("Exception ({}): {}".format(type(e), str(e)))
