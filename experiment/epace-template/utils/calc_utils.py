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
def calc_growth_rate(vial, vial_type, volume, gr_start, elapsed_time, exp_dir, logger):
    """
    Calculate the growth rate of a culture in a vial based on OD data between turbidostat dilution events.
    Originally in eVOLVER.py
    Args:
        vial (int): Vial number
        vial_type (str): Type of vial ('reservoir' or 'lagoon')
        volume (float): Volume of the vial in liters
        gr_start (float): Start time for growth rate calculation in hours
        elapsed_time (float): Elapsed time in hours
        exp_dir (str): Experiment directory path
        logger: Logger object for logging messages
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

    if vial_type == 'reservoir':
        # Calculate the growth rate in the reservoir
        # using the time-weighted average chemostat flow rate
        avg_chemo_rate = time_weighted_avg_chemostat_rate(vial, gr_start, elapsed_time, exp_dir)
        slope = slope + avg_chemo_rate
        
    # Save slope to file
    file_name =  "vial{0}_gr.txt".format(vial)
    gr_path = os.path.join(exp_dir, 'growthrate', file_name)
    text_file = open(gr_path, "a+")
    text_file.write("{0},{1}\n".format(elapsed_time, slope))
    text_file.close()

def time_weighted_avg_chemostat_rate(vial, window_start, window_end, exp_dir):
    """
    Calculate the time-weighted average chemostat flow rate between window_start and window_end.
    If window_end exceeds the last log entry, assume the rate stays constant at that last value.
    """
    # load chemostat log file
    filename = os.path.join(exp_dir, 'chemo_log', f'vial{vial}_chemo_log.txt')
    df = pd.read_csv(filename, header=None, names=['elapsed_time', 'flow_rate', 'step_time'])

    times = df['elapsed_time'].values
    rates = df['flow_rate'].values

    # extend with a final "time" at window_end and rate equal to the last rate
    if window_end > times[-1]:
        times = list(times) + [window_end]
        rates = list(rates) + [rates[-1]]

    weighted_sum = 0.0
    total_duration = window_end - window_start
    if total_duration <= 0:
        raise ValueError("window_end must be greater than window_start")

    # loop over each segment
    for i in range(len(times) - 1):
        seg_start, seg_end = times[i], times[i+1]
        # compute overlap of [seg_start, seg_end] with [window_start, window_end]
        overlap_start = max(seg_start, window_start)
        overlap_end   = min(seg_end,   window_end)
        if overlap_end > overlap_start:
            duration = overlap_end - overlap_start
            weighted_sum += rates[i] * duration

    return float(weighted_sum / total_duration)
