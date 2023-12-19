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

    ##### A function that can implement chemostats and turbidostats in different vials
    
    OD_data = input_data['transformed']['od']

    ##### USER DEFINED VARIABLES #####

    # Turbidostat Variables
    lower_thresh = [0.9, 0] # set the lower OD threshold of the reservoir (0 for chemostat)
    upper_thresh = [0.95, 0] # set the upper OD threshold of the reservoir (0 for chemostat)
    
    # Chemostat Variables
    start_time = [0, 0] #hours, set 0 to start immediately
    rate_config = [0.5, 0.5]  #Volumes/hr

    #### Selection Variables #### - pump 5
    selection_start = 3 # hours, set 0 to start selection immediately at selection_initial_conc
    selection_stock_conc = 50 # X times minimum in-vial concentration - setting to 0 stops
    selection_initial_conc =  1 # X times in-vial concentration; 1X = minimum selection
    selection_final_conc = 10 # X times in-vial concentration
    selection_units = 'X' # default is X in-vial concentration
    # For example: a lagoon with chemostat running at 1 Volumes/hr / 40X inducer stock concentration = 0.025 Volumes/hr of inducer added
    # 0.025 Volumes/hr * 10mL LAGOON_VOLUME = 0.25mL of inducer stock added per hour (however the eVOLVER needs Volumes/hr)
    time_to_final = 72 # hours; time until final selection concentration is reached
    selection_change_start = 6 # hours; time to start changing inducer concentration
    print_selection = True # whether to print selection data to terminal

    #### Drift Variables #### - pump 6
    drift_expt_start = 0 # hours, set 0 to start drift immediately
    drift_stock_conc = 50 # X times final concentration - setting to 0 stops
    drift_interval = 8 # hours; time between periods of drift
    drift_length = 3 # hours; time that drift is fully on
    interval_modifier = 1 # hours; additional time added to drift_interval after each drift
    
    alternate_selection = True # whether to alternate between selection and drift; selectiion inducer will wash out during drift
    print_drift = True # whether to print drift data to terminal

    ##### END OF USER DEFINED VARIABLES #####
    
    reservoir_vial = 0 # Index of the reservoir vial
    lagoon_vial = 1 # Index of the lagoon vial
    selection_pump = 4 # Index of the selection pump (number of pump is 5)
    drift_pump = 5 # Index of the drift pump (number of pump is 6)

    ##### Turbidostat Settings #####
    #Tunable settings for overflow protection, pump scheduling etc. Unlikely to change between expts

    time_out = 8 #(sec) additional amount of time to run efflux pump
    pump_wait = 3 # (min) minimum amount of time to wait between pump events
    turbidostat_vials = [reservoir_vial] # zero indexed list of vials to trigger turbidostat on

    stop_after_n_curves = np.inf #set to np.inf to never stop, or integer value to stop diluting after certain number of growth curves
    OD_values_to_average = 6  # Number of values to take in to calculate the OD average

    ##### End of Turbidostat Settings #####

    ##### Chemostat Settings #####
    #Tunable settings for bolus, etc. Unlikely to change between expts

    bolus = 0.5 #mL, can be changed with great caution, 0.2 is absolute minimum
    bolus_slow = 0.1 #mL, can be changed with great caution

    chemostat_vials = [0, 1] # zero indexed list of vials to trigger chemostat on
    ##### End of Chemostat Settings #####

    flow_rate = eVOLVER.get_flow_rate() #read from calibration file
    period_config = [0,0] #initialize array
    bolus_in_s = [0,0] #initialize array - calculated bolus for fast input pumps

    ##### Inducer Settings #####
    step_increment = 0.2 # hours; time between each selection level change
    max_gap = 0.05 # hours; there is a gap greater than this time (ie for drift or a pause in experiment), the time doesn't count towards selection time
    ##### End of Inducer Settings #####

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

        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'OD', file_name)
        data = eVOLVER.tail_to_np(OD_path, OD_values_to_average)
        average_OD = 0

        # Determine whether turbidostat dilutions are needed
        #enough_ODdata = (len(data) > 7) #logical, checks to see if enough data points (couple minutes) for sliding window
        collecting_more_curves = (num_curves <= (stop_after_n_curves + 2)) #logical, checks to see if enough growth curves have happened

        if data.size != 0:
            # Take median to avoid outlier
            od_values_from_file = data[:,1]
            average_OD = float(np.median(od_values_from_file))

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

    for x in chemostat_vials: #main loop through each vial

        # Update chemostat configuration files for each vial

        #initialize OD and find OD path
        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'OD', file_name)
        data = eVOLVER.tail_to_np(OD_path, OD_values_to_average)
        average_OD = 0
        #enough_ODdata = (len(data) > 7) #logical, checks to see if enough data points (couple minutes) for sliding window

        if data.size != 0: #waits for seven OD measurements (couple minutes) for sliding window

            #calculate median OD
            od_values_from_file = data[:,1]
            average_OD = float(np.median(od_values_from_file))

            # set chemostat config path and pull current state from file
            file_name =  "vial{0}_chemo_config.txt".format(x)
            chemoconfig_path = os.path.join(eVOLVER.exp_dir, EXP_NAME,
                                            'chemo_config', file_name)
            chemo_config = np.genfromtxt(chemoconfig_path, delimiter=',')
            last_chemoset = chemo_config[len(chemo_config)-1][0] #should t=0 initially, changes each time a new command is written to file
            last_chemophase = chemo_config[len(chemo_config)-1][1] #should be zero initially, changes each time a new command is written to file
            last_chemorate = chemo_config[len(chemo_config)-1][2] #should be 0 initially, then period in seconds after new commands are sent

            # once start time has passed and culture hits start OD, if no command has been written, write new chemostat command to file
            if elapsed_time > start_time[x]:

                #calculate time needed to pump bolus for each pump
                bolus_in_s[x] = bolus/flow_rate[x + 2]
                

                # calculate the period (i.e. frequency of dilution events) based on user specified growth rate and bolus size
                if rate_config[x] > 0:
                    if x == reservoir_vial: # volume is set depending on the vial type
                        volume = VOLUME
                    else:
                        volume = LAGOON_VOLUME
                    period_config[x] = (3600*bolus)/((rate_config[x])*volume) #scale dilution rate by bolus size and volume
                else: # if no dilutions needed, then just loops with no dilutions
                    period_config[x] = 0

                if  (last_chemorate != period_config[x]):
                    print('Chemostat updated in vial {0}'.format(x))
                    logger.info('chemostat initiated for vial %d, period %.2f'
                                % (x, period_config[x]))
                    # writes command to chemo_config file, for storage
                    text_file = open(chemoconfig_path, "a+")
                    text_file.write("{0},{1},{2}\n".format(elapsed_time,
                                                           (last_chemophase+1),
                                                           period_config[x])) #note that this changes chemophase
                    text_file.close()
        else:
            logger.debug('not enough OD measurements for vial %d' % x)


    ################################
    ##### INDUCER CALCULATIONS #####
    ################################
    lagoon_V_h = rate_config[lagoon_vial] # lagoon Volumes/hr

    #### Inducer Functions ####
    def get_last_config(var_name, vial):
        """
        Retrieves the last configuration for a given variable name and vial number.
        Args:
            var_name (str): The name of the variable.
            vial (int): The vial number.
        Returns:
            tuple or numpy.ndarray: If the loaded configuration has more than one dimension, 
                returns the last configuration and the path to the configuration file. 
                Otherwise, returns the configuration and the path to the configuration file.
        """
        # Construct file name and config path
        file_name = f"vial{vial}_{var_name}_config.txt"
        config_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, f'{var_name}_config', file_name)

        # Load config from file
        config = np.genfromtxt(config_path, delimiter=',')
        # Get the last configuration from the loaded config
        if config.ndim != 1:
            return config_path,config[-1]
        else:
            return config_path,config

    def compare_configs(var_name, vial, current_config):
        """
        Compare the current configuration with the last configuration for a given variable and vial.
        Args:
            var_name (str): The name of the variable.
            vial (int): The name of the vial.
        Returns:
            bool: True if the current configuration is different from the last configuration, False otherwise.
        """
        config_path,last_config = get_last_config(var_name, vial) # get last configuration and path
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


    ################
    ## Drift Code ##
    ################

    #### Drift Config Handling ####
    current_config = np.array([elapsed_time, drift_stock_conc, drift_interval, drift_length, interval_modifier, alternate_selection]) # Define the current configuration
    config_change = compare_configs('drift', lagoon_vial, current_config) # Check if config has changed and write to file if it has

    # Print and log the drift config is updated
    if config_change:
        print(f'\nDrift Config updated, conc {current_config[1]}, interval {current_config[2]}, length {current_config[3]}, modifier {current_config[4]}, alternate_selection {current_config[5]}')
        logger.info(f'Drift Config updated, conc {current_config[1]}, interval {current_config[2]}, length {current_config[3]}, modifier {current_config[4]}, alternate_selection {current_config[5]}')

    #### Drift Inducer Logic ####
    drifting = False # initialize variable
    drift_rate = 0  # Volumes/hour; initializing the variable
    if elapsed_time >= drift_expt_start and drift_stock_conc != 0: # if drift has started
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

        # Config was changed, update start and end times to turn off drift
        if config_change and interval_count != 0: # if config was changed and not the first interval
            drift_end = round(elapsed_time, 3)
            drift_start = round(elapsed_time + drift_interval + interval_modifier * (interval_count - 1), 3)
            print(f'Config change, starting drift OFF cycle | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}\n')
            logger.info(f'Config change, starting drift OFF cycle | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
        
        # Experiment restart handling
        elif last_time + 1 < elapsed_time: # if the experiment has restarted after greater than 1 hr
            # Change the start and end times of the drift to match the new elapsed time
            drift_start = drift_start + (elapsed_time - last_time) # new start time
            drift_end = drift_end + (elapsed_time - last_time) # new end time
            print(f'\nDrift scheduling resuming | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            logger.info('Drift scheduling resuming | Start Time %.2f | Current Time %.2f | End Time %.2f' % (drift_start, elapsed_time, drift_end))

        ## Determine what our drift status is ##
        elif elapsed_time >= drift_start and drift_end <= drift_start: # Starting drift
            drifting = True
            drift_end = round((drift_start + drift_length), 3) # set the end of the drift
            if print_drift:
                print(f'\nDrift STARTing | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            interval_count += 1 # increment the number of intervals completed

            # Calculate an initial bolus to bring the concentration to the target
            if last_drift_conc < 1: # if the target concentration is higher than current concentration
                # calculate the bolus size using:: C_stock * V_stock + C_initial * V_initial = C_final * V_final
                CiVi = last_drift_conc * LAGOON_VOLUME
                CfVf = 1 * LAGOON_VOLUME # approximate value ignoring volume of stock added
                bolus = (CfVf - CiVi) / drift_stock_conc # in mL, bolus size of stock to add to induce drift
                time_in = bolus / float(flow_rate[drift_pump]) # time to add bolus
                time_in = round(time_in, 3)
                
                MESSAGE[drift_pump] = str(time_in) # set the pump message
                current_drift_conc = 1 # set the current concentration to the target
                if print_drift:
                    print(f'Drift inducer bolus added: {round(bolus, 3)}mL | New concentration: {current_drift_conc}X')

        elif drift_start <= elapsed_time < drift_end: # We are in a drift cycle
            if print_drift:
                print(f'DRIFTING | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')
            drifting = True
            current_drift_conc  = 1 # (approximate) current concentration of drift, the drift pump chemostat (pump 6) is set to maintain this

        elif elapsed_time >= drift_end: # We are not in a drift cycle
            drift_interval = drift_interval + interval_modifier * (interval_count - 1) # increase space between cycles each cycle
            drift_start = round((drift_end + drift_interval), 2) # set the start of the next cycle
            current_drift_conc = exponential(-lagoon_V_h, 1, elapsed_time - drift_end) # approximate concentration of drift inducer
            if print_drift:
                print(f'Drift OFF | approximate drift inducer {round(current_drift_conc, 3)}X | Start Time {drift_start} | Current Time {elapsed_time} | End Time {drift_end}')

        # writes drift data to drift_log file, for storage
        text_file = open(drift_log_path, "a+")
        text_file.write("{0},{1},{2},{3},{4}\n".format(elapsed_time, current_drift_conc, drift_start, drift_end, interval_count))
        text_file.close()

    elif drift_stock_conc != 0: # if there is no drift inducer
        logger.debug(f'Drift not initiated, start time {drift_start} | current time {elapsed_time}')

    #### Drift inducer calculations ####
    drift_rate = 0 # Volumes/hr of inducer - initializing the variable 
    if drift_stock_conc != 0 and elapsed_time >= drift_expt_start and drifting:
        #calculate the rate of the inducer
        drift_rate = lagoon_V_h / drift_stock_conc #Volumes/hr


    ####################
    ## Selection Code ##
    ####################
    selection_rate = 0 # Volumes/hour
    
    #### Selection Config Handling ####
    current_config = np.array([elapsed_time, selection_initial_conc, selection_final_conc, time_to_final, selection_change_start]) # Define the current configuration
    config_change = compare_configs('selection', lagoon_vial, current_config) # Check if config has changed and write to file if it has

    # Print and log the drift config is updated
    if config_change:
        print(f'\nSelection Config updated, selection_initial_conc {current_config[1]}, selection_final_conc {current_config[2]}, time_to_final {current_config[3]}, change_start {current_config[4]}')
        logger.info(f'\nSelection Config updated, selection_initial_conc {current_config[1]}, selection_final_conc {current_config[2]}, time_to_final {current_config[3]}, change_start {current_config[4]}')
    
    #### Selection Inducer Logic ####
    if elapsed_time >= selection_start and selection_stock_conc != 0: # if we are selecting
        
        ## Selection Log Handling ##
        file_name = f"vial{lagoon_vial}_selection_log.txt"
        selection_log_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'selection_log', file_name)
        last_line = eVOLVER.tail_to_np(selection_log_path, 1)[0]  # get last line of selection log
        # Selection log variables
        last_time = last_line[0]  # time of last selection calculation
        last_selection_conc = last_line[1]  # in X final concentration, calculated concentration of selection inducer at last time
        last_selection_time = last_line[2] # total time spent in this selection scheme
        last_selection_target = last_line[3] # target concentration of selection inducer
        # Initialize variables
        current_selection_conc = last_selection_conc 
        if last_selection_target != 0:
            selection_target = last_selection_target # in-vial concentration to reach in a given selection increment
        else:
            selection_target = selection_initial_conc        
        # Initialize selection time; counter for total time spent on this selection increment
        if config_change: # If we changed the config
            selection_time = 0  # reset the selection time
        else:
            selection_time = last_selection_time
        # Check if there was a time gap
        time_diff = elapsed_time - last_time # time since last selection log
        if time_diff > max_gap: # if there was a time gap
            time_diff = 0
                    
        ## Selection logic ##
        # If we are drifting and we are alternating selection with drift
        if drifting and alternate_selection: # Do not alter selection_rate (selection_rate = 0)
            # Calculate the current selection concentration as exponential decay
            current_selection_conc = exponential(-lagoon_V_h, last_selection_conc, time_diff) # exponential decay
            if print_selection:
                print(f'Selection OFF | approximate selection concentration: {round(current_selection_conc, 4)}X')
                logger.info(f'Selection OFF | approximate selection concentration: {round(current_selection_conc, 4)}X')

        # If we are currently changing selection
        elif elapsed_time >= selection_change_start and selection_final_conc != selection_initial_conc:
            selection_time += time_diff # add the time elapsed to the selection time total

            # Update the selection target
            if last_selection_target > selection_final_conc: # if the target is greater than the final
                selection_target = selection_final_conc # set the target to the final
            elif selection_time >= step_increment: # Every step_increment hours we are increasing the selection target
                selection_slope = (selection_final_conc - selection_initial_conc) / time_to_final
                selection_change = selection_slope * selection_time # a single step in the selection curve
                selection_target = last_selection_target + selection_change # update the target
                selection_time = 0  # reset the selection time
                if print_selection:
                    print(f'\nNew selection target: {round(selection_target, 3)}\n')
                    logger.info(f'New selection target: {round(selection_target, 3)}')
            
            # Calculate the current selection concentration
            selection_rate = (lagoon_V_h / selection_stock_conc) * selection_target #Volumes/hr
            current_selection_conc = inducer_concentration(lagoon_V_h, last_selection_conc, selection_target, time_diff)
            if print_selection:
                print(f'Selecting, approximate concentration: {round(current_selection_conc, 3)}X, selection_rate: {round(selection_rate, 3)}V/hr | selection_target: {round(selection_target, 3)}X')
                logger.info(f'Selecting, approximate concentration: {round(current_selection_conc, 3)}X')

        # If we are not linearly changing selection
        else:
            selection_rate = lagoon_V_h / selection_stock_conc  # Volumes/hr
            current_selection_conc = selection_initial_conc # we are not
            selection_target = selection_initial_conc

        # Log the current selection concentration
        text_file = open(selection_log_path, "a+")
        text_file.write("{0},{1},{2},{3}\n".format(elapsed_time, current_selection_conc, selection_time, selection_target))
        text_file.close()
    

    ######################################
    #### General Inducer Calculations ####
    ######################################
    inducer_rate = [selection_rate, drift_rate] # Volumes/hr of inducer - initializing the array - [pump 5, pump 6] 
    bolus_slow_in_s = [0,0] #initialize array - calculated bolus for slow pumps
    inducer_period = [0,0] #initialize array - calculated period for slow pumps

    # calculate for inducer 1 - pump 5
    if inducer_rate[0] != 0:
        bolus_slow_in_s[0] = bolus_slow / float(flow_rate[selection_pump]) #calculate bolus
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
