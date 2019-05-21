#!/usr/bin/env python

import socket
import os.path
import logging
import shutil
import time
import pickle
import numpy as np
from scipy import stats
from socketIO_client import SocketIO, BaseNamespace
from threading import Thread
import asyncio
from custom_script import EXP_NAME, OD_POWER, PUMP_CAL_FILE
from custom_script import EVOLVER_IP, EVOLVER_PORT, OPERATION_MODE
from custom_script import STIR_INITIAL, TEMP_INITIAL

# logger set up
logger = logging.getLogger(__name__)

dpu_evolver_ns = None
received_data = {}
od_cal = None
temp_cal = None

save_path = os.path.dirname(os.path.realpath(__file__))
shared_name = None
shared_ip = None
shared_port = None

# TODO: use proper async/await
wait_for_data = True
control = np.power(2, range(0,32))
current_chemo = [0] * 16
current_temps = [0] * 16
connected = False

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        global connected, current_temps
        print("Connected to eVOLVER as client")
        logger.info('connected to eVOLVER as client')
        connected = True

    def on_disconnect(self, *args):
        global connected
        print("Disconected from eVOLVER as client")
        logger.info('disconnected to eVOLVER as client')
        connected = False

    def on_reconnect(self, *args):
        global connected, stop_waiting, current_temps
        current_temps = [0] * 16
        print("Reconnected to eVOLVER as client")
        logger.info("reconnected to eVOLVER as client")
        connected = True
        stop_waiting = True

    def on_dataresponse(self, data):
        #print(data)
        global received_data, wait_for_data
        received_data = data
        wait_for_data = False
        logger.debug("data response: %s" % data)

    def on_calibrationod(self, data):
        global od_cal, save_path, shared_name
        file_path = os.path.join(save_path,shared_name,'od_cal.txt')
        with open(file_path, 'w') as f:
            f.write(data)
        od_cal = True
        logger.debug("OD calibration: %s" % data)

    def on_calibrationtemp(self, data):
        global temp_cal, save_path, shared_name
        file_path = os.path.join(save_path,shared_name,'temp_calibration.txt')
        with open(file_path , 'w') as f:
            f.write(data)
        temp_cal = True
        logger.debug("temperature calibration: %s" % data)

def read_data(vials):
    global wait_for_data, received_data, current_temps, connected
    global stop_waiting, shared_ip, shared_port

    save_path = os.path.dirname(os.path.realpath(__file__))

    odcal_path = os.path.join(save_path, EXP_NAME, 'od_cal.txt')
    od_cal = np.genfromtxt(odcal_path, delimiter=',')

    tempcal_path = os.path.join(save_path, EXP_NAME, 'temp_calibration.txt')
    temp_cal = np.genfromtxt(tempcal_path, delimiter=',')

    wait_for_data = True
    stop_waiting = False
    logger.debug('requesting data from eVOLVER')
    dpu_evolver_ns.emit('data', {'config':{'od':[OD_POWER] * 16,
                                           'temp':['NaN'] * 16}},
                        namespace='/dpu-evolver')
    start_time = time.time()
    # print('Fetching data from eVOLVER')
    while(wait_for_data):
        if not connected or stop_waiting or (time.time() - start_time > 30):
            wait_for_data = False
            print('Issue with eVOLVER communication - '
                  'skipping data acquisition')
            logger.warning('issue with eVOLVER communication, skipping data '
                           'acquisition')
            return None, None
        pass


    od_data = received_data['od']
    temp_data = received_data['temp']
    if 'NaN' in od_data or 'NaN' in temp_data:
        print('NaN recieved, Error with measurement')
        logger.error('NaN received, error with measurements')
        return None, None
    temps = []
    for x in vials:
        file_name =  "vial{0}_tempconfig.txt".format(x)
        file_path = os.path.join(save_path, EXP_NAME, 'temp_config', file_name)
        temp_set_data = np.genfromtxt(file_path, delimiter=',')
        temp_set = temp_set_data[len(temp_set_data)-1][1]
        #convert raw thermistor data into temp using calibration fit
        temp_set = int((temp_set - temp_cal[1][x])/temp_cal[0][x])
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
                logger.debug('OD from vial %d: %.3f' % (x, od_data[x]))
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
    if not temps == current_temps:
        logger.debug('updating temperatures to %s' % list(temps))
        MESSAGE = list(temps)
        command = {'param':'temp', 'message':MESSAGE}
        dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')
        current_temps = temps

    return od_data, temp_data

def fluid_command(MESSAGE, vial, elapsed_time, pump_wait, exp_name, time_on,
                  file_write):
    logger.debug('fluid command: %s' % MESSAGE)
    command = {'param': 'pump', 'message': MESSAGE}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')

    save_path = os.path.dirname(os.path.realpath(__file__))

    file_name =  "vial{0}_pump_log.txt".format(vial)
    file_path = os.path.join(save_path, EXP_NAME, 'pump_log', file_name)

    if file_write == 'y':
        text_file = open(file_path,"a+")
        text_file.write("{0},{1}\n".format(elapsed_time, time_on))
        text_file.close()

def update_chemo(vials, bolus_in_s):
    global current_chemo

    save_path = os.path.dirname(os.path.realpath(__file__))
    MESSAGE = {}
    for x in vials:
        file_name =  "vial{0}_chemoconfig.txt".format(x)
        file_path = os.path.join(save_path, EXP_NAME, 'chemo_config',
                                 file_name)

        data = np.genfromtxt(file_path, delimiter=',')
        chemo_set = data[len(data)-1][2]
        if not chemo_set == current_chemo[x]:
            current_chemo[x] = chemo_set
            MESSAGE = {'pumps_binary':"{0:b}".format(control[x]),
                       'pump_time': bolus_in_s[x],
                       'efflux_pump_time': bolus_in_s[x] * 2,
                       'delay_interval': chemo_set,
                       'times_to_repeat': -1, 'run_efflux': 1}
            logger.debug('updating chemostat for pump %d: %s' % (x, MESSAGE))
            command = {'param': 'pump', 'message': MESSAGE}
            dpu_evolver_ns.emit('command', command, namespace = '/dpu-evolver')

def stir_rate (MESSAGE):
    command = {'param':'stir', 'message':MESSAGE}
    logger.debug('stir rate command: %s' % MESSAGE)
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')

def get_flow_rate():
    file_path = os.path.join(save_path, PUMP_CAL_FILE)
    flow_calibration = np.loadtxt(file_path, delimiter="\t")
    if len(flow_calibration) == 16:
        flow_rate = flow_calibration
    else:
        # Currently just implementing influx flow rate
        flow_rate = flow_calibration[0,:]
    return flow_rate

def calc_growth_rate(vial, gr_start, elapsed_time):
    save_path = os.path.dirname(os.path.realpath(__file__))
    ODfile_name =  "vial{0}_OD.txt".format(vial)
    # Grab Data and make setpoint
    OD_path = os.path.join(save_path, EXP_NAME, 'OD', ODfile_name)
    OD_data = np.genfromtxt(OD_path, delimiter=',')
    raw_time = OD_data[:,0]
    raw_OD = OD_data[:,1]
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
    gr_path = os.path.join(save_path, EXP_NAME, 'growthrate', file_name)
    text_file = open(gr_path,"a+")
    text_file.write("{0},{1}\n".format(elapsed_time, slope))
    text_file.close()

def parse_data(data, elapsed_time, vials, parameter):
    save_path = os.path.dirname(os.path.realpath(__file__))
    if data == 'empty':
        print("%s Data Empty! Skipping data log...".format(parameter))
        logger.warning('%s data empty! Skipping data log...' % parameter)
    else:
        for x in vials:
            file_name =  "vial{0}_{1}.txt".format(x, parameter)
            file_path = os.path.join(save_path, EXP_NAME, parameter, file_name)
            text_file = open(file_path,"a+")
            text_file.write("{0},{1}\n".format(elapsed_time, data[x]))
            text_file.close()

def start_background_loop(loop):
    logger.debug('starting background loop')
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run():
    global dpu_evolver_ns
    socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
    dpu_evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
    socketIO.wait()

def initialize_exp(vials, always_yes=False):
    logger.debug('initializing experiment')
    global od_cal, temp_cal, shared_name, shared_ip, shared_port
    shared_name = EXP_NAME
    shared_ip = EVOLVER_IP
    shared_port = EVOLVER_PORT
    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(run)

    if dpu_evolver_ns is None:
        print("Waiting for evolver connection...")
        logger.info('waiting for eVOLVER connection')

    save_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.join(save_path, EXP_NAME)

    while dpu_evolver_ns is None:
        pass

    if os.path.exists(dir_path):
        logger.info('found an existing experiment')
        if always_yes:
            exp_continue = 'y'
        else:
            exp_continue = input('Continue from existing experiment? (y/n): ')
    else:
        exp_continue = 'n'

    if exp_continue == 'n':

        start_time = time.time()
        if os.path.exists(dir_path):
            if always_yes:
                exp_overwrite = 'y'
            else:
                exp_overwrite = input('Directory aleady exists. '
                                      'Overwrite with new experiment? (y/n): ')
            logger.info('data directory already exists')
            if exp_overwrite == 'y':
                logger.info('deleting existing data directory')
                shutil.rmtree(dir_path)
            else:
                print('Change experiment name in custom_script.py '
                      'and then restart...')
                logger.warning('not deleting existing data directory, exiting')
                exit() #exit

        logger.debug('creating data directories')
        os.makedirs(os.path.join(dir_path,'OD'))
        os.makedirs(os.path.join(dir_path,'temp'))
        os.makedirs(os.path.join(dir_path,'temp_config'))
        if OPERATION_MODE == 'turbidostat':
            os.makedirs(os.path.join(dir_path,'pump_log'))
            os.makedirs(os.path.join(dir_path,'ODset'))
            os.makedirs(os.path.join(dir_path,'growthrate'))
        if OPERATION_MODE == 'chemostat':
            os.makedirs(os.path.join(dir_path,'chemo_config'))

        logger.debug('requesting OD calibrations')
        dpu_evolver_ns.emit('getcalibrationod', {}, namespace = '/dpu-evolver')
        while od_cal is None:
            pass

        logger.debug('requesting temperature calibrations')
        dpu_evolver_ns.emit('getcalibrationtemp',
                            {}, namespace = '/dpu-evolver')
        while temp_cal is None:
            pass

        for x in vials:
            # make OD file
            file_name =  "vial{0}_OD.txt".format(x)
            file_path = os.path.join(dir_path, 'OD', file_name)
            text_file = open(file_path, "w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(
                EXP_NAME, x, time.strftime("%c")))
            text_file.close()

            # make temperature data file
            file_name = "vial{0}_temp.txt".format(x)
            file_path = os.path.join(dir_path, 'temp', file_name)
            text_file = open(file_path, "w").close()

            # make temperature configuration file
            file_name =  "vial{0}_tempconfig.txt".format(x)
            file_path = os.path.join(dir_path, 'temp_config', file_name)
            text_file = open(file_path, "w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(
                EXP_NAME, x, time.strftime("%c")))
            #initialize based on custom_script.choose_setup()
            text_file.write("0,{0}\n".format(TEMP_INITIAL[x]))
            text_file.close()

            if OPERATION_MODE == 'turbidostat':
                # make pump log file
                file_name =  "vial{0}_pump_log.txt".format(x)
                file_path = os.path.join(dir_path, 'pump_log', file_name)
                text_file = open(file_path, "w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(
                    EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n")
                text_file.close()

                # make ODset file
                file_name =  "vial{0}_ODset.txt".format(x)
                file_path = os.path.join(dir_path, 'ODset', file_name)
                text_file = open(file_path, "w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(
                    EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n")
                text_file.close()

                # make growth rate file
                file_name =  "vial{0}_gr.txt".format(x)
                file_path = os.path.join(dir_path, 'growthrate', file_name)
                text_file = open(file_path, "w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(
                    EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n") #initialize to 0
                text_file.close()

            if OPERATION_MODE == 'chemostat':
                #make chemostat file
                file_name =  "vial{0}_chemoconfig.txt".format(x)
                file_path = os.path.join(dir_path, 'chemo_config', file_name)
                text_file = open(file_path, "w")
                text_file.write("0,0,0\n") #header
                text_file.write("0,0,0\n") #initialize to 0
                text_file.close()

        stir_rate(STIR_INITIAL)
        OD_read = None
        temp_read = None
        print('Getting initial values from eVOLVER...')
        logger.info('getting initial values from eVOLVER')
        while OD_read is None and temp_read is None:
            OD_read, temp_read  = read_data(vials)
            if always_yes:
                exp_blank = 'y'
            else:
                exp_blank = input('Calibrate vials to blank? (y/n): ')
            if exp_blank == 'y':
                OD_initial = OD_read
                logger.info('using initial OD measurement as blank')
            else:
                OD_initial = np.zeros(len(vials))

    else:
        # load existing experiment
        pickle_name =  "{0}.pickle".format(EXP_NAME)
        pickle_path = os.path.join(save_path, EXP_NAME, pickle_name)
        logger.info('loading previous experiment data: %s' % pickle_path)
        with open(pickle_path, 'rb') as f:
            loaded_var  = pickle.load(f)
        x = loaded_var
        start_time = x[0]
        OD_initial = x[1]

        # Restart chemostat pumps
        current_chemo = [0] * 16

    # copy current custom script to txt file
    backup_filename = '{0}_{1}.txt'.format(EXP_NAME,
                                           time.strftime('%y%m%d_%H%M'))
    shutil.copy('custom_script.py',os.path.join(save_path, EXP_NAME,
                                                backup_filename))
    logger.info('saved a copy of current custom_script.py as %s' %
                backup_filename)
    return start_time, OD_initial

def stop_all_pumps():
    logger.warning('stopping all pumps')
    command = {'param':'pump', 'message':'stop'}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')
    print('All Pumps Stopped!')

def save_var(start_time, OD_initial):
    # save variables needed for restarting experiment later
    save_path = os.path.dirname(os.path.realpath(__file__))
    pickle_name = "{0}.pickle".format(EXP_NAME)
    pickle_path = os.path.join(save_path, EXP_NAME, pickle_name)
    logger.debug('saving all variables: %s' % pickle_path)
    with open(pickle_path, 'wb') as f:
        pickle.dump([start_time, OD_initial], f)

def restart_chemo():
    logger.debug('restarting chemostat')
    global current_chemo
    current_chemo = [0] * 16

if __name__ == '__main__':
    print('Please run main_eVOLVER.py instead')
