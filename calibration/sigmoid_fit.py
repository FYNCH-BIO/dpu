import sys
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, leastsq
from scipy.linalg import lstsq
import scipy, scipy.optimize

data_file = "od_data.xlsx"

def sigmoid(x, a, b, c, d):
    return a + (b - a)/(1 + (10**((c-x)*d)))

def sigmoid_fit(df):
    coefficients = []
    measured_data = []
    medians = []
    titles = []

    for i in df.eV.unique():
        eV = df[df.eV == i]
        vialNum = len(eV.smart_sleeve.unique()) # number of vials in this eV calibration
        eV_print = []

        for v in eV.smart_sleeve.unique():
            vial = eV[eV.smart_sleeve == v]

            titles.append(f'eVOLVER:{i} Vial:{v}')

            measured_data.append(list(vial.standard))
            medians.append(list(vial.median_adc))

            paramsig, paramlin = curve_fit(sigmoid, vial.standard, vial.median_adc, p0 = [62721, 62721, 0, -1], maxfev=1000000000)
            paramsig = list(np.around(np.array(paramsig), decimals=3))
            eV_print.append(paramsig)
            coefficients.append(paramsig)
        eV_print = f'\neVOLVER {i} Copy + Paste:\n{eV_print}' + '}],\n'
        print(eV_print)

    # print(coefficients,"\n\n")

    graph_2d_data(
        sigmoid, measured_data, medians, coefficients, 
        "OD fit", 'sigmoid', 0, max(measured_data[0]), 500, titles)

def graph_2d_data(func, measured_data, medians, coefficients, fit_name, fit_type, space_min, space_max, space_step, titles):
    linear_space = np.linspace(space_min, space_max, space_step)

    fig, ax = plt.subplots(2, 2)
    fig.suptitle("Fit Name: " + fit_name)
    for i in range(4):
        ax[i // 2, (i % 2)].plot(measured_data[i], medians[i], 'o', markersize=3, color='black')
        # ax[i // 2, (i % 2)].errorbar(measured_data[i], medians[i], yerr=standard_deviations[i], fmt='none')
        # print(func(linear_space, *coefficients[i]))
        ax[i // 2, (i % 2)].plot(linear_space, func(linear_space, *coefficients[i]), markersize = 1.5, label = None)
        ax[i // 2, (i % 2)].set_title(titles[i])
        ax[i // 2, (i % 2)].ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    plt.subplots_adjust(hspace = 0.6)
    plt.show()


if __name__ == '__main__':
    df = pd.read_excel(data_file)

    sigmoid_fit(df)

