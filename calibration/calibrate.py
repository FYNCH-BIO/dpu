import sys
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, leastsq
from socketIO_client import SocketIO, BaseNamespace
from scipy.linalg import lstsq
import scipy, scipy.optimize
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

def SurfacePlot(func, data, fittedParameters, i, fig):
    x_data = data[0]
    y_data = data[1]
    z_data = data[2]

    xModel = np.linspace(min(x_data), max(x_data), 20)
    yModel = np.linspace(min(y_data), max(y_data), 20)
    X, Y = np.meshgrid(xModel, yModel)

    Z = func(np.array([X, Y]), *fittedParameters)

    ax = fig.add_subplot(4,4, i + 1, projection = '3d')

    ax.plot_surface(X, Y, Z, rstride=1, cstride=1, linewidth=1, antialiased=True, alpha=0.5)

    ax.scatter(x_data, y_data, z_data, c='r', s=10) # show data along with plotted surface

    ax.set_title('Surface Plot (click-drag with mouse)') # add a title for surface plot
    ax.set_xlabel('X Data') # X axis data label
    ax.set_ylabel('Y Data') # Y axis data label
    ax.set_zlabel('Z Data') # Z axis data label

def parse_od_cal_data(data):
    cal_ods = {'od90': [0] * 16, 'od135': [0] * 16, 'temp':[0] * 16}
    vial_datas = data['vialData']

    for param, param_vial_datas in vial_datas.items():
        for i, vial_data in enumerate(param_vial_datas):
            cal_ods[param][i] = [0] * 16
            for j in range(16):
                # Shift indexes to handle rotation of vials
                index_change = -j + i
                cal_ods[param][i][j] = vial_data[index_change]
    return cal_ods

def parse_temp_cal_data(data):
    return data['vialData']

def sigmoid(x, a, b, c, d):
    y = a + (b - a)/(1 + (10**((c-x)*d)))
    return y

def linear(x, a, b):
    y = np.array(x)*a + b
    return y

def three_dim(data, c0,c1,c2,c3,c4,c5,c6,c7,c8,c9):
    x = data[0]
    y = data[1]
    return c0 + c1*x + c2*y + c3*x**2 + c4*x*y + c5*y**2 + c6*x**3 + c7*(x**2)*y + c8*x*(y**2) + c9*(y**3)

def fit(x, y):
    #Fits the data to a sigmoid and returns the parameters
    xdata = np.array(x)
    ydata = np.array(y)

    paramsig, pcovsig = curve_fit(sigmoid, xdata, ydata, p0 = [62721, 62721, 0, -1], maxfev = 10000000)
    paramlin, pcovlin = curve_fit(linear, xdata, ydata, p0 = [-8750, 62721])
    return paramsig, paramlin;

def residuals(curve_y, real_y):
    #Calculates residuals using the least square method
    curve_arr = np.array(curve_y)
    real_arr = np.array(real_y)
    res = (curve_arr - real_arr)**2
    sumsquare = res.sum()
    return sumsquare

def calibrate_od(calibration_data, graph_name, param, graph = False):
    global input_data
    paramlist = []
    if graph:
        fig1, ax = plt.subplots(4, 4)
        fig1.suptitle('File Name: ' + graph_name)

    for m in range(16):
        raw_ods = []
        stds = []
        for raw_od in calibration_data[param][m]:
            raw_ods.append(np.median(raw_od))
            stds.append(np.std(raw_od))

        paramsig, paramlin = fit(input_data,raw_ods)
        paramlist.append(np.array(paramsig).tolist())
        if graph == True:
            ax[m//4, (m % 4)].plot(input_data, raw_ods, 'o', markersize=1.5, color='black')
            ax[m//4, (m % 4)].plot(np.linspace(0, max(input_data), 500), sigmoid(np.linspace(0, max(input_data), 500), *paramsig), markersize = 1.5, label=None)
            ax[m//4, (m % 4)].errorbar(input_data, raw_ods, yerr=stds, fmt='none')
            ax[m//4, (m % 4)].set_title('Vial: ' + str(m))
            ax[m//4, (m % 4)].ticklabel_format(style='sci', axis='y', scilimits=(0,0))

    if graph:
        plt.subplots_adjust(hspace = 0.6)
        plt.show()
    return paramlist


def calibrate3d_od(calibration_data, graph_name, graph= False):
    global input_data

    initial_parameters = [1.0, 1.0, 1.0,1.0,1.0,1.0, 1.0, 1.0,1.0,1.0]

    if graph:
        fig1 = plt.figure()
        fig1.suptitle('File Name: ' + graph_name)

    for i in range(16):
        x_data = np.median(calibration_data['od90'][i], axis = 1)
        y_data = np.median(calibration_data['od135'][i], axis = 1)
        z_data = np.array(input_data)

        data = [x_data, y_data, z_data]

        fitted_parameters, pcov = scipy.optimize.curve_fit(three_dim, [x_data, y_data], z_data, p0 = initial_parameters)
        if graph:
            SurfacePlot(three_dim, data, fitted_parameters, i, fig1)

        modelPredictions = three_dim(data, *fitted_parameters)

        absError = modelPredictions - z_data

        SE = np.square(absError) # squared errors
        MSE = np.mean(SE) # mean squared errors
        RMSE = np.sqrt(MSE) # Root Mean Squared Error, RMSE
        Rsquared = 1.0 - (np.var(absError) / np.var(z_data))
        print('Vial ' + str(i))
        print('RMSE:', RMSE)
        print('R-squared:', Rsquared)
        print('fitted prameters', fitted_parameters)

    if graph:
        plt.show()

    return fitted_parameters

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
    parser.add_option('--param', action = 'store', dest = 'param')


    (options, args) = parser.parse_args()
    cal_file = options.calfile
    get_files = options.getfiles
    od_cal = options.odcal
    temp_cal = options.tempcal
    ip_address = 'http://' + options.ipaddress
    odpower = options.odpower
    odaxis = options.odaxis
    multidimfit = options.multidimfit
    param = options.param

    if not options.ipaddress:
        print('Please specify ip address')
        parser.print_help()
        sys.exit(2)

    if not param:
        param = 'od90'

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
        parameters = calibrate_od(raw_calibration, cal_file, param, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationod', {'parameters':parameters, 'filename': cal_file, 'caltype': 'sigmoid'}, namespace='/dpu-evolver')
    if cal_file is not None and od_cal and multidimfit:
        parameters = calibrate3d_od(raw_calibration, cal_file, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationod', {'parameters':parameters, 'filename': cal_file, 'caltype': 'multidim'}, namespace='/dpu-evolver')
    if cal_file is not None and temp_cal:
        parameters = calibrate_temp(raw_calibration, cal_file, graph = True)
        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setcalibrationtemp', {'parameters':parameters, 'filename': cal_file}, namespace='/dpu-evolver')
