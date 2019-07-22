#!/usr/bin/env python3

import os
import sys
import time
import pickle
import shutil
import logging
import argparse
import numpy as np
from scipy import stats
from socketIO_client import SocketIO, BaseNamespace

import custom_script
from custom_script import EXP_NAME, OD_POWER, PUMP_CAL_FILE
from custom_script import EVOLVER_IP, EVOLVER_PORT, OPERATION_MODE
from custom_script import STIR_INITIAL, TEMP_INITIAL

# Should not be changed
# vials to be considered/excluded should be handled
# inside the custom functions
VIALS = [x for x in range(16)]

SAVE_PATH = os.path.dirname(os.path.realpath(__file__))
EXP_DIR = os.path.join(SAVE_PATH, EXP_NAME)

logger = logging.getLogger('eVOLVER')

EVOLVER_NS = None

class EvolverNamespace(BaseNamespace):
    start_time = None
    use_blank = False
    OD_initial = None

    def on_connect(self, *args):
        print("Connected to eVOLVER as client")
        logger.info('connected to eVOLVER as client')

    def on_disconnect(self, *args):
        print("Disconected from eVOLVER as client")
        logger.info('disconnected to eVOLVER as client')

    def on_reconnect(self, *args):
        print("Reconnected to eVOLVER as client")
        logger.info("reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        logger.debug('broadcast received')
        elapsed_time = round((time.time() - self.start_time) / 3600, 4)
        logger.debug('elapsed time: %.4f hours' % elapsed_time)
        print("{0}: {1} Hours".format(EXP_NAME, elapsed_time))
        # are the calibrations in yet?
        if not self.check_for_calibrations():
            logger.warning('calibration files still missing, skipping custom '
                           'functions')
            return

        # apply calibrations
        # update temperatures if needed
        data = self.transform_data(data, VIALS)
        if data is None:
            logger.error('could not tranform raw data, skipping user-'
                         'defined functions')
            return

        # should we "blank" the OD?
        if self.use_blank and self.OD_initial is None:
            logger.info('setting initial OD reading')
            self.OD_initial = data['transformed']['od_90']
        elif self.OD_initial is None:
            self.OD_initial = np.zeros(len(VIALS))
        data['transformed']['od_90'] = (data['transformed']['od_90'] -
                                        self.OD_initial)
        # save data
        self.save_data(data['transformed']['od_90'], elapsed_time,
                        VIALS, 'OD')
        self.save_data(data['transformed']['temp'], elapsed_time,
                        VIALS, 'temp')
        self.save_data(data['data'].get('od_90', []), elapsed_time,
                        VIALS, 'OD90_raw')
        self.save_data(data['data'].get('od_135', []), elapsed_time,
                        VIALS, 'OD135_raw')
        # run custom functions
        self.custom_functions(data, VIALS, elapsed_time)
        # save variables
        self.save_variables(self.start_time, self.OD_initial)

    def on_calibrationod(self, data):
        file_path = os.path.join(EXP_DIR, 'od_cal.txt')
        with open(file_path, 'w') as f:
            f.write(data)
        logger.debug("OD calibration: %s" % data)

    def on_calibrationtemp(self, data):
        file_path = os.path.join(EXP_DIR, 'temp_calibration.txt')
        with open(file_path , 'w') as f:
            f.write(data)
        logger.debug("temperature calibration: %s" % data)

    def request_od_calibration(self):
        logger.debug('requesting OD calibrations')
        self.emit('getcalibrationod',
                  {}, namespace = '/dpu-evolver')

    def request_temp_calibration(self):
        logger.debug('requesting temperature calibrations')
        self.emit('getcalibrationtemp',
                  {}, namespace = '/dpu-evolver')

    def transform_data(self, data, vials):
        odcal_path = os.path.join(EXP_DIR, 'od_cal.txt')
        od_cal = np.genfromtxt(odcal_path, delimiter=',')

        tempcal_path = os.path.join(EXP_DIR, 'temp_calibration.txt')
        temp_cal = np.genfromtxt(tempcal_path, delimiter=',')

        od_data = data['data'].get('od_90', None)
        temp_data = data['data'].get('temp', None)
        set_temp_data = data['config'].get('temp', {}).get('value', None)

        if od_data is None or temp_data is None or set_temp_data is None:
            print('Incomplete data recieved, Error with measurement')
            logger.error('Incomplete data received, error with measurements')
            return None
        if 'NaN' in od_data or 'NaN' in temp_data or 'NaN' in set_temp_data:
            print('NaN recieved, Error with measurement')
            logger.error('NaN received, error with measurements')
            return None

        od_data = np.array([float(x) for x in od_data])
        temp_data = np.array([float(x) for x in temp_data])
        set_temp_data = np.array([float(x) for x in set_temp_data])

        temps = []
        for x in vials:
            file_name =  "vial{0}_temp_config.txt".format(x)
            file_path = os.path.join(EXP_DIR, 'temp_config', file_name)
            temp_set_data = np.genfromtxt(file_path, delimiter=',')
            temp_set = temp_set_data[len(temp_set_data)-1][1]
            temps.append(temp_set)
            try:
                if (od_cal.shape[0] == 4):
                    #convert raw photodiode data into ODdata using calibration curve
                    od_data[x] = np.real(od_cal[2,x] -
                                        ((np.log10((od_cal[1,x] -
                                                    od_cal[0,x]) /
                                                    (float(od_data[x]) -
                                                    od_cal[0,x])-1)) /
                                                    od_cal[3,x]))
                    if not np.isfinite(od_data[x]):
                        od_data[x] = 'NaN'
                        logger.debug('OD from vial %d: %s' % (x, od_data[x]))
                    else:
                        logger.debug('OD from vial %d: %.3f' % (x, od_data[x]))
                else:
                    logger.error('OD calibration not formatted correctly')
                    od_data[x] = 'NaN'
            except ValueError:
                print("OD Read Error")
                logger.error('OD read error for vial %d, setting to NaN' % x)
                od_data[x] = 'NaN'
            try:
                temp_data[x] = (float(temp_data[x]) *
                                temp_cal[0][x]) + temp_cal[1][x]
                logger.debug('temperature from vial %d: %.3f' % (x, temp_data[x]))
            except ValueError:
                print("Temp Read Error")
                logger.error('temperature read error for vial %d, setting to NaN'
                            % x)
                temp_data[x]  = 'NaN'
            try:
                set_temp_data[x] = (float(set_temp_data[x]) *
                                    temp_cal[0][x]) + temp_cal[1][x]
                logger.debug('set_temperature from vial %d: %.3f' % (x,
                                                                set_temp_data[x]))
            except ValueError:
                print("Set Temp Read Error")
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
            raw_temperatures = [str(int((temps[x] - temp_cal[1][x]) /
                                        temp_cal[0][x]))
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
        data['transformed']['od_90'] = od_data
        data['transformed']['temp'] = temp_data
        return data

    def update_stir_rate(self, stir_rates):
        data = {'param': 'stir', 'value': stir_rates,
                'immediate': False, 'recurring': True}
        logger.debug('stir rate command: %s' % data)
        self.emit('command', data, namespace = '/dpu-evolver')

    def update_temperature(self, temperatures):
        data = {'param': 'temp', 'value': temperatures,
                'immediate': False, 'recurring': True}
        logger.debug('temperature command: %s' % data)
        self.emit('command', data, namespace = '/dpu-evolver')

    def fluid_command(self, MESSAGE):
        logger.debug('fluid command: %s' % MESSAGE)
        command = {'param': 'pump', 'value': MESSAGE,
                   'recurring': False ,'immediate': True}
        self.emit('command', command, namespace='/dpu-evolver')

    def update_chemo(self, data, vials, bolus_in_s, period_config):
        current_pump = data['config']['pump']['value']

        MESSAGE = {'fields_expected_incoming': 49,
                   'fields_expected_outgoing': 49,
                   'recurring': True,
                   'immediate': False,
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
        file_path = os.path.join(EXP_DIR, directory, file_name)
        text_file = open(file_path, "w")
        for default in defaults:
            text_file.write(default + '\n')
        text_file.close()

    def initialize_exp(self, vials, always_yes=False):
        logger.debug('initializing experiment')

        if os.path.exists(EXP_DIR):
            logger.info('found an existing experiment')
            exp_continue = None
            if always_yes:
                exp_continue = 'y'
            else:
                while exp_continue not in ['y', 'n']:
                    exp_continue = input('Continue from existing experiment? (y/n): ')
        else:
            exp_continue = 'n'

        if exp_continue == 'n':
            if os.path.exists(EXP_DIR):
                exp_overwrite = None
                if always_yes:
                    exp_overwrite = 'y'
                else:
                    while exp_overwrite not in ['y', 'n']:
                        exp_overwrite = input('Directory aleady exists. '
                                            'Overwrite with new experiment? (y/n): ')
                logger.info('data directory already exists')
                if exp_overwrite == 'y':
                    logger.info('deleting existing data directory')
                    shutil.rmtree(EXP_DIR)
                else:
                    print('Change experiment name in custom_script.py '
                        'and then restart...')
                    logger.warning('not deleting existing data directory, exiting')
                    sys.exit(1)

            start_time = time.time()

            self.request_od_calibration()
            self.request_temp_calibration()

            logger.debug('creating data directories')
            os.makedirs(os.path.join(EXP_DIR, 'OD'))
            os.makedirs(os.path.join(EXP_DIR, 'OD90_raw'))
            os.makedirs(os.path.join(EXP_DIR, 'OD135_raw'))
            os.makedirs(os.path.join(EXP_DIR, 'temp'))
            os.makedirs(os.path.join(EXP_DIR, 'temp_config'))
            os.makedirs(os.path.join(EXP_DIR, 'pump_log'))
            os.makedirs(os.path.join(EXP_DIR, 'ODset'))
            os.makedirs(os.path.join(EXP_DIR, 'growthrate'))
            os.makedirs(os.path.join(EXP_DIR, 'chemo_config'))
            for x in vials:
                exp_str = "Experiment: {0} vial {1}, {2}".format(EXP_NAME,
                                                                 x,
                                                           time.strftime("%c"))
                # make OD file
                self._create_file(x, 'OD', defaults=[exp_str])
                self._create_file(x, 'OD90_raw', defaults=[exp_str])
                self._create_file(x, 'OD135_raw', defaults=[exp_str])
                # make temperature data file
                self._create_file(x, 'temp')
                # make temperature configuration file
                self._create_file(x, 'temp_config',
                                  defaults=[exp_str,
                                            "0,{0}".format(TEMP_INITIAL[x])])
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

            self.update_stir_rate(STIR_INITIAL)

            if always_yes:
                exp_blank = 'y'
            else:
                exp_blank = input('Calibrate vials to blank? (y/n): ')
            if exp_blank == 'y':
                # will do it with first broadcast
                self.use_blank = True
                logger.info('will use initial OD measurement as blank')
            else:
                self.use_blank = False
                self.OD_initial = np.zeros(len(vials))
        else:
            # load existing experiment
            pickle_name =  "{0}.pickle".format(EXP_NAME)
            pickle_path = os.path.join(EXP_DIR, pickle_name)
            logger.info('loading previous experiment data: %s' % pickle_path)
            with open(pickle_path, 'rb') as f:
                loaded_var  = pickle.load(f)
            x = loaded_var
            start_time = x[0]
            self.OD_initial = x[1]

        # copy current custom script to txt file
        backup_filename = '{0}_{1}.txt'.format(EXP_NAME,
                                            time.strftime('%y%m%d_%H%M'))
        shutil.copy('custom_script.py', os.path.join(EXP_DIR,
                                                    backup_filename))
        logger.info('saved a copy of current custom_script.py as %s' %
                    backup_filename)

        return start_time

    def check_for_calibrations(self):
        result = True
        odcal_path = os.path.join(EXP_DIR, 'od_cal.txt')
        tempcal_path = os.path.join(EXP_DIR, 'temp_calibration.txt')
        if not os.path.exists(odcal_path):
            # log and request again
            logger.warning('OD calibrations not received yet, requesting again')
            self.request_od_calibration()
            result = False
        if not os.path.exists(tempcal_path):
            # log and request again
            logger.warning('temperature calibrations not received yet, '
                        'requesting again')
            self.request_temp_calibration()
            result = False
        return result

    def save_data(self, data, elapsed_time, vials, parameter):
        if len(data) == 0:
            return
        for x in vials:
            file_name =  "vial{0}_{1}.txt".format(x, parameter)
            file_path = os.path.join(EXP_DIR, parameter, file_name)
            text_file = open(file_path, "a+")
            text_file.write("{0},{1}\n".format(elapsed_time, data[x]))
            text_file.close()

    def save_variables(self, start_time, OD_initial):
        # save variables needed for restarting experiment later
        save_path = os.path.dirname(os.path.realpath(__file__))
        pickle_name = "{0}.pickle".format(EXP_NAME)
        pickle_path = os.path.join(EXP_DIR, pickle_name)
        logger.debug('saving all variables: %s' % pickle_path)
        with open(pickle_path, 'wb') as f:
            pickle.dump([start_time, OD_initial], f)

    def get_flow_rate(self):
        file_path = os.path.join(SAVE_PATH, PUMP_CAL_FILE)
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
        OD_path = os.path.join(EXP_DIR, 'OD', ODfile_name)
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
        gr_path = os.path.join(EXP_DIR, 'growthrate', file_name)
        text_file = open(gr_path, "a+")
        text_file.write("{0},{1}\n".format(elapsed_time, slope))
        text_file.close()

    def custom_functions(self, data, vials, elapsed_time):
        # load user script from custom_script.py
        if OPERATION_MODE == 'turbidostat':
            custom_script.turbidostat(self, data, vials, elapsed_time)
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
                print('Could not find function %s in custom_script.py '
                    '- Skipping user defined functions'%
                    OPERATION_MODE)

    def stop_exp(self):
        self.stop_all_pumps()

def get_options():
    description = 'Run an eVOLVER experiment from the command line'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--always-yes', action='store_true',
                        default=False,
                        help='Answer yes to all questions '
                             '(i.e. continues from existing experiment, '
                             'overwrites existing data and blanks OD '
                             'measurements)')
    parser.add_argument('--log-name',
                        default=os.path.join(EXP_DIR, 'evolver.log'),
                        help='Log file name directory (default: %(default)s)')

    log_nolog = parser.add_mutually_exclusive_group()
    log_nolog.add_argument('--verbose', action='count',
                           default=0,
                           help='Increase logging verbosity level to DEBUG '
                                '(default: INFO)')
    log_nolog.add_argument('--quiet', action='store_true',
                           default=False,
                           help='Disable logging to file entirely')

    return parser.parse_args()

if __name__ == '__main__':
    options = get_options()

    #changes terminal tab title in OSX
    print('\x1B]0;eVOLVER EXPERIMENT: PRESS Ctrl-C TO PAUSE\x07')

    # silence logging until experiment is initialized
    logging.level = logging.CRITICAL + 10

    socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
    EVOLVER_NS = socketIO.define(EvolverNamespace, '/dpu-evolver')

    # start by stopping any existing chemostat
    EVOLVER_NS.stop_all_pumps()
    #
    EVOLVER_NS.start_time = EVOLVER_NS.initialize_exp(VIALS,
                                                      options.always_yes)

    # logging setup
    if options.quiet:
        logging.basicConfig(level=logging.CRITICAL + 10)
    else:
        if options.verbose == 0:
            level = logging.INFO
        elif options.verbose >= 1:
            level = logging.DEBUG
        logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] '
                            '- %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            filename=options.log_name,
                            level=level)

    while True:
        try:
            # infinite loop
            socketIO.wait()
        except KeyboardInterrupt:
            try:
                print('Ctrl-C detected, pausing experiment')
                logger.warning('interrupt received, pausing experiment')
                EVOLVER_NS.stop_exp()
                while True:
                    key = input('Experiment paused. Press enter key to restart '
                                ' or hit Ctrl-C again to terminate experiment')
                    logger.warning('resuming experiment')
                    # no need to have something like "restart_chemo" here
                    # with the new server logic
                    break
            except KeyboardInterrupt:
                print('Second Ctrl-C detected, shutting down')
                logger.warning('second interrupt received, terminating '
                                'experiment')
                EVOLVER_NS.stop_exp()
                print('Experiment stopped, goodbye!')
                logger.warning('experiment stopped, goodbye!')
                break
        except Exception as e:
            logger.critical('exception %s stopped the experiment' % str(e))
            print('error "%s" stopped the experiment' % str(e))
            EVOLVER_NS.stop_exp()
            print('Experiment stopped, goodbye!')
            logger.warning('experiment stopped, goodbye!')
            break

    # stop experiment one last time
    # covers corner case where user presses Ctrl-C twice quickly
    EVOLVER_NS.stop_exp()
