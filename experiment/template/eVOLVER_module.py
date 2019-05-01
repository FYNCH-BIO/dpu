import socket
import os.path
import shutil
import time
import pickle
import numpy as np
import numpy.matlib
import matplotlib
import scipy.signal
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from socketIO_client import SocketIO, BaseNamespace
from threading import Thread
import asyncio
import custom_script

plt.ioff()

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
control = np.power(2,range(0,32))
current_chemo = [0] * 16
current_temps = [0] * 16
connected = False

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        global connected, current_temps
        print("Connected to eVOLVER as client")
        connected = True

    def on_disconnect(self, *args):
        global connected
        print("Disconected from eVOLVER as client")
        connected = False

    def on_reconnect(self, *args):
        global connected, stop_waiting, current_temps
        current_temps = [0] * 16
        print("Reconnected to eVOLVER as client")
        connected = True
        stop_waiting = True

    def on_dataresponse(self, data):
        #print(data)
        global received_data, wait_for_data
        received_data = data
        wait_for_data = False

    def on_calibrationod(self, data):
        global od_cal, save_path, shared_name
        file_path = os.path.join(save_path,shared_name,'od_cal.txt')
        with open(file_path, 'w') as f:
            f.write(data)
        od_cal = True

    def on_calibrationtemp(self, data):
        global temp_cal, save_path, shared_name
        file_path = os.path.join(save_path,shared_name,'temp_calibration.txt')
        with open(file_path , 'w') as f:
            f.write(data)
        temp_cal = True

def read_data(vials):
    global wait_for_data, received_data, current_temps, connected, stop_waiting, shared_ip, shared_port

    save_path = os.path.dirname(os.path.realpath(__file__))

    odcal_path = os.path.join(save_path,custom_script.EXP_NAME,'od_cal.txt')
    od_cal = np.genfromtxt(odcal_path, delimiter=',')    

    tempcal_path = os.path.join(save_path,custom_script.EXP_NAME,'temp_calibration.txt')
    temp_cal = np.genfromtxt(tempcal_path, delimiter=',')

    wait_for_data = True
    stop_waiting = False
    dpu_evolver_ns.emit('data', {'config':{'od':[custom_script.OD_POWER] * 16, 'temp':['NaN'] * 16}}, namespace='/dpu-evolver')
    start_time = time.time()
    # print('Fetching data from eVOLVER')
    while(wait_for_data):
        if not connected or stop_waiting or (time.time() - start_time > 60):
            wait_for_data = False
            print('Issue with eVOLVER communication - skipping data acquisition')
            return None, None
        pass


    od_data = received_data['od']
    temp_data = received_data['temp']
    if 'NaN' in od_data or 'NaN' in temp_data:
        print('NaN recieved, Error with measurement')
        return None, None
    temps = []
    for x in vials:
        file_name =  "vial{0}_tempconfig.txt".format(x)
        file_path = os.path.join(save_path,custom_script.EXP_NAME,'temp_config',file_name)
        temp_set_data = np.genfromtxt(file_path, delimiter=',')
        temp_set = temp_set_data[len(temp_set_data)-1][1]
        temp_set = int((temp_set - temp_cal[1][x])/temp_cal[0][x]) #convert raw thermistor data into temp using calibration fit
        temps.append(temp_set)

        try:
            if (od_cal.shape[0] == 4): #convert raw photodiode data into ODdata using calibration curve
                od_data[x] = np.real(od_cal[2,x] - ((np.log10((od_cal[1,x]-od_cal[0,x])/(float(od_data[x]) - od_cal[0,x])-1))/od_cal[3,x]))
        except ValueError:
            print("OD Read Error")
            od_data[x] = 'NaN'
        try:
            temp_data[x] = (float(temp_data[x]) * temp_cal[0][x]) + temp_cal[1][x]
        except ValueError:
            print("Temp Read Error")
            temp_data[x]  = 'NaN'
    if not temps == current_temps:
        MESSAGE = list(temps)
        command = {'param':'temp', 'message':MESSAGE}
        dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')
        current_temps = temps

    return od_data, temp_data

def fluid_command(MESSAGE, vial, elapsed_time, pump_wait, time_on, file_write):
    command = {'param':'pump', 'message':MESSAGE}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')

    save_path = os.path.dirname(os.path.realpath(__file__))

    file_name =  "vial{0}_pump_log.txt".format(vial)
    file_path = os.path.join(save_path,custom_script.EXP_NAME,'pump_log',file_name)

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
        file_path = os.path.join(save_path,custom_script.EXP_NAME,'chemo_config',file_name)

        data = np.genfromtxt(file_path, delimiter=',')
        chemo_set = data[len(data)-1][2]
        if not chemo_set == current_chemo[x]:
            current_chemo[x] = chemo_set
            MESSAGE = {'pumps_binary':"{0:b}".format(control[x]), 'pump_time': bolus_in_s[x], 'efflux_pump_time': bolus_in_s[x] * 2, 'delay_interval': chemo_set, 'times_to_repeat': -1, 'run_efflux': 1}
            command = {'param': 'pump', 'message': MESSAGE}
            dpu_evolver_ns.emit('command', command, namespace = '/dpu-evolver')

def stir_rate (MESSAGE):
    command = {'param':'stir', 'message':MESSAGE}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')

def get_flow_rate():
    file_path = os.path.join(save_path,custom_script.PUMP_CAL_FILE)
    flow_calibration = np.loadtxt(file_path, delimiter="\t")
    if len(flow_calibration)==16:
        flow_rate=flow_calibration
    else:
        flow_rate=flow_calibration[0,:] #Currently just implementing influx flow rate
    return flow_rate

def calc_growth_rate(vial, gr_start, elapsed_time):
    save_path = os.path.dirname(os.path.realpath(__file__))
    file_name =  "vial{0}_gr.txt".format(vial) 
    # Grab Data and make setpoint
    OD_path = os.path.join(save_path,custom_script.EXP_NAME,'OD',file_name)
    OD_data = np.genfromtxt(OD_path, delimiter=',')
    raw_time=OD_data[:,0]
    raw_OD=OD_data[:,1]
    raw_time=raw_time[np.isfinite(raw_OD)]
    raw_OD=raw_OD[np.isfinite(raw_OD)]

    # Trim points prior to gr_start
    trim_time=raw_time[np.nonzero(np.where(raw_time>gr_start,1,0))]
    trim_OD=raw_OD[np.nonzero(np.where(raw_time>gr_start,1,0))]

    # Take natural log, calculate slope
    log_OD = np.log(trim_OD)
    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(trim_time[np.isfinite(log_OD)],log_OD[np.isfinite(log_OD)])

    # Save slope to file
    gr_path = os.path.join(save_path,custom_script.EXP_NAME,'growthrate',file_name)
    text_file = open(gr_path,"a+")
    text_file.write("{0},{1}\n".format(elapsed_time,slope))
    text_file.close()

def parse_data(data, elapsed_time, vials, parameter):
    save_path = os.path.dirname(os.path.realpath(__file__))
    if data == 'empty':
        print("%s Data Empty! Skipping data log...".format(parameter))
    else:
        for x in vials:
            file_name =  "vial{0}_{1}.txt".format(x, parameter)
            file_path = os.path.join(save_path,custom_script.EXP_NAME,parameter,file_name)
            text_file = open(file_path,"a+")
            text_file.write("{0},{1}\n".format(elapsed_time, data[x]))
            text_file.close()

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run():
    global dpu_evolver_ns
    socketIO = SocketIO(custom_script.EVOLVER_IP, custom_script.EVOLVER_PORT)
    dpu_evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
    socketIO.wait()

def initialize_exp(vials):
    global od_cal, temp_cal, shared_name, shared_ip, shared_port
    shared_name = custom_script.EXP_NAME
    shared_ip = custom_script.EVOLVER_IP
    shared_port = custom_script.EVOLVER_PORT
    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(run)

    if dpu_evolver_ns is None:
        print("Waiting for evolver connection...")

    save_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.join(save_path,custom_script.EXP_NAME)



    while dpu_evolver_ns is None:
        pass

    if os.path.exists(dir_path):
        exp_continue = input('Continue from existing experiment? (y/n): ')
    else:
        exp_continue = 'n'

    if exp_continue == 'n':

        start_time = time.time()
        if os.path.exists(dir_path):
            exp_overwrite = input('Directory aleady exists. Overwrite with new experiment? (y/n): ')
            if exp_overwrite == 'y':
                shutil.rmtree(dir_path)
            else:
                print('Change experiment name in custom_script.py and then restart...')
                exit() #exit

        os.makedirs(os.path.join(dir_path,'OD'))
        os.makedirs(os.path.join(dir_path,'temp'))
        os.makedirs(os.path.join(dir_path,'temp_config'))
        if custom_script.OPERATION_MODE == 'turbidostat':
            os.makedirs(os.path.join(dir_path,'pump_log'))
            os.makedirs(os.path.join(dir_path,'ODset'))
            os.makedirs(os.path.join(dir_path,'growthrate'))
        if custom_script.OPERATION_MODE == 'chemostat':
            os.makedirs(os.path.join(dir_path,'chemo_config'))

        dpu_evolver_ns.emit('getcalibrationod', {}, namespace = '/dpu-evolver')
        while od_cal is None:
            pass

        dpu_evolver_ns.emit('getcalibrationtemp', {}, namespace = '/dpu-evolver')
        while temp_cal is None:
            pass

        for x in vials:
            file_name =  "vial{0}_OD.txt".format(x) # make OD file
            file_path = os.path.join(dir_path,'OD',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(custom_script.EXP_NAME, x, time.strftime("%c")))
            text_file.close()

            file_name =  "vial{0}_temp.txt".format(x) # make temperature data file
            file_path = os.path.join(dir_path,'temp',file_name)
            text_file = open(file_path,"w").close()

            file_name =  "vial{0}_tempconfig.txt".format(x) # make temperature configuration file
            file_path = os.path.join(dir_path,'temp_config',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(custom_script.EXP_NAME, x, time.strftime("%c")))
            text_file.write("0,{0}\n".format(custom_script.TEMP_INITIAL[x])) #initialize based on custom_script.choose_setup()
            text_file.close()

            if custom_script.OPERATION_MODE == 'turbidostat':
                file_name =  "vial{0}_pump_log.txt".format(x) # make pump log file
                file_path = os.path.join(dir_path,'pump_log',file_name)
                text_file = open(file_path,"w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(custom_script.EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n")
                text_file.close()

                file_name =  "vial{0}_ODset.txt".format(x) # make ODset file
                file_path = os.path.join(dir_path,'ODset',file_name)
                text_file = open(file_path,"w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(custom_script.EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n")
                text_file.close()

                file_name =  "vial{0}_gr.txt".format(x) # make growth rate file
                file_path = os.path.join(dir_path,'growthrate',file_name)
                text_file = open(file_path,"w")
                text_file.write("Experiment: {0} vial {1}, {2}\n".format(custom_script.EXP_NAME, x, time.strftime("%c")))
                text_file.write("0,0\n") #initialize to 0
                text_file.close()

            if custom_script.OPERATION_MODE == 'chemostat':
                file_name =  "vial{0}_chemoconfig.txt".format(x) #make chemostat file
                file_path = os.path.join(dir_path,'chemo_config',file_name)
                text_file = open(file_path,"w")
                text_file.write("0,0,0\n") #header
                text_file.write("0,0,0\n") #initialize to 0
                text_file.close()

        stir_rate(custom_script.STIR_INITIAL)
        OD_read = None
        temp_read = None
        print('Getting initial values from eVOLVER...')
        while OD_read is None and temp_read is None:
            OD_read, temp_read  = read_data(vials)
            exp_blank = input('Calibrate vials to blank? (y/n): ')
            if exp_blank == 'y':
                OD_initial = OD_read # take an OD measurement, subtract OD_initial from all future measurements, note that this is not stored in data files
            else:
                OD_initial = np.zeros(len(vials)) # just use zeros, may lead to offsets in data if vial/medai is slightly diff, but can correct in post-processing unless needed for feedback

    else: #load existing experiment
        pickle_name =  "{0}.pickle".format(custom_script.EXP_NAME)
        pickle_path = os.path.join(save_path,custom_script.EXP_NAME,pickle_name)
        with open(pickle_path, 'rb') as f:
            loaded_var  = pickle.load(f)
        x = loaded_var
        start_time = x[0]
        OD_initial = x[1]

        # Restart chemostat pumps
        current_chemo = [0] * 16

    # copy current custom script to txt file
    backup_filename = '{0}_{1}.txt'.format(custom_script.EXP_NAME,(time.strftime('%y%m%d_%H%M')))
    shutil.copy('custom_script.py',os.path.join(save_path,custom_script.EXP_NAME,backup_filename))
    return start_time, OD_initial

def stop_all_pumps():
    command = {'param':'pump', 'message':'stop'}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')
    print('All Pumps Stopped!')

def save_var(start_time, OD_initial):
    # save variables needed for restarting experiment later
    save_path = os.path.dirname(os.path.realpath(__file__))
    pickle_name =  "{0}.pickle".format(custom_script.EXP_NAME)
    pickle_path = os.path.join(save_path,custom_script.EXP_NAME,pickle_name)
    with open(pickle_path, 'wb') as f:
        pickle.dump([start_time, OD_initial], f)

def restart_chemo():
    global current_chemo
    current_chemo = [0] * 16

if __name__ == '__main__':
    print('Please run main_eVOLVER.py instead')
