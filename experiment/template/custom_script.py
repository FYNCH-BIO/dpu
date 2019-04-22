import eVOLVER_module
import numpy as np
import os.path
import time


# This code will operate eVOLVER as a pulsatile chemostat, with user-specified temperature, stir rate, dilution rate, dilution start time, and dilution start OD.
# The code waits for the specified time, permits the culture to grow up to the specified starting OD, then initiates repeated dilutions according to specified dilution rate.
# Last Updated: Chris Mancuso 07/24/18

def choose_name():
    ##### Sets name of experiment folder, make new name for each experiment, otherwise files will be overwritten

    ##### USER DEFINED FIELDS #####

    exp_name = 'test_expt'
    evolver_ip = '192.168.1.36'
    evolver_port = 8081
    return exp_name, evolver_ip, evolver_port

    ##### END OF USER DEFINED FIELDS #####

def test (OD_data, temp_data, vials, elapsed_time, exp_name):

    ##### USER DEFINED VARIABLES #####

    temp_input = 30 #degrees C, can be scalar or 16-value numpy array
    stir_input = 8 #try 8,10,12; can be scalar or 16-value numpy array

    lower_thresh = np.array([9999] * len(vials))
    upper_thresh = np.array([9999] * len(vials))
    # lower_thresh = np.array([0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2])
    # upper_thresh = np.array([0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.4])

    ##### END OF USER DEFINED VARIABLES #####


    ##### Calibration Values:
    # Be sure to check that OD_cal.txt and temp_calibration.txt are up to date
    # Additional calibration values below, remain the same between experiments

    time_out = 15 #(sec) additional amount of time to run efflux pump
    pump_wait = 3 # (min) minimum amount of time to wait between pump events
    control = np.power(2,range(0,32)) #vial addresses
    flow_rate = np.array([0.95,1.1,0.975,0.85,0.95,1.05,1.05,1.05,1.025,1.125,1.0,1.0,1.05,1.15,1.1,1.025]) #ml/sec, paste from pump calibration
    volume =  30 #mL, determined by straw length


    save_path = os.path.dirname(os.path.realpath(__file__)) #save path

    ##### End of Calibration Values


    ##### Turbidostat Control Code Below #####


    for x in vials: #main loop through each vial

        # Update temperature configuration files for each vial
        file_name =  "vial{0}_tempconfig.txt".format(x)
        tempconfig_path = os.path.join(save_path,exp_name,'temp_config',file_name)
        temp_config = np.genfromtxt(tempconfig_path, delimiter=',')

        if (len(temp_config) is 2): #set temp at the beginning of the experiment, can clone for subsequent temp changes
                if np.isscalar(temp_input):
                    temp_val = temp_input
                else:
                    temp_val = temp_input[x]

                text_file = open(tempconfig_path,"a+")
                text_file.write("{0},{1}\n".format(elapsed_time, temp_val))
                text_file.close()

        # Update turbidostat configuration files for each vial
        # initialize OD and find OD path

        file_name =  "vial{0}_ODset.txt".format(x)
        ODset_path = os.path.join(save_path,exp_name,'ODset',file_name)
        data = np.genfromtxt(ODset_path, delimiter=',')
        ODset = data[len(data)-1][1]

        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(save_path,exp_name,'OD',file_name)
        data = np.genfromtxt(OD_path, delimiter=',')
        average_OD = 0

        # Determine whether turbidostat dilutions are needed
        if len(data) > 7:
            # Take median to avoid outlier
            od_values_from_file = []
            for n in range(1,7):
                od_values_from_file.append(data[len(data)-n][1])
            average_OD = float(np.median(od_values_from_file))

            if (average_OD > upper_thresh[x]) and (ODset != lower_thresh[x]):
                text_file = open(ODset_path,"a+")
                text_file.write("{0},{1}\n".format(elapsed_time, lower_thresh[x]))
                text_file.close()
                ODset = lower_thresh[x]

            if (average_OD < (lower_thresh[x]+(upper_thresh[x] - lower_thresh[x])/2)) and (ODset != upper_thresh[x]):
                text_file = open(ODset_path,"a+")
                text_file.write("{0},{1}\n".format(elapsed_time, upper_thresh[x]))
                text_file.close()
                ODset = upper_thresh[x]

            if average_OD > ODset:

                time_in = - (np.log(lower_thresh[x]/average_OD)*volume)/flow_rate[x]

                if time_in > 20:
                    time_in = 20

                save_path = os.path.dirname(os.path.realpath(__file__))
                file_name =  "vial{0}_pump_log.txt".format(x)
                file_path = os.path.join(save_path,exp_name,'pump_log',file_name)
                data = np.genfromtxt(file_path, delimiter=',')
                last_pump = data[len(data)-1][0]
                if ((elapsed_time - last_pump)*60) >= pump_wait:
                    MESSAGE = {'pumps_binary':"{0:b}".format(control[x]), 'pump_time': time_in, 'efflux_pump_time': time_out, 'delay_interval': 0, 'times_to_repeat': 0, 'run_efflux': 1}
                    eVOLVER_module.fluid_command(MESSAGE, x, elapsed_time, pump_wait *60, exp_name, time_in, 'y')


    # end of test() fxn

def test_chemostat (OD_data, temp_data, vials, elapsed_time, exp_name):

    ##### USER DEFINED VARIABLES #####

    temp_input = 30 #degrees C, can be scalar or 16-value numpy array
    stir_input = 10 #try 8,10,12; see paper for rpm conversion, can be scalar or 16-value numpy array

    start_OD = 0 # ~OD600, set to 0 to start chemostate dilutions at any positive OD

    start_time1 = 0 #hours, set 0 to start immediately
    rate_config1 = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]) #UNITS of 1/hr, NOT mL/hr, so dilution rate ~ growth rate, set to 0 for unused vials.

    #start_timeN = XX #define as many as needed if successive rounds with different flow rates needed
    #rate_configN = XX #define as many as needed if successive rounds with different flow rates needed

    ##### END OF USER DEFINED VARIABLES #####


    ##### Calibration Values:
    # Be sure to check that OD_cal.txt and temp_calibration.txt are up to date
    # Additional calibration values below, remain the same between experiments

    control = np.power(2,range(0,32)) #vial addresses
    flow_rate = np.array([1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1,1.1]) #ml/sec, paste from pump calibration
    volume =  25 #mL, determined by straw length
    bolus = 500 #uL, can be changed with great caution, 200uL is absolute minimum
    period_config = np.array([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]) #initialize array
    save_path = os.path.dirname(os.path.realpath(__file__)) #save path

    bolus_in_s = flow_rate * (bolus / 1000)

    ##### End of Calibration Values


    ##### Chemostat Control Code Below #####


    for x in vials: #main loop through each vial

        # Update temperature configuration files for each vial
        file_name =  "vial{0}_tempconfig.txt".format(x)
        tempconfig_path = os.path.join(save_path,exp_name,'temp_config',file_name)
        temp_config = np.genfromtxt(tempconfig_path, delimiter=',')

        if (len(temp_config) is 2): #set temp at the beginning of the experiment, can clone for subsequent temp changes
                if np.isscalar(temp_input):
                    temp_val = temp_input
                else:
                    temp_val = temp_input[x]

                text_file = open(tempconfig_path,"a+")
                text_file.write("{0},{1}\n".format(elapsed_time, temp_val))
                text_file.close()

        # Update chemostat configuration files for each vial

        #initialize OD and find OD path
        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(save_path,exp_name,'OD',file_name)
        data = np.genfromtxt(OD_path, delimiter=',')
        average_OD = 0

        if len(data) > 7: #waits for seven OD measurements (couple minutes) for sliding window
            for n in range(1,6):
                average_OD = average_OD + (data[len(data)-n][1]/5)  #calculates average OD over a small window

            # set chemostat config path and pull current state from file
            file_name =  "vial{0}_chemoconfig.txt".format(x)
            chemoconfig_path = os.path.join(save_path,exp_name,'chemo_config',file_name)
            chemo_config = np.genfromtxt(chemoconfig_path, delimiter=',')
            last_chemoset = chemo_config[len(chemo_config)-1][0] #should t=0 initially, changes each time a new command is written to file
            last_chemophase = chemo_config[len(chemo_config)-1][1] #should be zero initially, changes each time a new command is written to file

            # once start time has passed and culture hits start OD, if no command has been written, write new chemostat command to file
            if ((elapsed_time > start_time1) & (average_OD > start_OD)):

                if  (last_chemophase == 0):

                    # calculate the period (i.e. frequency of dilution events) based on user specified growth rate and bolus size
                    if rate_config1[x] > 0:
                        period_config[x] = (3600*bolus)/((rate_config1[x])*volume)
                        period_config[x] = (period_config[x])*flow_rate[x]*(25/volume) #corrects for flow rates other than 1mL/sec and volumes other than 25mL
                        period_config[x] = period_config[x] / 1000 # converts to s
                    else: # if no dilutions needed, then just loops with no dilutions
                        period_config[x] = 0

                    print('Chemostat initiated in vial {0}'.format(x))
                    # writes command to chemo_config file, for storage
                    text_file = open(chemoconfig_path,"a+")
                    text_file.write("{0},1,{1}\n".format(elapsed_time,period_config[x])) #note that this sets chemophase to 1
                    text_file.close()

                ##### Sample code below for subsequent chemostat phases, be sure to update N in variable names etc.
                # if  ((last_chemophase == N-1) & (elapsed_time > start_timeN):

                #     # calculate the period (i.e. frequency of dilution events) based on user specified growth rate and bolus size
                #     if rate_configN[x] > 0:
                #         period_config[x] = (3600*bolus)/((rate_configN[x])*volume)
                #         period_config[x] = (period_config[x])*flow_rate[x]*(25/volume) #corrects for flow rates other than 1mL/sec and volumes other than 25mL

                #     else: # if no dilutions needed, then just loops with no dilutions
                #         period_config[x] = 0

                #     print 'Chemostat updated in vial %i' % (x)
                #     # writes command to chemo_config file, for storage
                #     text_file = open(chemoconfig_path,"a+")
                #     text_file.write("%f,N,%i\n" %  (elapsed_time,period_config[x])) #note that this sets chemophase to N, replace with integer value
                #     text_file.close()

        #end of main loop through vials

    #Update chemostat command after all vials are dealt with
    eVOLVER_module.update_chemo(vials, exp_name, bolus_in_s, control) #uses values stored in chemo_config files

    #Update stir rate for all vials
    if np.isscalar(stir_input):
        STIR_MESSAGE = [stir_input] * 16
    else:
        stir_val = np.array2string(stir_input, separator = ',')
        stir_val = stir_val.replace(' ','')
        stir_val = stir_val.replace('[','')
        stir_val = stir_val.replace(']','')
        STIR_MESSAGE = list(map(int, stir_val.split(',')))

    eVOLVER_module.stir_rate(STIR_MESSAGE)

    # end of test() fxn
