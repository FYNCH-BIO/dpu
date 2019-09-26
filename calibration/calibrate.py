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

VALID_FIT_TYPES = ['sigmoid', 'linear', 'constant', '3d']

data_received = False
calibration = None
input_data = None
dpu_evolver_ns = None

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

    def on_calibration(self, data):
        global data_received, calibration, input_data
        calibration = data
        data_received = True

    def on_calibrationnames(self, data):
        global data_received
        for calibration_name in data:
            print(calibration_name)
        data_received = True

def sigmoid(x, a, b, c, d):
    return a + (b - a)/(1 + (10**((c-x)*d)))

def linear(x, a, b):
    return np.array(x)*a + b

def three_dim(data, c0, c1, c2, c3, c4, c5):
    x = data[0]
    y = data[1]
    return c0 + c1*x + c2*y + c3*x**2 + c4*x*y + c5*y**2

def sigmoid_fit(calibration, fit_name, params, graph = True):
    coefficients = []

    # For single param calibrations, just take the first value from the returned dictionary
    calibration_data = list(process_vial_data(calibration, param = params[0]).values())[0]
    medians = calibration_data["medians"]
    standard_deviations = calibration_data["standard_deviations"]
    measured_data = calibration_data["measured_data"]

    for i in range(16):
        paramsig, paramlin = curve_fit(sigmoid, measured_data[i], medians[i], p0 = [62721, 62721, 0, -1], maxfev=1000000000)
        coefficients.append(np.array(paramsig).tolist())
    print(coefficients)

    if graph:
        graph_2d_data(sigmoid, measured_data, medians, standard_deviations, coefficients, fit_name, 'sigmoid', 0, max([max(sublist) for sublist in measured_data]), 500)
    return create_fit(coefficients, fit_name, "sigmoid", time.time(), params)

def linear_fit(calibration, fit_name, params, graph = True):
    coefficients = []

    # For single param calibrations, just take the first value from the returned dictionary
    print(calibration)
    calibration_data = list(process_vial_data(calibration, param = params[0]).values())[0]
    medians = calibration_data["medians"]
    standard_deviations = calibration_data["standard_deviations"]
    measured_data = calibration_data["measured_data"]

    for i in range(16):
        print(measured_data[i])
        print(medians[i])
        paramlin, cov = curve_fit(linear, medians[i], measured_data[i])
        coefficients.append(paramlin.tolist())

    if graph:
        graph_2d_data(linear, medians, measured_data, standard_deviations, coefficients, fit_name, 'linear', 500, 3000, 50)

    return create_fit(coefficients, fit_name, "linear", time.time(), params)

def constant_fit(calibration, fit_name, params):
    calibration_data = process_vial_data(calibration, param = params[0]).values()[0]
    measured_data = calibration_data["measured_data"]
    return create_fit(coefficients, fit_name, "constant", time.time(), params)

def three_dimension_fit(calibration, fit_name, params, graph = True):
    initial_parameters = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    coefficients = []
    datas = []
    calibration_data = process_vial_data(calibration)

    for param, param_data in calibration_data.items():
        if param == params[0]:
            x_datas = param_data['medians']
        elif param == params[1]:
            y_datas = param_data['medians']
        z_datas = param_data['measured_data']

    for i in range(16):
        x_data = np.array(x_datas[i])
        y_data = np.array(y_datas[i])
        z_data = np.array(z_datas[i])

        data = [x_data, y_data, z_data]

        fitted_parameters, pcov = scipy.optimize.curve_fit(three_dim, [x_data, y_data], z_data, p0 = initial_parameters)

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

        coefficients.append(fitted_parameters.tolist())
        datas.append(data)

    if graph:
        graph_3d_data(three_dim, datas, coefficients, fit_name)

    return create_fit(coefficients, fit_name, '3d', time.time(), params)

def graph_2d_data(func, measured_data, medians, standard_deviations, coefficients, fit_name, fit_type, space_min, space_max, space_step):
    linear_space = np.linspace(space_min, space_max, space_step)
    fig, ax = plt.subplots(4, 4)
    fig.suptitle("Fit Name: " + fit_name)
    for i in range(16):
        ax[i // 4, (i % 4)].plot(measured_data[i], medians[i], 'o', markersize=3, color='black')
        ax[i //4, (i % 4)].errorbar(measured_data[i], medians[i], yerr=standard_deviations[i], fmt='none')
        ax[i // 4, (i % 4)].plot(linear_space, func(linear_space, *coefficients[i]), markersize = 1.5, label = None)
        ax[i // 4, (i % 4)].set_title('Vial: ' + str(i))
        ax[i // 4, (i % 4)].ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    plt.subplots_adjust(hspace = 0.6)
    plt.show()

def graph_3d_data(func, datas, coefficients, fit_name):
    fig = plt.figure()
    fig.suptitle("Fit Name: " + fit_name)
    for i, data in enumerate(datas):
        x_data = data[0]
        y_data = data[1]
        z_data = data[2]
        x_space = np.linspace(min(x_data), max(x_data), 20)
        y_space= np.linspace(min(y_data), max(y_data), 20)
        X, Y = np.meshgrid(x_space, y_space)
        Z = func(np.array([X, Y]), *coefficients[i])

        ax = fig.add_subplot(4, 4, i + 1, projection = '3d')

        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, linewidth=1, antialiased=True, alpha=0.5)

        ax.scatter(x_data, y_data, z_data, c='r', s=10) # show data along with plotted surface

        ax.set_xlabel('OD90') # X axis data label
        ax.set_ylabel('OD135') # Y axis data label
        ax.set_zlabel('OD Measured') # Z axis data label

    plt.show()

def process_vial_data(calibration, param = None):
    """
        Data is structed as a list of lists. Each element in the outer list is a vial.
        That element is also a list, one for each point to be fit. The list contains 1 or more points.
        This function takes the median of those points and calculates the standard deviation, returning
        a similar structure.

        [vial0, vial1, vial2, ... ]
        vial = [point0, point1, point2, ...]
        point = [replicate0, replicate1, replicate2, ...]

    """
    raw_sets = calibration.get("raw", None)
    if raw_sets is None:
        print("Error processing calibration data - no raw sets found")
        sys.exit(1)

    calibration_data = {}
    vial_datas = []
    names = []
    for raw_set in raw_sets:
        if param is None or raw_set.get("param") == param:
            vial_datas.append(raw_set["vialData"])
            names.append(raw_set.get("param"))

    for i, vial_data in enumerate(vial_datas):
        medians = []
        standard_deviations = []
        for vial in vial_data:
            point_medians = []
            point_standard_deviations = []
            for point in vial:
                point_medians.append(np.median(point))
                point_standard_deviations.append(np.std(point))
            medians.append(point_medians)
            standard_deviations.append(point_standard_deviations)
        calibration_data[names[i]] = {"medians": medians, "standard_deviations": standard_deviations, "measured_data": calibration["measuredData"]}

    return calibration_data

def create_fit(coefficients, fit_name, fit_type, time_fit, params):
    return {"name": fit_name, "coefficients": coefficients, "type": fit_type, "timeFit": time_fit, "active": False, "params": params}

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
    parser.add_option('-n', '--calibration-name', action = 'store', dest = 'calname', help = "Name of the calibration.")
    parser.add_option('-g', '--get-calibration-names', action = 'store_true', dest = 'getnames', help = "Prints out all calibration names present on the eVOLVER.")
    parser.add_option('-a', '--ip', action = 'store', dest = 'ipaddress', help = "IP address of eVOLVER")
    parser.add_option('-t', '--fit-type', action = 'store', dest = 'fittype', help = "Valid options: sigmoid, linear, constant, 3d")
    parser.add_option('-f', '--fit-name', action = 'store', dest = 'fitname', help = "Desired name for the fit.")
    parser.add_option('-p', '--params', action = 'store', dest = 'params', help = "Desired parameter(s) to fit. Comma separated, no spaces")


    (options, args) = parser.parse_args()
    cal_name = options.calname
    get_names = options.getnames
    fit_type = options.fittype
    fit_name = options.fitname
    params = options.params

    if not options.ipaddress:
        print('Please specify ip address')
        parser.print_help()
        sys.exit(2)

    ip_address = 'http://' + options.ipaddress

    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(run, ip_address, 8081)

    if dpu_evolver_ns is None:
        print("Waiting for evolver connection...")

    while dpu_evolver_ns is None:
        pass

    if get_names:
        print("Getting calibration names...")
        dpu_evolver_ns.emit('getcalibrationnames', [], namespace = '/dpu-evolver')
    if cal_name:
        if fit_name is None:
            print("Please input a name for the fit!")
            parser.print_help()
            sys.exit(2)
        if fit_type not in VALID_FIT_TYPES:
            print("Invalid fit type!")
            parser.print_help()
            sys.exit(2)
        if params is None:
            print("Must provide at least 1 parameter!")
            parser.print_help()
            sys.exit(2)
        dpu_evolver_ns.emit('getcalibration', {'name':cal_name}, namespace='/dpu-evolver')
        params = params.strip().split(',')

    while not data_received:
        pass

    if cal_name is not None and not get_names:
        if fit_type == "sigmoid":
            fit = sigmoid_fit(calibration, fit_name, params)
        elif fit_type == "linear":
            fit = linear_fit(calibration, fit_name, params)
        elif fit_type == "constant":
            fit = constant_fit(calibration, params)
        elif fit_type == "3d":
            fit = three_dimension_fit(calibration, fit_name, params)

        update_cal = input('Update eVOLVER with calibration? (y/n): ')
        if update_cal == 'y':
            dpu_evolver_ns.emit('setfitcalibration', {'name': cal_name, 'fit': fit}, namespace = '/dpu-evolver')
