#!/usr/bin/env python3

import numpy as np
import logging
import os.path
import time
import math

# logger setup
logger = logging.getLogger(__name__)

##### USER DEFINED GENERAL SETTINGS #####

# If using the GUI for data visualization, do not change EXP_NAME!
# only change if you wish to have multiple data folders within a single
# directory for a set of scripts
EXP_NAME = 'data'

# Port for the eVOLVER connection. You should not need to change this unless you have multiple applications on a single RPi.
EVOLVER_PORT = 5555

##### Identify pump calibration files, define initial values for temperature, stirring, volume, power settings

TEMP_INITIAL = [37] * 2 # degrees C, makes 2-value list
#Alternatively enter 2-value list to set different values
#TEMP_INITIAL = [30,37]

STIR_INITIAL = [11] * 2 #try 8,10,12 etc; makes 2-value list
#Alternatively enter 2-value list to set different values
#STIR_INITIAL = [7,8]

VOLUME = 30 #mL, determined by vial cap straw length
LAGOON_VOLUME = 10
OPERATION_MODE = 'hybrid' #use to choose between 'turbidostat' and 'chemostat' and other functions
# if using a different mode, name your function as the OPERATION_MODE variable

##### END OF USER DEFINED GENERAL SETTINGS #####

def hybrid(eVOLVER, input_data, vials, elapsed_time):
    
    """
    A function implements custom experiment handling for ePACE
        - Implements chemostats and turbidostats in vials
        - Handles drift and inducers
        - Interacts with eVOLVER.py
    """ 

    ##### USER DEFINED VARIABLES #####

    ## Turbidostat Variables ##
    lower_thresh = [0.9, 0] # set the lower OD threshold of the reservoir (0 for lagoon)
    upper_thresh = [0.95, 0] # set the upper OD threshold of the reservoir (0 for lagoon)
    
    ## Chemostat Variables ##
    start_time = [0, 0] # experiment time in hours; set 0 to start immediately
    chemo_OD_start = [0, 0] # lagoon OD to start chemostat, set 0 to start immediately
    chemo_initial_rate = [0.5, 0.5]  # Volumes/hr; see wiki for reservoir setting example
    chemo_final_rate = [1, 3] # Volumes/hr; typically reservoir >= 1/3 of lagoon to keep its volume constant
    chemo_time_to_final = [24, 100] # experiment time in hours; time until final flow rate is reached
    print_chemo = True # whether to print chemostat info to terminal

    ## Inducer 1 Variables ## - pump 5 - commonly mutation control via arabinose
    inducer1_start = 0 # experiment time in hours; set 0 to start immediately
    inducer1_OD_start = 0 # lagoon OD to start inducer1, set 0 to start immediately
    inducer1_stock_conc = 50 # X times minimum in-vial concentration - SETTING TO 0 STOPS
    # For example: a lagoon with chemostat running at 1 Volumes/hr / 40X inducer stock concentration = 0.025 Volumes/hr of inducer added
    # 0.025 Volumes/hr * 10mL LAGOON_VOLUME = 0.25mL of inducer stock added per hour (however the eVOLVER needs Volumes/hr)

    ## Drift Variables ## - pump 6
    drift_expt_start = 0 # experiment time in hours, set 0 to start drift immediately
    drift_OD_start = 0 # lagoon OD to start drift, set 0 to start immediately
    drift_stock_conc = 50 # X times final concentration - SETTING TO 0 STOPS
    initial_drift_bolus = True # Whether to add an initial bolus of drift inducer to bring lagoon to 1X concentration immediately on starting drift
    print_drift = True # whether to print drift data to terminal
    # Drift Cycling Variables
    drift_cycling = False # Whether to do scheduled drift cycles; set to False to control drift manually through setting drift_stock_conc
    max_drift_cycles = 2 # number of drift cycles to run before stopping; changing mid-experiment will reset count to 0 - setting to 0 stops
    drift_interval = 6 # hours; time between periods of drift
    drift_length = 3 # hours; time that drift is fully on
    interval_modifier = 0 # hours; additional time added to drift_interval after each drift - count is NOT reset when drift_cycle_num is changed mid experiment

    ##### END OF USER DEFINED VARIABLES #####

    ##### ADVANCED SETTINGS #####
    ## Indices ##
    reservoir_vial = 0 # Index of the reservoir vial
    lagoon_vial = 1 # Index of the lagoon vial
    inducer1_pump = 4 # Index of the inducer1 pump (number of pump is 5)
    drift_pump = 5 # Index of the drift pump (number of pump is 6)

    ## General Fluidics Settings ##
    flow_rate = eVOLVER.get_flow_rate() #read from calibration file
    bolus_fast = 0.5 #mL, can be changed with great caution, 0.2 is absolute minimum
    bolus_slow = 0.1 #mL, can be changed with great caution

    step_increment = 0.2 # hours; time between each flow rate change
    max_gap = 0.1 # hours; time gap to ignore for flow rate changes (ie a pause in experiment)
    ## End of General Fluidics Settings ##

    ## Turbidostat Settings ##
    #Tunable settings for overflow protection, pump scheduling etc. Unlikely to change between expts
    time_out = 8 #(sec) additional amount of time to run efflux pump
    pump_wait = 3 # (min) minimum amount of time to wait between pump events
    turbidostat_vials = [reservoir_vial] # zero indexed list of vials to trigger turbidostat on

    stop_after_n_curves = np.inf #set to np.inf to never stop, or integer value to stop diluting after certain number of growth curves
    OD_values_to_average = 6  # Number of values to take in to calculate the OD average
    ## End of Turbidostat Settings ##

    ## Chemostat Settings ##
    #Tunable settings for bolus, etc. Unlikely to change between expts
    chemostat_vials = [0, 1] # zero indexed list of vials to trigger chemostat on
    ## End of Chemostat Settings ##

    ## Advanced Inducer 1 Settings ##
    # Variables for linearly changing inducer1 concentration over time
    inducer1_initial_conc =  1 # X times in-vial concentration; 1X = minimum inducer1
    inducer1_final_conc = 1 # X times in-vial concentration
    time_to_final = 100 # experiment time in hours; time until final inducer1 concentration is reached
    inducer1_change_start = 6 #  experiment time in hours; time to start changing inducer concentration
    print_inducer1 = False # whether to print inducer1 data to terminal
    alternate_inducer1 = False # whether to alternate between inducer1 and drift; inducer 1 will wash out during drift
    
    ##### END OF ADVANCED SETTINGS #####

    ##################################
    #### GENERAL HELPER FUNCTIONS ####
    ##################################
    def get_last_line(var_name, vial):
        """
        Retrieves the last line of the file for a given variable name and vial number.
        Args:
            var_name (str): The name of the variable.
            vial (int): The vial number.
        Returns:
            tuple or numpy.ndarray: Returns the last line of the file and the path to the file.
        """
        # Construct file name and path
        file_name = f"vial{vial}_{var_name}.txt"
        file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, f'{var_name}', file_name)
        # Load last line from file
        file = eVOLVER.tail_to_np(file_path, 1)[0] # get last line
        # Get the last line from the loaded file
        if file.ndim != 1:
            return file_path,file[-1]
        else:
            return file_path,file

    def compare_configs(var_name, vial, current_config):
        """
        Compare the current configuration with the last configuration for a given variable and vial.
        Args:
            var_name (str): The name of the variable.
            vial (int): The name of the vial.
            current_config (list): The current configuration.
        Returns:
            bool: True if the current configuration is different from the last configuration, False otherwise.
        """
        config_path,last_config = get_last_line(var_name+'_config', vial) # get last configuration and path
        # Check if config has changed
        if not np.array_equal(last_config[1:], current_config[1:]): # ignore the times, see if arrays are the same
            # Write the updated configuration to the config file
            with open(config_path, "a+") as text_file:
                line = ','.join(str(config) for config in current_config) # Convert the list to a string with commas as separators
                text_file.write(line+'\n') # Write the string to the file, including a newline character
            return True # If the arrays are not the same, return True
        else:
            return False # If the arrays are the same, return False

    # Function for exponential decay
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
        
    def stepped_rate_modification(step_time, step_increment, initial_value, final_value, time_to_final, current_rate):
        """
        Calculates the new target flow rate for a fluid based on the time passed since the last step.
        Args:
            step_time (float): Time since last flow rate change, in hours.
            step_increment (float): Time between each flow rate change, in hours.
            initial_value (float): Initial flow rate value.
            final_value (float): Final target flow rate value.
            time_to_final (float): Total time to reach the final value from the initial value, in hours.
            current_rate (float): Current flow rate value.
        Returns:
            tuple: The new target flow rate ('new_rate') and the updated step time ('step_time').
        """
        if initial_value == final_value:
            raise ValueError("Initial value and final value should not be equal.")
        if step_time < 0 or step_increment <= 0 or time_to_final <= 0:
            raise ValueError("Time values must be positive.")

        # Check if the current rate is already at or beyond the final value
        if (initial_value < final_value and current_rate >= final_value) or (initial_value > final_value and current_rate <= final_value):
            return final_value, step_time

        # Calculate new rate if step_time is sufficient for a rate change
        if step_time >= step_increment:
            slope = (final_value - initial_value) / time_to_final
            increment = slope * step_time
            new_rate = current_rate + increment
            return new_rate, 0

        return current_rate, step_time # if nothing else, return the same target and time


    # Get ODs for use in experiment start thresholding
    vial_ODs = []
    for x in chemostat_vials:
        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'OD', file_name)
        data = eVOLVER.tail_to_np(OD_path, OD_values_to_average)
        if data.size != 0: # Check if data is not empty
            od_values_from_file = data[:,1]
            average_OD = float(np.median(od_values_from_file)) # Take median to avoid outlier
        else:
            average_OD = np.nan
        vial_ODs.append(average_OD)
    # lagoon_OD = vial_ODs[lagoon_vial]
    lagoon_OD = 0


    ################################
    #### TURBIDOSTAT CODE BELOW ####
    ################################

    # fluidic message: initialized so that no change is sent
    MESSAGE = ['--'] * 6
    for x in turbidostat_vials: #main loop through each vial

        # Update turbidostat configuration files for each vial
        # initialize OD and find OD path

        file_name =  "vial{0}_ODset.txt".format(x)
        ODset_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'ODset', file_name)
        data = np.genfromtxt(ODset_path, delimiter=',')
        ODset = data[len(data)-1][1]
        ODsettime = data[len(data)-1][0]
        num_curves=len(data)/2;

        average_OD = vial_ODs[x]

        # Determine whether turbidostat dilutions are needed
        #enough_ODdata = (len(data) > 7) #logical, checks to see if enough data points (couple minutes) for sliding window
        collecting_more_curves = (num_curves <= (stop_after_n_curves + 2)) #logical, checks to see if enough growth curves have happened

        if not np.isnan(average_OD):

            #if recently exceeded upper threshold, note end of growth curve in ODset, allow dilutions to occur and growthrate to be measured
            if (average_OD > upper_thresh[x]) and (ODset != lower_thresh[x]):
                text_file = open(ODset_path, "a+")
                text_file.write("{0},{1}\n".format(elapsed_time,
                                                   lower_thresh[x]))
                text_file.close()
                ODset = lower_thresh[x]
                # calculate growth rate
                eVOLVER.calc_growth_rate(x, ODsettime, elapsed_time)

            #if have approx. reached lower threshold, note start of growth curve in ODset
            if (average_OD < (lower_thresh[x] + (upper_thresh[x] - lower_thresh[x]) / 3)) and (ODset != upper_thresh[x]):
                text_file = open(ODset_path, "a+")
                text_file.write("{0},{1}\n".format(elapsed_time, upper_thresh[x]))
                text_file.close()
                ODset = upper_thresh[x]

            #if need to dilute to lower threshold, then calculate amount of time to pump
            if average_OD > ODset and collecting_more_curves:

                time_in = - (np.log(lower_thresh[x]/average_OD)*VOLUME)/flow_rate[x + 2]

                if time_in > 20:
                    time_in = 20

                time_in = round(time_in, 2)

                file_name =  "vial{0}_pump_log.txt".format(x)
                file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME,
                                         'pump_log', file_name)
                data = np.genfromtxt(file_path, delimiter=',')
                last_pump = data[len(data)-1][0]
                if ((elapsed_time - last_pump)*60) >= pump_wait: # if sufficient time since last pump, send command to Arduino
                    logger.info('turbidostat dilution for vial %d' % x)
                    # influx pump
                    MESSAGE[x + 2] = str(time_in)
                    # efflux pump
                    MESSAGE[x] = str(time_in + time_out)

                    file_name =  "vial{0}_pump_log.txt".format(x)
                    file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'pump_log', file_name)

                    text_file = open(file_path, "a+")
                    text_file.write("{0},{1}\n".format(elapsed_time, time_in))
                    text_file.close()
        else:
            logger.debug('not enough OD measurements for vial %d' % x)

    # end of turbidostat() fxn


    ################################
    ##### CHEMOSTAT CODE BELOW #####
    ################################
    period_config = [0,0] #initialize array
    bolus_in_s = [0,0] #initialize array - calculated bolus for fast input pumps
    current_chemo_rate = [0,0] #initialize array - rate of chemostat flow at current time

    for x in chemostat_vials: #main loop through each vial
        ## Chemostat Config Handling ##
        # Check if chemostat config has changed
        current_config = [elapsed_time, chemo_initial_rate[x], chemo_final_rate[x], chemo_time_to_final[x]]
        config_change = compare_configs('chemo', x, current_config) # Check if config has changed and write to file if it has
        # Print and log the drift config is updated
        if config_change:
            print(f"Vial {x} chemostat config changed| Initial Rate: {chemo_initial_rate[x]} | Final Rate: {chemo_final_rate[x]} | Time to Final: {chemo_time_to_final[x]}")
            logger.info(f"Vial {x} chemostat config changed| Initial Rate: {chemo_initial_rate[x]} | Final Rate: {chemo_final_rate[x]} | Time to Final: {chemo_time_to_final[x]}")

        ## Chemostat Log Handling ##
        # set chemostat config path and pull current state from file
        chemolog_path,chemo_log = get_last_line('chemo_log', x)
        last_time = chemo_log[0] #should t=0 initially, changes each time a new command is written to file
        last_rate = chemo_log[1] #Volumes/hr; chemostat flow rate
        last_step_time = chemo_log[2] # hours; time since last flow rate change

        ## Initialize Variables ##
        if last_rate != 0:
            current_chemo_rate[x] = last_rate # in-vial concentration to reach in a given inducer1 increment
        else:
            current_chemo_rate[x] = chemo_initial_rate[x] # Volumes/hr; Initial chemostat flow rate
        if config_change: # If we changed the config
            step_time = 0  # reset the step time
        else:
            step_time = last_step_time # step time is the same as the last step time
        time_diff = elapsed_time - last_time # time since last chemo_log
        if time_diff > max_gap: # if there was a time gap, don't add to step_time
            time_diff = 0

        ## Chemostat Logic ##
        if (elapsed_time >= start_time[x]) and ((vial_ODs[x] >= chemo_OD_start[x]) or (chemo_OD_start[x] == 0)): # Are we starting chemostat?
            # calculate the period (i.e. frequency of dilution events) based on user specified growth rate and bolus size
            if x == reservoir_vial: # volume is set depending on the vial type
                volume = VOLUME
            else:
                volume = LAGOON_VOLUME
            #calculate time needed to pump bolus for each pump
            bolus_in_s[x] = bolus_fast/flow_rate[x + 2]

            # If we are linearly changing chemostat flow rate
            if chemo_final_rate[x] != chemo_initial_rate[x]:
                step_time += time_diff # time since last flow rate change
                # Modify flow rate and step time
                current_chemo_rate[x], step_time = stepped_rate_modification(step_time, step_increment,
                                                                            chemo_initial_rate[x], chemo_final_rate[x],
                                                                            chemo_time_to_final[x], current_chemo_rate[x])
                # Write to chemo_log file for storage
                text_file = open(chemolog_path, "a+")
                text_file.write(f'{elapsed_time},{current_chemo_rate[x]},{step_time}\n')
                text_file.close()

            # Calculate the current chemo period
            if current_chemo_rate[x] > 0:
                period_config[x] = (3600*bolus_fast)/((current_chemo_rate[x])*volume) #scale dilution rate by bolus size and volume
            else:
                period_config[x] = 0
            
            # Read outs
            if current_chemo_rate[x] != last_rate:
                logger.info(f'\nNew chemostat rate in vial {x}: {round(current_chemo_rate[x], 3)} | period: {round(period_config[x], 3)}s | bolus (per period): {round(bolus_in_s[x], 3)}s')
                if print_chemo:
                    print(f'\nNew chemostat rate in vial {x}: {round(current_chemo_rate[x], 3)} | period: {round(period_config[x], 3)}s | bolus (per period): {round(bolus_in_s[x], 3)}s')
        
        else: # If we are not yet starting the lagoon
            if print_chemo:
                print(f"Chemostat not started in vial {x} | start_time = {start_time[x]} | chemo_OD_start = {chemo_OD_start[x]} | vial_OD = {vial_ODs[x]}")
            logger.info(f"Chemostat not started in vial {x} | start_time = {start_time[x]} | chemo_OD_start = {chemo_OD_start[x]} | vial_OD = {vial_ODs[x]}")
           

    ################################
    ##### INDUCER CALCULATIONS #####
    ################################
    lagoon_V_h = current_chemo_rate[lagoon_vial] # lagoon Volumes/hr; initialize variable

    ################
    ## Drift Code ##
    ################
    drifting = False # initialize variable
 
    #### Drift Config Handling ####
    current_config = np.array([elapsed_time, drift_stock_conc, drift_interval, drift_length, interval_modifier, alternate_inducer1]) # Define the current configuration
    config_change = compare_configs('drift', lagoon_vial, current_config) # Check if config has changed and write to file if it has

    # Print and log the drift config is updated
    if config_change:
        print(f'\nDrift Config updated, conc {current_config[1]}, interval {current_config[2]}, length {current_config[3]}, modifier {current_config[4]}, alternate_inducer1 {current_config[5]}')
        logger.info(f'Drift Config updated, conc {current_config[1]}, interval {current_config[2]}, length {current_config[3]}, modifier {current_config[4]}, alternate_inducer1 {current_config[5]}')

    #### Drift scheduling ####
    if (elapsed_time >= drift_expt_start) and ((lagoon_OD >= drift_OD_start) or (drift_OD_start == 0)): # if drift scheduling has started
        # set drift log path and pull last state from file
        file_name =  "vial{0}_drift_log.txt".format(lagoon_vial)
        drift_log_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'drift_log', file_name)
        last_line = eVOLVER.tail_to_np(drift_log_path, 1)[0] # get last line of drift log

        # Drift log variables
        last_time = last_line[0] # time of last drift calculation
        last_drift_conc = last_line[1] # in X final concentration, calculated concentration of drift inducer at last time
        drift_start = last_line[2] # start of last round of drift
        drift_end = last_line[3] # end of last round of drift
        interval_count = last_line[4] # number of intervals completed, also used with interval_modifier to set interval length over time

        current_drift_conc = 0 # in X final concentration, calculated concentration of current drift inducer

        ## Drift Start and End Time Updates ##
        # Config was changed, update start and end times to turn off drift
        if config_change and interval_count != 0: # if config was changed and not the first interval
            drift_end = round(elapsed_time, 3)
            drift_start = round(elapsed_time + drift_interval + interval_modifier * (interval_count - 1), 3)
            print(f'Config change, starting drift OFF cycle | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}\n')
            logger.info(f'Config change, starting drift OFF cycle | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
        # Update drift_start and drift_end for the first interval to account for drift_OD_start and drift_expt_start
        elif (drift_start == 0) and (drift_end == 0): # if this is the first interval and drift scheduling has started
            drift_start = round(elapsed_time, 3) # starting drift from current time, rather than the experiment start time
            drift_end = round(elapsed_time + drift_interval, 3)
        # Experiment time gap handling
        if time_diff > max_gap: 
            # Change the start and end times of the drift to match the new elapsed time
            drift_start = drift_start + time_diff # new start time
            drift_end = drift_end + time_diff # new end time
            print(f'\nTime gap greater than {max_gap} | Drift scheduling resuming | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            logger.info(f'\nTime gap greater than {max_gap} | Drift scheduling resuming | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')

        ## Drift Logic ##
        # If we are manually turning drift on or off    
        if not drift_cycling:
            if round(last_drift_conc, 3) != 0 and drift_stock_conc == 0: # Drift inducer is off, but there is a concentration in the lagoon
                current_drift_conc = exponential(-lagoon_V_h, 1, elapsed_time - drift_end) # therefore drift conc is in exponential decay
                if print_drift:
                    print(f'MANUAL DRIFT OFF | Drift inducer washing out | approximate drift inducer {round(current_drift_conc, 3)}X')
                logger.info(f'MANUAL DRIFT OFF | Drift inducer washing out | approximate drift inducer {round(current_drift_conc, 3)}X')
            elif drift_stock_conc != 0: # If we are drifting
                drifting = True
                current_drift_conc = 1 # set the current concentration to the target     
                if last_drift_conc < 1 and initial_drift_bolus: # Should we add an initial bolus to bring the concentration to 1X?
                    # calculate the bolus size using:: C_stock * V_stock + C_initial * V_initial = C_final * V_final
                    CiVi = last_drift_conc * LAGOON_VOLUME
                    CfVf = 1 * LAGOON_VOLUME # approximate value ignoring volume of stock added
                    calculated_bolus = (CfVf - CiVi) / drift_stock_conc # in mL, bolus size of stock to add to induce drift
                    time_in = calculated_bolus / float(flow_rate[drift_pump]) # time to add bolus
                    time_in = round(time_in, 3)
                    MESSAGE[drift_pump] = str(time_in) # set the pump message
                    if print_drift:
                        print(f'Drift inducer bolus added: {round(calculated_bolus, 3)}mL | Approximate concentration: {current_drift_conc}X')
                    logger.info(f'Drift inducer bolus added: {round(calculated_bolus, 3)}mL | Approximate concentration: {current_drift_conc}X')
                elif last_drift_conc < 1: # if we are not adding an initial bolus, calculate the concentration of the inducer
                    current_drift_conc = inducer_concentration(lagoon_V_h, last_drift_conc, 1, time_diff)

                if print_drift and (last_drift_conc != 1): # only print manual drift one time
                    print(f'MANUAL DRIFT ON | Approximate conc {round(current_drift_conc, 3)}X')
                logger.info(f'MANUAL DRIFT ON | Approximate conc {round(current_drift_conc, 3)}')

        # Check if max drift cycles has been reached
        elif (interval_count >= max_drift_cycles) and (elapsed_time >= drift_end): # if we are in the last cycle of drift, stop afterwards
            current_drift_conc = exponential(-lagoon_V_h, 1, elapsed_time - drift_end) # approximate concentration of drift inducer
            logger.info(f'Drift ENDED | Maximum drift cycles reached: {max_drift_cycles} | Current conc {round(current_drift_conc, 3)}')
            if print_drift and round(current_drift_conc, 3) != 0:
                print(f'Drift ENDED | Maximum drift cycles reached: {max_drift_cycles} | Current conc {round(current_drift_conc, 3)}')

        # Starting drift
        elif (elapsed_time >= drift_start) and (drift_end <= drift_start): 
            drifting = True
            drift_end = round((drift_start + drift_length), 3) # set the end of the drift
            interval_count += 1 # increment the number of intervals completed
            logger.info(f'\nDrift STARTing | Cycle {interval_count} | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            if print_drift:
                print(f'\nDrift STARTing | Cycle {interval_count} | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')

            # Calculate an initial bolus to bring the concentration to the target
            if last_drift_conc < 1 and initial_drift_bolus: # Should we add an initial bolus to bring the concentration to 1X?
                # calculate the bolus size using:: C_stock * V_stock + C_initial * V_initial = C_final * V_final
                CiVi = last_drift_conc * LAGOON_VOLUME
                CfVf = 1 * LAGOON_VOLUME # approximate value ignoring volume of stock added
                calculated_bolus = (CfVf - CiVi) / drift_stock_conc # in mL, bolus size of stock to add to induce drift
                time_in = calculated_bolus / float(flow_rate[drift_pump]) # time to add bolus
                time_in = round(time_in, 3)
                
                MESSAGE[drift_pump] = str(time_in) # set the pump message
                current_drift_conc = 1 # set the current concentration to the target
                if print_drift:
                    print(f'Drift inducer bolus added: {round(calculated_bolus, 3)}mL | New concentration: {current_drift_conc}X')
                logger.info(f'Drift inducer bolus added: {round(calculated_bolus, 3)}mL | New concentration: {current_drift_conc}X')

        # Currently drifting
        elif (drift_start <= elapsed_time < drift_end):
            if print_drift:
                print(f'DRIFTING | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            drifting = True
            current_drift_conc = 1 # (approximate) current concentration of drift, the drift pump chemostat (pump 6) is set to maintain this

        # Not drifting
        elif elapsed_time >= drift_end:
            drift_interval = drift_interval + interval_modifier * (interval_count - 1) # increase space between cycles each cycle
            drift_start = round((drift_end + drift_interval), 2) # set the start of the next cycle
            current_drift_conc = exponential(-lagoon_V_h, 1, elapsed_time - drift_end) # approximate concentration of drift inducer
            if print_drift:
                print(f'Drift OFF | approximate drift inducer {round(current_drift_conc, 3)}X | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')

        # writes drift data to drift_log file, for storage
        text_file = open(drift_log_path, "a+")
        text_file.write("{0},{1},{2},{3},{4}\n".format(elapsed_time, current_drift_conc, drift_start, drift_end, interval_count))
        text_file.close()
    elif (drift_stock_conc != 0) and ((elapsed_time < drift_expt_start) or (lagoon_OD < drift_OD_start)):
        logger.info(f'Drift not initiated, drift_expt_start {drift_expt_start} |  drift_OD_start {drift_OD_start} | lagoon_OD {lagoon_OD}')

    #### Drift inducer calculations ####
    drift_rate = 0 # Volumes/hr of inducer - initializing the variable 
    if drift_stock_conc != 0 and elapsed_time >= drift_expt_start and drifting:
        #calculate the rate of the inducer
        drift_rate = lagoon_V_h / drift_stock_conc #Volumes/hr


    ####################
    ## Inducer 1 Code ##
    ####################
    inducer1_rate = 0 # Volumes/hour
    
    #### Inducer 1 Config Handling ####
    current_config = np.array([elapsed_time, inducer1_initial_conc, inducer1_final_conc, time_to_final, inducer1_change_start]) # Define the current configuration
    config_change = compare_configs('inducer1', lagoon_vial, current_config) # Check if config has changed and write to file if it has

    # Print and log the inducer1 config is updated
    if config_change:
        if print_inducer1:
            print(f'\nInducer 1 Config updated, inducer1_initial_conc {current_config[1]}, inducer1_final_conc {current_config[2]}, time_to_final {current_config[3]}, change_start {current_config[4]}')
        logger.info(f'\nInducer 1 Config updated, inducer1_initial_conc {current_config[1]}, inducer1_final_conc {current_config[2]}, time_to_final {current_config[3]}, change_start {current_config[4]}')
    
    #### Inducer 1 Logic ####
    if (elapsed_time >= inducer1_start) and ((lagoon_OD >= inducer1_OD_start) or (inducer1_OD_start == 0)) and (inducer1_stock_conc != 0): # if we are inducing
        
        ## Inducer 1 Log Handling ##
        file_name = f"vial{lagoon_vial}_inducer1_log.txt"
        inducer1_log_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'inducer1_log', file_name)
        last_line = eVOLVER.tail_to_np(inducer1_log_path, 1)[0]  # get last line of inducer1 log
        # Inducer 1 log variables
        last_time = last_line[0]  # time of last inducer1 calculation
        last_inducer1_conc = last_line[1]  # in X final concentration, calculated concentration of inducer1 inducer at last time
        last_inducer1_time = last_line[2] # total time spent in this inducer1 scheme
        last_inducer1_target = last_line[3] # target concentration of inducer1 inducer

        ## Initialize Variables ##
        current_inducer1_conc = last_inducer1_conc 
        if last_inducer1_target != 0:
            inducer1_target = last_inducer1_target # in-vial concentration to reach in a given inducer1 increment
        else:
            inducer1_target = inducer1_initial_conc        
        # Initialize inducer1 time; counter for total time spent on this inducer1 increment
        if config_change: # If we changed the config
            inducer1_time = 0  # reset the inducer1 time
        else:
            inducer1_time = last_inducer1_time
        # Check if there was a time gap
        time_diff = elapsed_time - last_time # time since last inducer1 log
        if time_diff > max_gap: # if there was a time gap
            time_diff = 0
                    
        ## Inducer 1 logic ##
        # If we are drifting and we are alternating inducer1 with drift
        if drifting and alternate_inducer1: # Do not alter inducer1_rate (inducer1_rate = 0)
            # Calculate the current inducer1 concentration as exponential decay
            current_inducer1_conc = exponential(-lagoon_V_h, last_inducer1_conc, time_diff) # exponential decay
            if print_inducer1:
                print(f'Inducer 1 OFF | approximate inducer1 concentration: {round(current_inducer1_conc, 4)}X')
            logger.info(f'Inducer 1 OFF | approximate inducer1 concentration: {round(current_inducer1_conc, 4)}X')

        # If we are currently changing inducer1
        elif elapsed_time >= inducer1_change_start and inducer1_final_conc != inducer1_initial_conc:
            inducer1_time += time_diff # add the time elapsed to the inducer1 time total

            # Update the inducer1 target
            if last_inducer1_target > inducer1_final_conc: # if the target is greater than the final
                inducer1_target = inducer1_final_conc # set the target to the final
            elif inducer1_time >= step_increment: # Every step_increment hours we are increasing the inducer1 target
                inducer1_slope = (inducer1_final_conc - inducer1_initial_conc) / time_to_final
                inducer1_change = inducer1_slope * inducer1_time # a single step in the inducer1 curve
                inducer1_target = last_inducer1_target + inducer1_change # update the target
                inducer1_time = 0  # reset the inducer1 time
                if print_inducer1:
                    print(f'\nNew inducer1 target: {round(inducer1_target, 3)}\n')
                logger.info(f'New inducer1 target: {round(inducer1_target, 3)}')
            
            # Calculate the current inducer1 concentration
            inducer1_rate = (lagoon_V_h / inducer1_stock_conc) * inducer1_target #Volumes/hr
            current_inducer1_conc = inducer_concentration(lagoon_V_h, last_inducer1_conc, inducer1_target, time_diff)
            if print_inducer1:
                print(f'Inducer 1 ON, approximate concentration: {round(current_inducer1_conc, 3)}X, inducer1_rate: {round(inducer1_rate, 3)}V/hr | inducer1_target: {round(inducer1_target, 3)}X')
            logger.info(f'Inducer 1 ON, approximate concentration: {round(current_inducer1_conc, 3)}X')

        # If we are not linearly changing inducer1
        else:
            inducer1_rate = lagoon_V_h / inducer1_stock_conc  # Volumes/hr
            current_inducer1_conc = inducer1_initial_conc
            inducer1_target = inducer1_initial_conc
            logger.info(f'Inducer 1 ON, inducer1_rate: {round(inducer1_rate, 3)}V/hr')
            if print_inducer1:
                print(f'Inducer 1 ON, inducer1_rate: {round(inducer1_rate, 3)}V/hr')

        # Log the current inducer1 concentration
        text_file = open(inducer1_log_path, "a+")
        text_file.write("{0},{1},{2},{3}\n".format(elapsed_time, current_inducer1_conc, inducer1_time, inducer1_target))
        text_file.close()
        
    elif (inducer1_stock_conc != 0) and ((elapsed_time < inducer1_start) or (lagoon_OD < inducer1_OD_start)):
        logger.info(f'Inducer1 not initiated, start time {inducer1_start} | inducer1_OD_start {inducer1_OD_start} | lagoon_OD {lagoon_OD}')
    

    ######################################
    #### General Inducer Calculations ####
    ######################################
    inducer_rate = [inducer1_rate, drift_rate] # Volumes/hr of inducer - initializing the array - [pump 5, pump 6] 
    bolus_slow_in_s = [0,0] #initialize array - calculated bolus for slow pumps
    inducer_period = [0,0] #initialize array - calculated period for slow pumps

    # calculate for inducer 1 - pump 5
    if inducer_rate[0] != 0:
        bolus_slow_in_s[0] = bolus_slow / float(flow_rate[inducer1_pump]) #calculate bolus
        inducer_period[0] = (3600 * bolus_slow)/(inducer_rate[0] * LAGOON_VOLUME) #calculate period
    
    # calculate for inducer 2 - pump 6
    if inducer_rate[1] != 0:
        bolus_slow_in_s[1] = bolus_slow / float(flow_rate[drift_pump]) #calculate bolus
        inducer_period[1] = (3600 * bolus_slow)/(inducer_rate[1] * LAGOON_VOLUME) #calculate period
    
    ##### End of Inducer Calculations #####

    # send fluidic command only if we are actually turning on any of the pumps
    if MESSAGE != ['--'] * 6:
        eVOLVER.fluid_command(MESSAGE)

    eVOLVER.update_chemo(input_data, chemostat_vials, bolus_in_s, period_config, bolus_slow_in_s, inducer_period) #compares computed chemostat config to the remote one
    # end of chemostat() fxn


if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
    logger.info('Please run eVOLVER.py instead')
