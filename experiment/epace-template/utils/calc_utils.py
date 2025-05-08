import math
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
