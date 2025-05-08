import os
import math
from scipy import stats
import numpy as np
import pandas as pd

# MATH UTILITIES FOR CALCULATIONS
def exponential(flow_rate, conc0, time):
    """
    Calculate the exponential growth / decay of a substance over time.
    Args:
        flow_rate (float): The lagoon flow rate. Negative for decay, positive for growth.
        conc0 (float): The initial concentration of the substance.
        time (float): The time period over which the growth is calculated.
    Returns:
        float: The final concentration of the substance after the given time period.
    """
    return conc0 * math.e ** (flow_rate * time)

def inducer_concentration(flow_rate, conc0, conc_eq, time):
    """
    Calculate the concentration of the inducer in a chemostat at time t.
    Args:
        flow_rate (float): The lagoon flow rate.
        conc0 (float): Initial concentration of the inducer, in X at t0.
        conc_eq (float): Final (equilibrium) concentration, in X.
        time (float): Current time in hours since t0.
    Returns:
        float: Concentration of the inducer at time t, in X.
    """
    return conc_eq + (conc0 - conc_eq) * np.exp(-flow_rate * time)

# GROWTH RATE UTILITIES
def calc_growth_rate(vial, gr_start, elapsed_time, exp_dir, logger):
    """
    Calculate the growth rate of a culture in a vial based on OD data between turbidostat dilution events.
    Originally in eVOLVER.py
    Args:
        self: The current instance of the class.
        vial (int): The vial number.
        gr_start (float): The time at which to start calculating the growth rate.
        elapsed_time (float): The elapsed time of the experiment.
    """
    ODfile_name =  "vial{0}_OD.txt".format(vial)
    # Grab Data and make setpoint
    OD_path = os.path.join(exp_dir, 'OD', ODfile_name)
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
    gr_path = os.path.join(exp_dir, 'growthrate', file_name)
    text_file = open(gr_path, "a+")
    text_file.write("{0},{1}\n".format(elapsed_time, slope))
    text_file.close()
