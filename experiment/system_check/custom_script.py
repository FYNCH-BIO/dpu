#!/usr/bin/env python3

import numpy as np
import logging
import os.path
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

save_path = os.path.dirname(os.path.realpath(__file__)) #save path


# logger setup
logger = logging.getLogger(__name__)

##### USER DEFINED GENERAL SETTINGS #####

#set new name for each experiment, otherwise files will be overwritten
EXP_NAME = 'system_check'
EVOLVER_IP = input('What is the IP address of the eVOLVER? (look on touchscreen): ')
EVOLVER_PORT = 8081

##### Identify pump calibration files, define initial values for temperature, stirring, volume, power settings

TEMP_INITIAL = [0] * 16 #degrees C, makes 16-value list
#Alternatively enter 16-value list to set different values
#TEMP_INITIAL = [30,30,30,30,32,32,32,32,34,34,34,34,36,36,36,36]

STIR_INITIAL = [0] * 16 #try 8,10,12 etc; makes 16-value list
#Alternatively enter 16-value list to set different values
#STIR_INITIAL = [7,7,7,7,8,8,8,8,9,9,9,9,10,10,10,10]

VOLUME =  25 #mL, determined by vial cap straw length
OD_POWER = 4095 #must match value used for OD calibration
PUMP_CAL_FILE = 'pump_cal.txt' #tab delimited, mL/s with 16 influx pumps on first row, etc.
OPERATION_MODE = 'custom_function' #use to choose between 'turbidostat' and 'chemostat' functions
# if using a different mode, name your function as the OPERATION_MODE variable

##### END OF USER DEFINED GENERAL SETTINGS #####

def custom_function(eVOLVER, input_data, vials, elapsed_time):
    if elapsed_time < 0.01:
        overwrite_serial = False
        signed_by = input('Initials of who is performing the diagnostics: ')

        vp_serial = input("What is the serial number of the Vial Platform?: ")
        ss_serial = input("What is the serial number of the Smart Sleeves?: ")
        fb_serial = input("What is the serial number of the Fluidic Box?: ")

        pump_number = input('How many sets of 16-pumps are setup on this eVOLVER (1,2,3)? ')
        if pump_number == "" :
            input('Please enter a number: ')
        pump_number = int(pump_number)

        pp_serial = []
        for x in range(pump_number):
            pp_serial.append(input("What is the serial number of the Peristaltic Pumps, set {0}?: ".format(x)))

        print(pp_serial)

        vial_loading = input("Are 20 mL of water loaded into each Smart Sleeve (w/ stir bar)? (y/n): ")
        if vial_loading == 'y':
            milk_ready = input("Do you have ~10 mL of milk ready? (y/n): " )
            if milk_ready:
                print('Ready to start system test!')
            else:
                print("Please get a bit of milk for OD diagnostics.")
                exit()
        else:
            print("Please get vials ready before experiment.")
            exit()

        ## Stir diagnostics
        print("Starting STIR Diagnostics")
        stir_diagnostics = [0] * 16
        broken_stir = []
        ## Run through each fan and press enter if only one stirring
        for n in vials:
            STIR = [0] * 16
            STIR[n] = 8
            eVOLVER.update_stir_rate(STIR, True)
            stir_status = input('Vial {0} Stir ON? (press ENTER if OK, n if not OK): '.format(n))
            if stir_status != 'n':
                stir_diagnostics[n] = 1
            else:
                broken_stir.append([n])
        ## Resume strring for all fans
        STIR = [8] * 16
        eVOLVER.update_stir_rate(STIR, True)

        if not broken_stir:
            print('All stirring reported to be working.')
        else:
            print('Please fix the following motors, then re-run diagnostics:')
            print(broken_stir)

        print("STIR Diagnostics Finished.")

        ## PUMP diagnostics
        print("Starting PUMP Diagnostics")

        pump_diagnostics = [0] * pump_number * 16
        broken_pumps = []
        PUMPS = [x for x in range(pump_number * 16)]
        ## Run through each fan and press enter if only one stirring
        for n in PUMPS:
            PUMP_STATUS = [0] * pump_number * 16
            PUMP_STATUS[n] = 30
            eVOLVER.fluid_command(PUMP_STATUS)
            pump_status = input('Pump {0} ON? (press ENTER if OK, n if not OK): '.format(n))
            if pump_status != 'n':
                pump_diagnostics[n] = 1
            else:
                broken_pumps.append([n])
        ## Resume strring for all fans
        PUMP_STATUS = [0] * pump_number * 16
        eVOLVER.fluid_command(PUMP_STATUS)

        if not broken_pumps:
            print('All pumps reported to be working.')
        else:
            print('Please fix the following pumps, then re-run diagnostics:')
            print(broken_pumps)


        print("PUMP Diagnostics Finished.")
        print("Resetting connection to clear input queue...")
        eVOLVER.reset_connection()
        time.sleep(1)

        print("Starting OD Diagnostics...")
        values_averaged = 5
        for n in range(values_averaged):
            eVOLVER.grab_data(20)
            print("Collecting initial data points ({0}/5)...".format(n+1))

        average_OD90_water = [0] * 16
        average_OD135_water = [0] * 16

        for x in vials:
            file_name =  "vial{0}_OD90_raw.txt".format(x)
            OD90_path = os.path.join(save_path, EXP_NAME, 'OD90_raw', file_name)

            file_name =  "vial{0}_OD135_raw.txt".format(x)
            OD135_path = os.path.join(save_path, EXP_NAME, 'OD135_raw', file_name)

            OD90_data = np.genfromtxt(OD90_path, delimiter=',')
            od_values_from_file = []
            for n in range(1,values_averaged):
                od_values_from_file.append(OD90_data[len(OD90_data)-n][1])
            average_OD90_water[x] = float(np.mean(od_values_from_file))

            OD135_data = np.genfromtxt(OD135_path, delimiter=',')
            od_values_from_file = []
            for n in range(1,values_averaged):
                od_values_from_file.append(OD135_data[len(OD135_data)-n][1])
            average_OD135_water[x] = float(np.mean(od_values_from_file))

        print(average_OD90_water)
        print(average_OD135_water)

        input("Finished collecting initial data. Press ENTER after spiking 100 uL of milk.")
        eVOLVER.reset_connection()
        for n in range(5):
            eVOLVER.grab_data(20)
            print("Collecting data points ({0}/5)...".format(n+1))


        average_OD90_milk = [0] * 16
        average_OD135_milk = [0] * 16
        delta_OD90 = [0] * 16
        delta_OD135 = [0] * 16

        for x in vials:
            file_name =  "vial{0}_OD90_raw.txt".format(x)
            OD90_path = os.path.join(save_path, EXP_NAME, 'OD90_raw', file_name)

            file_name =  "vial{0}_OD135_raw.txt".format(x)
            OD135_path = os.path.join(save_path, EXP_NAME, 'OD135_raw', file_name)

            OD90_data = np.genfromtxt(OD90_path, delimiter=',')
            od_values_from_file = []
            for n in range(1,values_averaged):
                od_values_from_file.append(OD90_data[len(OD90_data)-n][1])
            average_OD90_milk[x] = float(np.mean(od_values_from_file))
            delta_OD90[x] = average_OD90_milk[x] - average_OD90_water[x]

            OD135_data = np.genfromtxt(OD135_path, delimiter=',')
            od_values_from_file = []
            for n in range(1,values_averaged):
                od_values_from_file.append(OD135_data[len(OD135_data)-n][1])
            average_OD135_milk[x] = float(np.mean(od_values_from_file))
            delta_OD135[x] = average_OD135_milk[x] - average_OD135_water[x]

        print(average_OD90_water)
        print(average_OD90_milk)

        print(average_OD135_water)
        print(average_OD135_milk)

        for x in vials:
            print('Vial {0}   OD90:{1}   OD135:{2}'.format(x,delta_OD90[x],delta_OD135[x]))

        print('Starting Temperature Diagnostics...')
        measured_temp = input("Current actual room temperature (C)?: ")

        eVOLVER.reset_connection()

        print('Recording room temperature from OD readings...')
        tempcal_path = os.path.join(save_path,EXP_NAME, 'temp_calibration.txt')
        temp_cal = np.genfromtxt(tempcal_path, delimiter=',')

        room_temp = [0] * 16
        for x in vials:

            file_name =  "vial{0}_temp.txt".format(x)
            TEMP_path = os.path.join(save_path, EXP_NAME, 'temp', file_name)

            TEMP_data = np.genfromtxt(TEMP_path, delimiter=',')
            temp_values_from_file = []
            for n in range(1,values_averaged):
                temp_values_from_file.append(TEMP_data[len(TEMP_data)-n][1])
            room_temp[x] = float((np.mean(temp_values_from_file) - temp_cal[1][x])/temp_cal[0][x])

        room_temp = np.around(room_temp)

        print('Setting temperature to 1500...')

        TEMP_SET = [0] * 16
        for x in vials:
            TEMP_SET[x] = (temp_cal[0][x] *1500) + temp_cal[1][x]

            file_name =  "vial{0}_temp_config.txt".format(x)
            temp_config_path = os.path.join(save_path, EXP_NAME, 'temp_config', file_name)

            text_file = open(temp_config_path, "a+")
            text_file.write("{0},{1}\n".format(elapsed_time,
                                               TEMP_SET[x]))
            text_file.close()


        print('Waiting 30 minutes for temperature to equilibriate...')
        for n in range(90): # 90 cycles
            eVOLVER.grab_data(20)

        high_temp = [0] * 16
        for x in vials:

            file_name =  "vial{0}_temp.txt".format(x)
            TEMP_path = os.path.join(save_path, EXP_NAME, 'temp', file_name)

            TEMP_data = np.genfromtxt(TEMP_path, delimiter=',')
            temp_values_from_file = []
            for n in range(1,values_averaged):
                temp_values_from_file.append(TEMP_data[len(TEMP_data)-n][1])
            high_temp[x] = float((np.mean(temp_values_from_file) - temp_cal[1][x])/temp_cal[0][x])

        high_temp = np.around(high_temp)

        print('Temperature recorded!')

        print('Returning Temperature back to Room Temp')
        eVOLVER.update_temperature([2500]*16, True)

        print(room_temp)
        print(high_temp)

        in1 = []
        eff = []
        in2 = []
        if pump_number >= 1:
            in1 = pp_serial[0]
        else:
            in1 = 'N/A'
        if pump_number >= 2:
            eff = pp_serial[1]
        else:
            eff = 'N/A'

        if pump_number == 3:
            in2 = pp_serial[2]
        else:
            in2 = 'N/A'


        now = datetime.now()

        log_data_prompt = input('Want to log the data on Google Sheets? WARNING: Must have the appropriate hash file to access: (y/n)')

        if log_data_prompt == 'y':
            # use creds to create a client to interact with the Google Drive API
            scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name('evolver-quality-control-f5ec138ddaad.json', scope)
            client = gspread.authorize(creds)

            sheet = client.open("eVOLVER Quality Control").worksheet('Sys Check')

            list_of_registered = sheet.get_all_records()

            list_of_registered = sheet.get_all_records()
            starting_entry = len(list_of_registered)+2

            print('Data logging....')
            for x in vials:
                vial_data = [vp_serial,
                            ss_serial,
                            fb_serial,
                            in1,
                            eff,
                            in2,
                            x,
                            'OK',
                            OD_POWER,
                            average_OD90_water[x],
                            average_OD90_milk[x],
                            delta_OD90[x],
                            average_OD135_water[x],
                            average_OD135_milk[x],
                            delta_OD135[x],
                            measured_temp,
                            room_temp[x],
                            high_temp[x],
                            signed_by,
                            now.strftime("%Y_%m_%d__%H_%M_%S")]

                sheet.insert_row(vial_data, starting_entry)
                print('Data logged.')
        else:
            print('Data not logged!')

        exit()


# def your_function_here(): # good spot to define modular functions for dynamics or feedback

if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
