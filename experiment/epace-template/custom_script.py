#!/usr/bin/env python3

import numpy as np
import logging
import os.path
import time

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

    reservoir_vial = 0
    lagoon_vial = 1

    # Turbidostat Variables
    stop_after_n_curves = np.inf #set to np.inf to never stop, or integer value to stop diluting after certain number of growth curves
    OD_values_to_average = 6  # Number of values to calculate the OD average

    lower_thresh = [0.9, 0] # set the lower OD threshold (0s for chemostats)
    upper_thresh = [0.95, 0] # set the upper OD threshold (0s for chemostats)
    
    # Chemostat Variables
    start_time = [0, 0] #hours, set 0 to start immediately
    rate_config = [0.4, 0.5]  #Volumes/hr

    inducer_rate = [0.025, 0] #Volumes/hr - [pump 5, pump 6] - setting to 0 stops

    inducer_on = True # whether inducer is flowing or not

    ##### END OF USER DEFINED VARIABLES #####


    ##### Turbidostat Settings #####
    #Tunable settings for overflow protection, pump scheduling etc. Unlikely to change between expts

    time_out = 8 #(sec) additional amount of time to run efflux pump
    pump_wait = 3 # (min) minimum amount of time to wait between pump events
    turbidostat_vials = [reservoir_vial] # zero indexed list of vials to trigger turbidostat on

    ##### End of Turbidostat Settings #####

    ##### Chemostat Settings #####
    #Tunable settings for bolus, etc. Unlikely to change between expts

    bolus = 0.5 #mL, can be changed with great caution, 0.2 is absolute minimum
    bolus_slow = 0.1 #mL, can be changed with great caution, 0.2 is absolute minimum

    chemostat_vials = [0, 1] # zero indexed list of vials to trigger chemostat on
    ##### End of Chemostat Settings #####

    flow_rate = eVOLVER.get_flow_rate() #read from calibration file
    period_config = [0,0] #initialize array
    bolus_in_s = [0,0] #initialize array - calculated bolus for fast input pumps
    inducer_period = [0,0] #initialize array - calculated period for slow pumps
    bolus_slow_in_s = [0,0] #initialize array - calculated bolus for slow pumps

    ##### TURBIDOSTAT CODE BELOW #####

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

    # send fluidic command only if we are actually turning on any of the pumps
    if MESSAGE != ['--'] * 6:
        eVOLVER.fluid_command(MESSAGE)

        # your_FB_function_here() #good spot to call feedback functions for dynamic temperature, stirring, etc for ind. vials
    # your_function_here() #good spot to call non-feedback functions for dynamic temperature, stirring, etc.

    # end of turbidostat() fxn

    ##### CHEMOSTAT CODE BELOW #####

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

    # your_function_here() #good spot to call non-feedback functions for dynamic temperature, stirring, etc.
    if inducer_on:
        # calculate for inducer 1 - pump 5
        if inducer_rate[0] != 0:
            bolus_slow_in_s[0] = bolus_slow / float(flow_rate[4]) #calculate bolus
            inducer_period[0] = (3600 * bolus_slow)/(inducer_rate[0] * LAGOON_VOLUME) #calculate period
        
        # calculate for inducer 2 - pump 6
        if inducer_rate[1] != 0:
            bolus_slow_in_s[1] = bolus_slow / float(flow_rate[5]) #calculate bolus
            inducer_period[1] = (3600 * bolus_slow)/(inducer_rate[1] * LAGOON_VOLUME) #calculate period
    else:
        inducer_period = [0,0]
        bolus_slow_in_s = [0,0]
    eVOLVER.update_chemo(input_data, chemostat_vials, bolus_in_s, period_config, bolus_slow_in_s, inducer_period) #compares computed chemostat config to the remote one
    # end of chemostat() fxn


if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
    logger.info('Please run eVOLVER.py instead')
