#!/usr/bin/env python3

import os
import sys
import time
import pickle
import shutil
import logging
import argparse
import numpy as np
import json
import traceback
import statistics
from scipy import stats
from socketIO_client import SocketIO, BaseNamespace
from git import Repo


import custom_script
from custom_script import PUMP_CAL_FILE
from custom_script import OPERATION_MODE

import nbstreamreader
from nbstreamreader import NonBlockingStreamReader as NBSR

# Should not be changed
# vials to be considered/excluded should be handled
# inside the custom functions
VIALS = [x for x in range(16)]

SIGMOID = 'sigmoid'
LINEAR = 'linear'
THREE_DIMENSION = '3d'

logger = logging.getLogger('eVOLVER')

EVOLVER_NS = None

class EvolverNamespace(BaseNamespace):
    #important file/directory paths
    savePath = None
    expDirectory = None
    OD_Cal_Path = None
    Temp_Cal_Path = None

    expName = None
    expContinue = None
    expInitial = None
    expOverwrite = None
    expZero = None
    expBlank = None
    expAlwaysYes = None

    start_time = None
    use_blank = False
    OD_initial = None

    pause = False
    tempWindow = [ [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []  ]
    spillCount = 0

    gitURL = None
    gitPath = None

    def on_connect(self, *args):
        #print("Connected to eVOLVER as client")
        logger.info('connected to eVOLVER as client')

    def on_disconnect(self, *args):
        #print("Disconected from eVOLVER as client")
        logger.info('disconnected to eVOLVER as client')

    def on_reconnect(self, *args):
        #print("Reconnected to eVOLVER as client")
        logger.info("reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        #if experiment is paused skip on_broadcast()
        if self.pause:
            return
        print("Broadcast received",flush=True)
        logger.debug('broadcast received')
        elapsed_time = round((time.time() - self.start_time) / 3600, 4)
        logger.debug('elapsed time: %.4f hours' % elapsed_time)
        # are the calibrations in yet?
        if not self.check_for_calibrations():
            logger.warning('calibration files still missing, skipping custom '
                           'functions')
            return

        with open(self.OD_Cal_Path) as f:
            od_cal = json.load(f)
        with open(self.Temp_Cal_Path) as f:
            temp_cal = json.load(f)

        # apply calibrations
        # update temperatures if needed
        data = self.transform_data(data, VIALS, od_cal, temp_cal)
        if data is None:
            logger.error('could not tranform raw data, skipping user-'
                         'defined functions')
            return

        # should we "blank" the OD?
        if self.use_blank and self.OD_initial is None:
            logger.info('setting initial OD reading')
            self.OD_initial = data['transformed']['od']
        elif self.OD_initial is None:
            self.OD_initial = np.zeros(len(VIALS))
        data['transformed']['od'] = (data['transformed']['od'] -
                                        self.OD_initial)
        # save data
        self.save_data(data['transformed']['od'], elapsed_time,
                        VIALS, 'OD')
        self.save_data(data['transformed']['temp'], elapsed_time,
                        VIALS, 'temp')

<<<<<<< HEAD
        # check for media spills
        self.spill_check(data['transformed']['temp'], VIALS)

=======
>>>>>>> f032767... Working on github integration
        for param in od_cal['params']:
            self.save_data(data['data'].get(param, []), elapsed_time,
                        VIALS, param + '_raw')
        for param in temp_cal['params']:
            self.save_data(data['data'].get(param, []), elapsed_time,
                        VIALS, param + '_raw')

        # run custom functions
        self.custom_functions(data, VIALS, elapsed_time)
        # save variables
        self.save_variables(self.start_time, self.OD_initial)

<<<<<<< HEAD

=======
>>>>>>> f032767... Working on github integration
    def on_activecalibrations(self, data):
        #print('Calibrations recieved',flush=True)
        for calibration in data:
            if calibration['calibrationType'] == 'od':
                file_path = self.OD_Cal_Path
            elif calibration['calibrationType'] == 'temperature':
                file_path = self.Temp_Cal_Path
            else:
                continue
            for fit in calibration['fits']:
                if fit['active']:
                    with open(file_path, 'w') as f:
                        json.dump(fit, f)
                    # Create raw data directories and files for params needed
                    for param in fit['params']:
                        if not os.path.isdir(os.path.join(self.expDirectory, param + '_raw')):
                            os.makedirs(os.path.join(self.expDirectory, param + '_raw'))
                            for x in range(len(fit['coefficients'])):
                                exp_str = "Experiment: {0} vial {1}, {2}".format(self.expName,
                                        x,
                                        time.strftime("%c"))
                                self._create_file(x, param + '_raw', defaults=[exp_str])
                    break

    def request_calibrations(self):
        logger.debug('requesting active calibrations')
        self.emit('getactivecal',
                  {}, namespace = '/dpu-evolver')

    def transform_data(self, data, vials, od_cal, temp_cal):
        od_data_2 = None
        if od_cal['type'] == THREE_DIMENSION:
            od_data_2 = data['data'].get(od_cal['params'][1], None)

        od_data = data['data'].get(od_cal['params'][0], None)
        temp_data = data['data'].get(temp_cal['params'][0], None)
        set_temp_data = data['config'].get('temp', {}).get('value', None)

        if od_data is None or temp_data is None or set_temp_data is None:
            #print('Incomplete data recieved, Error with measurement')
            logger.error('Incomplete data received, error with measurements')
            return None
        if 'NaN' in od_data or 'NaN' in temp_data or 'NaN' in set_temp_data:
            #print('NaN recieved, Error with measurement')
            logger.error('NaN received, error with measurements')
            return None

        od_data = np.array([float(x) for x in od_data])
        if od_data_2:
            od_data_2 = np.array([float(x) for x in od_data_2])
        temp_data = np.array([float(x) for x in temp_data])
        set_temp_data = np.array([float(x) for x in set_temp_data])

        temps = []
        for x in vials:
            file_name =  "vial{0}_temp_config.txt".format(x)
            file_path = os.path.join(self.expDirectory, 'temp_config', file_name)
            temp_set_data = np.genfromtxt(file_path, delimiter=',')
            temp_set = temp_set_data[len(temp_set_data)-1][1]
            temps.append(temp_set)
            od_coefficients = od_cal['coefficients'][x]
            temp_coefficients = temp_cal['coefficients'][x]
            try:
                if od_cal['type'] == SIGMOID:
                    #convert raw photodiode data into ODdata using calibration curve
                    od_data[x] = np.real(od_coefficients[2] -
                                        ((np.log10((od_coefficients[1] -
                                                    od_coefficients[0]) /
                                                    (float(od_data[x]) -
                                                    od_coefficients[0])-1)) /
                                                    od_coefficients[3]))
                    if not np.isfinite(od_data[x]):
                        od_data[x] = 'NaN'
                        logger.debug('OD from vial %d: %s' % (x, od_data[x]))
                    else:
                        logger.debug('OD from vial %d: %.3f' % (x, od_data[x]))
                elif od_cal['type'] == THREE_DIMENSION:
                    od_data[x] = np.real(od_coefficients[0] +
                                        (od_coefficients[1]*od_data[x]) +
                                        (od_coefficients[2]*od_data_2[x]) +
                                        (od_coefficients[3]*(od_data[x]**2)) +
                                        (od_coefficients[4]*od_data[x]*od_data_2[x]) +
                                        (od_coefficients[5]*(od_data_2[x]**2)))
                else:
                    logger.error('OD calibration not of supported type!')
                    od_data[x] = 'NaN'
            except ValueError:
                #print("OD Read Error")
                logger.error('OD read error for vial %d, setting to NaN' % x)
                od_data[x] = 'NaN'
            try:
                temp_data[x] = (float(temp_data[x]) *
                                temp_coefficients[0]) + temp_coefficients[1]
                logger.debug('temperature from vial %d: %.3f' % (x, temp_data[x]))
            except ValueError:
                #print("Temp Read Error")
                logger.error('temperature read error for vial %d, setting to NaN'
                            % x)
                temp_data[x]  = 'NaN'
            try:
                set_temp_data[x] = (float(set_temp_data[x]) *
                                    temp_coefficients[0]) + temp_coefficients[1]
                logger.debug('set_temperature from vial %d: %.3f' % (x,
                                                                set_temp_data[x]))
            except ValueError:
                #print("Set Temp Read Error")
                logger.error('set temperature read error for vial %d, setting to NaN'
                            % x)
                set_temp_data[x]  = 'NaN'

        temps = np.array(temps)
        # update temperatures only if difference with expected
        # value is above 0.2 degrees celsius
        delta_t = np.abs(set_temp_data - temps).max()
        if delta_t > 0.2:
            logger.info('updating temperatures (max. deltaT is %.2f)' %
                        delta_t)
            coefficients = temp_cal['coefficients']
            raw_temperatures = [str(int((temps[x] - temp_cal['coefficients'][x][1]) /
                                        temp_cal['coefficients'][x][0]))
                                for x in vials]
            self.update_temperature(raw_temperatures)
        else:
            # config from server agrees with local config
            # report if actual temperature doesn't match
            delta_t = np.abs(temps - temp_data).max()
            if delta_t > 0.2:
                logger.info('actual temperature doesn\'t match configuration '
                            '(yet? max deltaT is %.2f)' % delta_t)
                logger.debug('temperature config: %s' % temps)
                logger.debug('actual temperatures: %s' % temp_data)

        # add a new field in the data dictionary
        data['transformed'] = {}
        data['transformed']['od'] = od_data
        data['transformed']['temp'] = temp_data
        return data

    def update_stir_rate(self, stir_rates, immediate = False):
        data = {'param': 'stir', 'value': stir_rates,
                'immediate': immediate, 'recurring': True}
        logger.debug('stir rate command: %s' % data)
        self.emit('command', data, namespace = '/dpu-evolver')

    def update_temperature(self, temperatures, immediate = False):
        data = {'param': 'temp', 'value': temperatures,
                'immediate': immediate, 'recurring': True}
        logger.debug('temperature command: %s' % data)
        self.emit('command', data, namespace = '/dpu-evolver')

    def fluid_command(self, MESSAGE):
        logger.debug('fluid command: %s' % MESSAGE)
        command = {'param': 'pump', 'value': MESSAGE,
                   'recurring': False ,'immediate': True}
        self.emit('command', command, namespace='/dpu-evolver')

    def update_chemo(self, data, vials, bolus_in_s, period_config, immediate = False):
        current_pump = data['config']['pump']['value']

        MESSAGE = {'fields_expected_incoming': 49,
                   'fields_expected_outgoing': 49,
                   'recurring': True,
                   'immediate': immediate,
                   'value': ['--'] * 48,
                   'param': 'pump'}

        for x in vials:
            # stop pumps if period is zero
            if period_config[x] == 0:
                # influx
                MESSAGE['value'][x] = '0|0'
                # efflux
                MESSAGE['value'][x + 16] = '0|0'
            else:
                # influx
                MESSAGE['value'][x] = '%.2f|%d' % (bolus_in_s[x], period_config[x])
                # efflux
                MESSAGE['value'][x + 16] = '%.2f|%d' % (bolus_in_s[x] * 2,
                                                        period_config[x])

        if MESSAGE['value'] != current_pump:
            logger.info('updating chemostat: %s' % MESSAGE)
            self.emit('command', MESSAGE, namespace = '/dpu-evolver')

    def stop_all_pumps(self, ):
        data = {'param': 'pump',
                'value': ['0'] * 48,
                'recurring': False,
                'immediate': True}
        logger.info('stopping all pumps')
        self.emit('command', data, namespace = '/dpu-evolver')

    def _create_file(self, vial, param, directory=None, defaults=None):
        if defaults is None:
            defaults = []
        if directory is None:
            directory = param
        file_name =  "vial{0}_{1}.txt".format(vial, param)
        file_path = os.path.join(self.expDirectory, directory, file_name)
        text_file = open(file_path, "w")
        for default in defaults:
            text_file.write(default + '\n')
        text_file.close()

    def initialize_exp(self, vials):
        logger.debug('initializing experiment')

        #check to see if there is already an existing experiment
        if os.path.exists(self.expDirectory):
            logger.info('found an existing experiment')
            if self.expAlwaysYes:
                self.expContinue = 'y'

        if self.expContinue == 'n':
            if os.path.exists(self.expDirectory):
                if self.expAlwaysYes:
                    self.expOverwrite = 'y'
                logger.info('data directory already exists')
                if self.expOverwrite == 'y':
                    logger.info('deleting existing data directory')
                    #shutil.rmtree(self.expDirectory)
                else:
                    #print('Change experiment name in custom_script.py '
                        #'and then restart...')
                    logger.warning('not deleting existing data directory, exiting')
                    sys.exit(1)
            start_time = time.time()
            self.request_calibrations()

            self.createRepo()
            logger.debug('creating data directories')
            os.makedirs(os.path.join(self.expDirectory, 'OD'))
            os.makedirs(os.path.join(self.expDirectory, 'temp'))
            os.makedirs(os.path.join(self.expDirectory, 'temp_config'))
            os.makedirs(os.path.join(self.expDirectory, 'pump_log'))
            os.makedirs(os.path.join(self.expDirectory, 'ODset'))
            os.makedirs(os.path.join(self.expDirectory, 'growthrate'))
            os.makedirs(os.path.join(self.expDirectory, 'chemo_config'))
            for x in vials:
                exp_str = "Experiment: {0} vial {1}, {2}".format(self.expName,
                                                                 x,
                                                           time.strftime("%c"))
                # make OD file
                self._create_file(x, 'OD', defaults=[exp_str])
                # make temperature data file
                self._create_file(x, 'temp')
                # make temperature configuration file
                self._create_file(x, 'temp_config',
                                  defaults=[exp_str,
                                            "0,{0}".format(self.expInitial['temp_input'][x])])
                # make pump log file
                self._create_file(x, 'pump_log',
                                  defaults=[exp_str,
                                            "0,0"])
                # make ODset file
                self._create_file(x, 'ODset',
                                  defaults=[exp_str,
                                            "0,0"])
                # make growth rate file
                self._create_file(x, 'gr',
                                  defaults=[exp_str,
                                            "0,0"],
                                  directory='growthrate')
                # make chemostat file
                self._create_file(x, 'chemo_config',
                                  defaults=["0,0,0",
                                            "0,0,0"],
                                  directory='chemo_config')
            self.update_stir_rate(self.expInitial['stir_input'])
            if self.expAlwaysYes:
                self.expBlank = 'y'
            #else:
                #expBlank = input('Calibrate vials to blank? (y/n): ')
            if self.expBlank == 'y':
                # will do it with first broadcast
                self.use_blank = True
                logger.info('will use initial OD measurement as blank')
            else:
                self.use_blank = False
                self.OD_initial = np.zeros(len(vials))
        else:
            # load existing experiment
            pickle_name =  "{0}.pickle".format(self.expName)
            pickle_path = os.path.join(self.expDirectory, pickle_name)
            logger.info('loading previous experiment data: %s' % pickle_path)
            with open(pickle_path, 'rb') as f:
                loaded_var  = pickle.load(f)
            x = loaded_var
            start_time = x[0]
            self.OD_initial = x[1]
        # copy current custom script to txt file
        backup_filename = '{0}_{1}.txt'.format(self.expName,
                                            time.strftime('%y%m%d_%H%M'))
        shutil.copy('/Users/ezirayimerwolle/Library/Application Support/Electron/legacy/data/ezira_test/custom_script.py', os.path.join(self.expDirectory,
                                                    backup_filename))
        logger.info('saved a copy of current custom_script.py as %s' %
                    backup_filename)
        #print('End',flush=True)
        return start_time

    def check_for_calibrations(self):
        result = True
        if not os.path.exists(self.OD_Cal_Path) or not os.path.exists(self.Temp_Cal_Path):
            # log and request again
            logger.warning('Calibrations not received yet, requesting again')
            self.request_calibrations()
            result = False
        return result

    def save_data(self, data, elapsed_time, vials, parameter):
        if len(data) == 0:
            return
        for x in vials:
            file_name =  "vial{0}_{1}.txt".format(x, parameter)
            file_path = os.path.join(self.expDirectory, parameter, file_name)
            text_file = open(file_path, "a+")
            text_file.write("{0},{1}\n".format(elapsed_time, data[x]))
            text_file.close()

    def save_variables(self, start_time, OD_initial):
        print("Saving variables",flush=True)
        # save variables needed for restarting experiment later
        save_path = os.path.dirname(os.path.realpath(__file__))
        pickle_name = "{0}.pickle".format(self.expName)
        pickle_path = os.path.join(self.expDirectory, pickle_name)
        logger.debug('saving all variables: %s' % pickle_path)
        with open(pickle_path, 'wb') as f:
            pickle.dump([start_time, OD_initial], f)

    def get_flow_rate(self):
        file_path = os.path.join(self.savePath, PUMP_CAL_FILE)
        flow_calibration = np.loadtxt(file_path, delimiter="\t")
        if len(flow_calibration) == 16:
            flow_rate = flow_calibration
        else:
            # Currently just implementing influx flow rate
            flow_rate = flow_calibration[0,:]
        return flow_rate

    def calc_growth_rate(self, vial, gr_start, elapsed_time):
        ODfile_name =  "vial{0}_OD.txt".format(vial)
        # Grab Data and make setpoint
        OD_path = os.path.join(self.expDirectory, 'OD', ODfile_name)
        OD_data = np.genfromtxt(OD_path, delimiter=',')
        raw_time = OD_data[:, 0]
        raw_OD = OD_data[:, 1]
        raw_time = raw_time[np.isfinite(raw_OD)]
        raw_OD = raw_OD[np.isfinite(raw_OD)]

        # Trim points prior to gr_start
        trim_time = raw_time[np.nonzero(np.where(raw_time > gr_start, 1, 0))]
        trim_OD = raw_OD[np.nonzero(np.where(raw_time > gr_start, 1, 0))]

        # Take natural log, calculate slope
        log_OD = np.log(trim_OD)
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            trim_time[np.isfinite(log_OD)],
            log_OD[np.isfinite(log_OD)])
        logger.debug('growth rate for vial %s: %.2f' % (vial, slope))

        # Save slope to file
        file_name =  "vial{0}_gr.txt".format(vial)
        gr_path = os.path.join(self.expDirectory, 'growthrate', file_name)
        text_file = open(gr_path, "a+")
        text_file.write("{0},{1}\n".format(elapsed_time, slope))
        text_file.close()

    def custom_functions(self, data, vials, elapsed_time):
        print('In custom',flush=True)
        # load user script from custom_script.py
        if OPERATION_MODE == 'turbidostat':
            custom_script.turbidostat(self, data, vials, elapsed_time,self.expInitial['lower_thresh'],self.expInitial['upper_thresh'],self.expInitial['volume'])
        elif OPERATION_MODE == 'chemostat':
            custom_script.chemostat(self, data, vials, elapsed_time)
        else:
            # try to load the user function
            # if failing report to user
            logger.info('user-defined operation mode %s' % OPERATION_MODE)
            try:
                func = getattr(custom_script, OPERATION_MODE)
                func(self, data, vials, elapsed_time)
            except AttributeError:
                logger.error('could not find function %s in custom_script.py' %
                            OPERATION_MODE)
                #print('Could not find function %s in custom_script.py '
                    #'- Skipping user defined functions'%
                    #OPERATION_MODE)

    def stop_exp(self):
        self.stop_all_pumps()

    def spill_detection(self, data, vials):
        for x in vials:
            newData = float(data[x])
            size = len(self.tempWindow)
            #add to window till it reaches proper window size
            if (size < self.windowSize):
                self.tempWindow.append(newData)
            if (size == 10):
                #calculate moving average and z-score for new data point
                avg = sum(self.tempWindow) / len(self.tempWindow)
                std = stdev(self.tempWindow)
                diff = abs((abs(newData) - avg))
                z_score = diff / std
                if (z_score > 10 and std >= 0.04 and diff > 2):
                    logger.warn('Large temperature deviation detected in vial %f' % vials[x])
                    print('slack:Lage temperature deviation detected in vial:', vials[x], flush=True)
                    self.spillCount += 1
                else:
                    self.tempWindow.append(newData)
                    self.tempWindow.pop(0)
                if (self.spillCount == 3):
                    logger.warn('Potential spill detected in vial %f' % vials[x])
                    print('slack:Potential spill detected in vial: ', vials[x], flush=True)
                    self.pause = True
                    return True
    def createRepo(self):
        gitConfigPath = os.path.join(self.savePath, 'GitHubConfig.json')

        with open(gitConfigPath) as f:
            gitConfig = json.load(f)
            self.gitURL = gitConfig['remoteURL']
            self.gitPath = gitConfig['localPath']
        print(self.gitPath,flush=True)
        try:
            origin = Repo(self.gitPath)
            print(origin.git.status(),flush=True)
        except:
            empty_repo = git.Repo.init(os.path.join(self.gitPath))
            origin = empty_repo.create_remote('origin', self.gitURL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-z","--zero")
    parser.add_argument("-c","--continues")
    parser.add_argument("-o","--overwrite")
    parser.add_argument("-p","--parameters")
    parser.add_argument("-i","--evolverIP")
    parser.add_argument("-t","--evolverPort")
    parser.add_argument("-n","--name")
    parser.add_argument("-b","--blank")

    parser.add_argument('--always_yes', action='store_true',
                        default=False,
                        help='Answer yes to all questions '
                            '(i.e. continues from existing experiment, '
                            'overwrites existing data and blanks OD '
                            'measurements)')
    parser.add_argument('--log_name',
                        help='Log file name directory (default: %(default)s)')
    log_nolog = parser.add_mutually_exclusive_group()
    log_nolog.add_argument('--verbose', action='count',
                           default=0,
                           help='Increase logging verbosity level to DEBUG '
                                '(default: INFO)')
    log_nolog.add_argument('--quiet', action='store_true',
                           default=False,
                           help='Disable logging to file entirely')
    args = parser.parse_args()

    #assign variables values
    evolverIP = args.evolverIP
    evolverPort = args.evolverPort

    #changes terminal tab title in OSX
    #print('\x1B]0;eVOLVER EXPERIMENT: PRESS Ctrl-C TO PAUSE\x07',flush=True)

    # silence logging until experiment is initialized
    #logging.level = logging.CRITICAL + 10

    socketIO = SocketIO(evolverIP, evolverPort)
    EVOLVER_NS = socketIO.define(EvolverNamespace, '/dpu-evolver')

    #store user input information from application
    EVOLVER_NS.expName = args.name
    EVOLVER_NS.expContinue = args.continues
    EVOLVER_NS.expInitial = json.loads(args.parameters)
    EVOLVER_NS.expOverwrite = args.overwrite
    EVOLVER_NS.expZero = args.zero
    EVOLVER_NS.expBlank = args.blank
    EVOLVER_NS.expAlwaysYes = args.always_yes

    EVOLVER_NS.savePath = os.path.dirname(os.path.realpath(__file__))
    EVOLVER_NS.expDirectory = EVOLVER_NS.savePath
    EVOLVER_NS.OD_Cal_Path = os.path.join(EVOLVER_NS.savePath, 'od_cal.json')
    EVOLVER_NS.Temp_Cal_Path = os.path.join(EVOLVER_NS.savePath, 'temp_cal.json')

    # start by stopping any existing chemostat
    EVOLVER_NS.stop_all_pumps()
    EVOLVER_NS.start_time = EVOLVER_NS.initialize_exp(VIALS)
    # logging setup
    if args.log_name:
        log_name = args.log_name
    else:
        log_name = os.path.join(EVOLVER_NS.expDirectory, 'evolver.log')

    if args.quiet:
        logging.basicConfig(level=logging.CRITICAL + 10)
    else:
        if args.verbose == 0:
            level = logging.INFO
        elif args.verbose >= 1:
            level = logging.DEBUG
        logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] '
                            '- %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            filename=log_name,
                            level=level)

    reset_connection_timer = time.time()

    #instanitate NonBlockingStreamReader to read user input values from electron app
    nbsr = NBSR(sys.stdin)
    while True:
        time.sleep(2)
        socketIO.wait(seconds=0.1)
        if time.time() - reset_connection_timer > 3600:
            # reset connection to avoid buildup of broadcast
            # messages (unlikely but could happen for very long
            # experiments with slow dpu code/computer)
            logger.info('resetting connection to eVOLVER to avoid '
                        'potential buildup of broadcast messages')
            socketIO.disconnect()
            socketIO.connect()
            reset_connection_timer = time.time()
        # infinite loop
        message = nbsr.readline()
        if 'pause-script' in message:
            print('Pausing expt', flush=True)
            logger.warning('interrupt received, pausing experiment')
            EVOLVER_NS.stop_exp()
            socketIO.disconnect()
            EVOLVER_NS.pause = True
        if 'continue-script' in message:
            print('Restarting expt', flush=True)
            logger.info('resuming experiment')
            socketIO.connect()
            EVOLVER_NS.pause = False
