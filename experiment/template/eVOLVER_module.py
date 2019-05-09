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

def read_data(vials, exp_name):
    global wait_for_data, received_data, current_temps, connected, stop_waiting, shared_ip, shared_port

    save_path = os.path.dirname(os.path.realpath(__file__))

    odcal_path = os.path.join(save_path,exp_name,'od_cal.txt')
    od_cal = np.genfromtxt(odcal_path, delimiter=',')

    tempcal_path = os.path.join(save_path,exp_name,'temp_calibration.txt')
    temp_cal = np.genfromtxt(tempcal_path, delimiter=',')

    wait_for_data = True
    stop_waiting = False
    dpu_evolver_ns.emit('data', {'config':{'od':[2500] * 16, 'temp':['NaN'] * 16}}, namespace='/dpu-evolver')
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
        file_path = os.path.join(save_path,exp_name,'temp_config',file_name)
        temp_set_data = np.genfromtxt(file_path, delimiter=',')
        temp_set = temp_set_data[len(temp_set_data)-1][1]
        temp_set = int((temp_set - temp_cal[1][x])/temp_cal[0][x])
        temps.append(temp_set)

        try:
            if (od_cal.shape[0] == 4):
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

def fluid_command(MESSAGE, vial, elapsed_time, pump_wait, exp_name, time_on, file_write):
    command = {'param':'pump', 'message':MESSAGE}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')

    save_path = os.path.dirname(os.path.realpath(__file__))

    file_name =  "vial{0}_pump_log.txt".format(vial)
    file_path = os.path.join(save_path,exp_name,'pump_log',file_name)

    if file_write == 'y':
        text_file = open(file_path,"a+")
        text_file.write("{0},{1}\n".format(elapsed_time, time_on))
        text_file.close()

def update_chemo(vials, exp_name, bolus_in_s, control):

    global current_chemo

    save_path = os.path.dirname(os.path.realpath(__file__))
    MESSAGE = {}
    for x in vials:
        file_name =  "vial{0}__chemoconfig.txt".format(x)
        file_path = os.path.join(save_path,exp_name,'chemo_config',file_name)

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

def parse_data(data, elapsed_time, vials, exp_name, parameter):
    save_path = os.path.dirname(os.path.realpath(__file__))
    if data == 'empty':
        print("%s Data Empty! Skipping data log...".format(parameter))
    else:
        for x in vials:
            file_name =  "vial{0}_{1}.txt".format(x, parameter)
            file_path = os.path.join(save_path,exp_name,parameter,file_name)
            text_file = open(file_path,"a+")
            text_file.write("{0},{1}\n".format(elapsed_time, data[x]))
            text_file.close()

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run(evolver_ip, evolver_port):
    global dpu_evolver_ns
    socketIO = SocketIO(evolver_ip, evolver_port)
    dpu_evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
    socketIO.wait()

def initialize_exp(exp_name, vials, evolver_ip, evolver_port):
    global od_cal, temp_cal, shared_name, shared_ip, shared_port
    shared_name = exp_name
    shared_ip = evolver_ip
    shared_port = evolver_port
    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(run, evolver_ip, evolver_port)

    if dpu_evolver_ns is None:
        print("Waiting for evolver connection...")

    save_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.join(save_path,exp_name)



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
        os.makedirs(os.path.join(dir_path,'pump_log'))
        os.makedirs(os.path.join(dir_path,'temp_config'))
        os.makedirs(os.path.join(dir_path,'ODset'))
        os.makedirs(os.path.join(dir_path,'chemo_config'))

        dpu_evolver_ns.emit('getcalibrationod', {}, namespace = '/dpu-evolver')
        while od_cal is None:
            pass

        dpu_evolver_ns.emit('getcalibrationtemp', {}, namespace = '/dpu-evolver')
        while temp_cal is None:
            pass

        for x in vials:
            file_name =  "vial{0}_OD.txt".format(x)
            file_path = os.path.join(dir_path,'OD',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name, x, time.strftime("%c")))
            text_file.close()

            file_name =  "vial{0}_temp.txt".format(x)
            file_path = os.path.join(dir_path,'temp',file_name)
            text_file = open(file_path,"w").close()

            file_name =  "vial{0}_tempconfig.txt".format(x)
            file_path = os.path.join(dir_path,'temp_config',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name, x, time.strftime("%c")))
            text_file.write("0,0\n")
            text_file.close()

            file_name =  "vial{0}_pump_log.txt".format(x)
            file_path = os.path.join(dir_path,'pump_log',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name, x, time.strftime("%c")))
            text_file.write("0,0\n")
            text_file.close()

            file_name =  "vial{0}_ODset.txt".format(x)
            file_path = os.path.join(dir_path,'ODset',file_name)
            text_file = open(file_path,"w")
            text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name, x, time.strftime("%c")))
            text_file.write("0,0\n")
            text_file.close()

            file_name =  "vial{0}_chemoconfig.txt".format(x)
            file_path = os.path.join(dir_path,'chemo_config',file_name)
            text_file = open(file_path,"w")
            text_file.write("0,0,0\n")
            text_file.write("0,0,0\n")
            text_file.close()

        OD_read = None
        temp_read = None
        print('Getting initial values from eVOLVER...')
        while OD_read is None and temp_read is None:
            OD_read, temp_read  = read_data(vials, exp_name)
            exp_blank = input('Calibrate vials to blank? (y/n): ')
            if exp_blank == 'y':
                OD_initial = OD_read
            else:
                OD_initial = np.zeros(len(vials))

    else:
        pickle_name =  "{0}.pickle".format(exp_name)
        pickle_path = os.path.join(save_path,exp_name,pickle_name)
        with open(pickle_path, 'rb') as f:
            loaded_var  = pickle.load(f)
        x = loaded_var
        start_time = x[0]
        OD_initial = x[1]

        # Restart chemostat pumps
        current_chemo = [0] * 16

    return start_time, OD_initial

def stop_all_pumps():
    command = {'param':'pump', 'message':'stop'}
    dpu_evolver_ns.emit('command', command, namespace='/dpu-evolver')
    print('All Pumps Stopped!')

def save_var(exp_name, start_time, OD_initial):
    save_path = os.path.dirname(os.path.realpath(__file__))
    pickle_name =  "{0}.pickle".format(exp_name)
    pickle_path = os.path.join(save_path,exp_name,pickle_name)
    with open(pickle_path, 'wb') as f:
        pickle.dump([start_time, OD_initial], f)

def restart_chemo():
    global current_chemo
    current_chemo = [0] * 16

if __name__ == '__main__':
    print('Please run main_eVOLVER.py instead')
