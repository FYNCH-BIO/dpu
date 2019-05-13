import sys
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, leastsq
from socketIO_client import SocketIO, BaseNamespace
from scipy.linalg import lstsq
import asyncio
from threading import Thread
import json
import optparse
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter

cal_received = False
raw_calibration = None
input_data = None
dpu_evolver_ns = None
odpower = None
odaxis = None

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        global connected
        print("Connected to eVOLVER as client")
        connected = True

    def on_disconnect(self, *args):
        global connected
        print("Disconected from eVOLVER as client")
        connected = False

    def on_reconnect(self, *args):
        global connected, stop_waiting
        print("Reconnected to eVOLVER as client")
        connected = True
        stop_waiting = True

    def on_calibrationrawod(self, data):
        global cal_received, raw_calibration, input_data
        input_data = data['inputData']
        raw_calibration = parse_od_cal_data(data)
        cal_received = True

    def on_calibrationrawtemp(self, data):
        global cal_received, raw_calibration, input_data
        raw_calibration = parse_temp_cal_data(data)
        cal_received = True

    def on_odfilenames(self, data):
        global cal_received
        for f in data:
            print(f)
        cal_received = True

    def on_tempfilenames(self, data):
        global cal_received
        for f in data:
            print(f)
        cal_received = True

def parse_od_cal_data(data):
    global input_data, odaxis

    input_data = data['inputData'] #load data from json

    yaxis_levels = []
    for cal_measurement in data['vialData']:
        yaxis_levels.insert(len(yaxis_levels),cal_measurement[odaxis]) # identify power levels from json

    yaxis_levels = list(set(yaxis_levels)) # drop replicated values
    cal_ods = {}
    for level in yaxis_levels:
        cal_ods[level] = [] #create json to house data for each level

    for cal_measurement in data['vialData']:
        power_level = cal_measurement[odaxis]
        for i,od in enumerate(cal_measurement['od']):
            if len(cal_ods[power_level]) == i:
                cal_ods[power_level].append([])
            cal_ods[power_level][i].append(od)

    for power_level, vial_datas in cal_ods.items():
        for i, vial_data in enumerate(vial_datas):
            new_vial_data = [0] * 16
            # Shift indexes to handle rotation of vials
            for j in range(16):
                index_change = -j + i
                new_vial_data[j] = vial_data[index_change]
            cal_ods[power_level][i] = new_vial_data

    return cal_ods

def parse_temp_cal_data(data):
    return data['vialData']

def sigmoid(x, a, b, c, d):
    y = a + (b - a)/(1 + (10**((c-x)*d)))
    return y

def linear(x, a, b):
    y = np.array(x)*a + b
    return y

def fit(x, y):
    #Fits the data to a sigmoid and returns the parameters
    xdata = np.array(x)
    ydata = np.array(y)

    paramsig, pcovsig = curve_fit(sigmoid, xdata, ydata, p0 = [62721, 62721, 0, -1], maxfev = 10000000)
    paramlin, pcovlin = curve_fit(linear, xdata, ydata, p0 = [-8750, 62721])
    return paramsig, paramlin;

def fit3d(x, y, z):
    x = np.array(x)
    y = np.array(y)
    z = np.array(z)

    data = np.transpose(np.stack((x, y, z), axis=0))
    # best-fit quadratic curve: Z = C[4]*X**2. + C[5]*Y**2. + C[3]*X*Y + C[1]*X + C[2]*Y + C[0]`
    A = np.c_[np.ones(data.shape[0]), data[:,:2], np.prod(data[:,:2], axis=1), data[:,:2]**2]
    paramquad,_,_,_ = lstsq(A, data[:,2])
    return paramquad, data;

def residuals(curve_y, real_y):
    #Calculates residuals using the least square method
    curve_arr = np.array(curve_y)
    real_arr = np.array(real_y)
    res = (curve_arr - real_arr)**2
    sumsquare = res.sum()
    return sumsquare

def calibrate_od(calibration_data, graph_name, graph= False):
    global input_data
    power_levels = []
    if odpower == 'all':
        power_levels = sorted(np.fromiter(calibration_data.keys(), dtype=int), reverse = False)
    else:
        power_levels = [int(odpower)]

    paramlist = []
    if graph:
        fig1, ax = plt.subplots(4, 4)
        fig1.suptitle('File Name: ' + graph_name)

    for level in power_levels:
        for m in range(16):
            raw_ods = []
            stds = []
            for raw_od in calibration_data[level][m]:
                raw_ods.append(np.mean(raw_od))
                stds.append(np.std(raw_od))

            paramsig, paramlin = fit(input_data,raw_ods)
            paramlist.append(np.array(paramsig).tolist())
            if graph == True:
                fit_label = str(odaxis) + ': ' + str(level) if m == 0 else None
                ax[m//4, (m % 4)].plot(input_data, raw_ods, 'o', markersize=1.5, color='black')
                ax[m//4, (m % 4)].plot(np.linspace(0, max(input_data), 500), sigmoid(np.linspace(0, max(input_data), 500), *paramsig), markersize = 1.5, label=fit_label)
                ax[m//4, (m % 4)].errorbar(input_data, raw_ods, yerr=stds, fmt='none')
                ax[m//4, (m % 4)].set_title('Vial: ' + str(m))
                ax[m//4, (m % 4)].ticklabel_format(style='sci', axis='y', scilimits=(0,0))

    if graph:
        fig1.legend(loc = 'lower center', ncol=len(power_levels))
        plt.subplots_adjust(hspace = 0.6)
        plt.show()
    return paramlist


def calibrate3d_od(calibration_data, graph_name, graph= False):
    global input_data
    power_levels = sorted(np.fromiter(raw_calibration.keys(), dtype=int), reverse = False)

    paramlist = []
    if graph:
        fig = plt.figure()
        fig.suptitle('File Name: ' + graph_name)

    for m in range(16): ##vial
        x= []; y = []; z = []
        for input_index, od_value in enumerate(input_data):
            for power_index, level in enumerate(power_levels):
                x.append(np.mean(calibration_data[level][m][input_index]))
                y.append(level)
                z.append(od_value)


        paramquad, data = fit3d(x, y, z)
        paramlist.append(np.array(paramquad).tolist())

        xs = np.arange(np.amin(x), np.amax(x),1000)
        xy = np.arange(np.amin(y), np.amax(y),100)
        (X, Y) = np.meshgrid(xs,xy)
        XX = X.flatten()
        YY = Y.flatten()

        Z = np.dot(np.c_[np.ones(XX.shape), XX, YY, XX*YY, XX**2, YY**2], paramquad).reshape(X.shape) # evaluate it on a grid

        if graph == True:
            ax = fig.add_subplot(4, 4, m+1, projection='3d')
            ax.plot_surface(X, Y, Z, rstride=1, cstride=1, alpha=0.2)
            ax.scatter(data[:,0], data[:,1], data[:,2], c='r', s=50)
            ax.set_title('Vial: ' + str(m))

    if graph:
        plt.subplots_adjust(hspace = 0.6)
        plt.show()

    return paramlist

def calibrate_temp(calibration_data, graph_name, graph = False):
    paramlist = []
    if graph:
        fig, ax = plt.subplots(4, 4)
        fig.suptitle('File Name: ' + graph_name)


    ave_temps = []
    stds = []
    entered_values = []

    for temp_measurement in calibration_data:
        for i, vial in enumerate(temp_measurement['temp']):
            if len(ave_temps) == i:
                ave_temps.append([])
                stds.append([])
                entered_values.append([])
            ave_temps[i].append(np.mean(vial))
            stds[i].append(np.std(vial))
            entered_values[i].append(float(temp_measurement['enteredValues'][i]))

    paramlist = []
    for m in range(16):
        params, cov = curve_fit(linear, ave_temps[m], entered_values[m])
        paramlist.append(params.tolist())
        if graph == True:
            ax[m//4, (m % 4)].plot(ave_temps[m], entered_values[m], 'o', markersize=3, color='black')
            ax[m//4, (m % 4)].plot(np.linspace(500, 3000, 50), linear(np.linspace(500,3000,50), *params), markersize = 1.5)
            ax[m//4, (m % 4)].set_title('Vial: ' + str(m))

    if graph:
        plt.subplots_adjust(hspace = 0.6)
        plt.show()
    return paramlist


def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run(evolver_ip, evolver_port):
    global dpu_evolver_ns
    socketIO = SocketIO(evolver_ip, evolver_port)
    dpu_evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
    socketIO.wait()

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-f', '--cal-file', action = 'store', dest = 'calfile')
    parser.add_option('-g', '--get-filenames', action = 'store_true', dest = 'getfiles')
    parser.add_option('-o', '--od', action = 'store_true', dest = 'odcal')
    parser.add_option('-t', '--temp', action = 'store_true', dest = 'tempcal')
    parser.add_option('-a', '--ip', action = 'store', dest = 'ipaddress')
    parser.add_option('--odpower', action = 'store', dest = 'odpower', default='2500')
    parser.add_option('--odaxis', action = 'store', dest = 'odaxis', default='powerLevel')
    parser.add_option('--3d', action = 'store_true', dest = 'multidimfit')


    (options, args) = parser.parse_args()
    cal_file = options.calfile
    get_files = options.getfiles
    od_cal = options.odcal
    temp_cal = options.tempcal
    ip_address = 'http://' + options.ipaddress
    odpower = options.odpower
    odaxis = options.odaxis
    multidimfit = options.multidimfit

    if not options.ipaddress:
        print('Please specify ip address')
        parser.print_help()
        sys.exit(1)

    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(run, ip_address, 8081)

    if not od_cal and not temp_cal:
        print('Please specify od or temperature calibration')
        parser.print_help()
        sys.exit(1)

    if dpu_evolver_ns is None:
        print("Waiting for evolver connection...")

    while dpu_evolver_ns is None:
        pass

    if get_files and od_cal:
        dpu_evolver_ns.emit('getcalibrationfilenamesod', {}, namespace = '/dpu-evolver')
    if get_files and temp_cal:
        dpu_evolver_ns.emit('getcalibrationfilenamestemp', {}, namespace = '/dpu-evolver')
    if cal_file and od_cal:
        dpu_evolver_ns.emit('getcalibrationrawod', {'filename':cal_file}, namespace='/dpu-evolver')
    if cal_file and temp_cal:
        dpu_evolver_ns.emit('getcalibrationrawtemp', {'filename':cal_file}, namespace = '/dpu-evolver')

    while not cal_received:
        pass

    if cal_file is not None and od_cal and not multidimfit:
        parameters = calibrate_od(raw_calibration, cal_file, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationod', {'parameters':parameters, 'filename': cal_file, 'caltype': 'sigmoid'}, namespace='/dpu-evolver')
    if cal_file is not None and od_cal and multidimfit:
        parameters = calibrate3d_od(raw_calibration, cal_file, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationod', {'parameters':parameters, 'filename': cal_file, 'caltype': 'multidim_quad'}, namespace='/dpu-evolver')
    if cal_file is not None and temp_cal:
        parameters = calibrate_temp(raw_calibration, cal_file, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationtemp', {'parameters':parameters, 'filename': cal_file}, namespace='/dpu-evolver')
