#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import numpy as np
from unittest import mock
import eVOLVER_module
import main_eVOLVER
import custom_script

eVOLVER_module.initialize_exp = mock.Mock()
eVOLVER_module.initialize_exp.return_value = 0.0, None
eVOLVER_module.fluid_command = mock.Mock()
eVOLVER_module.update_chemo = mock.Mock()
eVOLVER_module.stir_rate = mock.Mock()

logger = logging.getLogger('test')

def update_eVOLVER(OD_data, temp_data, elapsed_time, vials):
    logger.debug('elapsed time: %.4f hours' % elapsed_time)
    print("Time: {0} Hours".format(elapsed_time))

    if OD_data is not None and temp_data is not None:
        eVOLVER_module.parse_data(OD_data, elapsed_time,
                                  vials, exp_name, 'OD')
        eVOLVER_module.parse_data(temp_data, elapsed_time,
                                  vials, exp_name, 'temp')

        main_eVOLVER.OD_data = OD_data
        main_eVOLVER.temp_data = temp_data

        # make decision
        main_eVOLVER.custom_functions(elapsed_time, main_eVOLVER.exp_name)

        # save Variables
        eVOLVER_module.save_var(main_eVOLVER.exp_name,
                                main_eVOLVER.start_time,
                                np.zeros(len(vials)))

def get_options():
    description = 'Run a mock eVOLVER experiment from the command line'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('mock',
                        help='Path to test data (same directory format, '
                             'can be either a previous experiment or '
                             'generated data)')

    parser.add_argument('--vials',
                        type=int,
                        default=range(0, 16),
                        nargs='+',
                        help='Vials to run the tests on (default: 0-15)')
    parser.add_argument('--log-path',
                        default='evolver_test.log',
                        help='Path to the log file (default: %(default)s)')

    log_nolog = parser.add_mutually_exclusive_group()
    log_nolog.add_argument('--verbose', action='count',
                           default=0,
                           help='Increase logging verbosity level to DEBUG '
                                '(default: INFO)')
    log_nolog.add_argument('--quiet', action='store_true',
                           default=False,
                           help='Disable logging to file entirely')

    return parser.parse_args()

if __name__ == '__main__':
    options = get_options()

    # logging setup
    if options.quiet:
        logging.basicConfig(level=logging.CRITICAL + 10)
    else:
        if options.verbose == 0:
            level = logging.INFO
        elif options.verbose >= 1:
            level = logging.DEBUG
        logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] '
                            '- %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            filename=options.log_path,
                            level=level)

    exp_name, evolver_ip, evolver_port = custom_script.choose_name()
    vials = options.vials
    start_time, OD_initial = eVOLVER_module.initialize_exp(exp_name, vials,
                                                           evolver_ip,
                                                           evolver_port)
    main_eVOLVER.start_time = start_time
    main_eVOLVER.vials = options.vials
    main_eVOLVER.exp_name = exp_name

    # read mock data
    od_data_all = {}
    temp_data_all = {}
    for x in vials:
        file_name =  "vial{0}_OD.txt".format(x)
        od_path = os.path.join(options.mock, 'OD', file_name)
        od_data_all[x] = np.genfromtxt(od_path, delimiter=',')
        file_name =  "vial{0}_temp.txt".format(x)
        temp_path = os.path.join(options.mock, 'temp', file_name)
        temp_data_all[x] = np.genfromtxt(temp_path, delimiter=',')
    # keep track of the timepoints to use
    times = set()
    for x in vials:
        times = times.union(od_data_all[x][:, 0])
        times = times.union(temp_data_all[x][:, 0])

    # create output directory
    save_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.join(save_path, exp_name)
    if os.path.exists(dir_path):
        print('Please delete the old output directory (%s) and restart' %
              dir_path)
        logger.error('output directory %s exists already, exiting' %
                     dir_path)
        sys.exit(1)

    logger.debug('creating data directories')
    os.makedirs(os.path.join(dir_path, 'OD'))
    os.makedirs(os.path.join(dir_path, 'temp'))
    os.makedirs(os.path.join(dir_path, 'pump_log'))
    os.makedirs(os.path.join(dir_path, 'temp_config'))
    os.makedirs(os.path.join(dir_path, 'ODset'))
    os.makedirs(os.path.join(dir_path, 'chemo_config'))
    for x in vials:
        file_name =  "vial{0}_OD.txt".format(x)
        file_path = os.path.join(dir_path,'OD',file_name)
        text_file = open(file_path,"w")
        text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name,
                                                                    x,
                                                        time.strftime("%c")))
        text_file.close()

        file_name =  "vial{0}_temp.txt".format(x)
        file_path = os.path.join(dir_path,'temp',file_name)
        text_file = open(file_path,"w").close()

        file_name =  "vial{0}_tempconfig.txt".format(x)
        file_path = os.path.join(dir_path,'temp_config',file_name)
        text_file = open(file_path,"w")
        text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name,
                                                                    x,
                                                        time.strftime("%c")))
        text_file.write("0,0\n")
        text_file.close()

        file_name =  "vial{0}_pump_log.txt".format(x)
        file_path = os.path.join(dir_path,'pump_log',file_name)
        text_file = open(file_path,"w")
        text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name,
                                                                    x,
                                                        time.strftime("%c")))
        text_file.write("0,0\n")
        text_file.close()

        file_name =  "vial{0}_ODset.txt".format(x)
        file_path = os.path.join(dir_path,'ODset',file_name)
        text_file = open(file_path,"w")
        text_file.write("Experiment: {0} vial {1}, {2}\n".format(exp_name,
                                                                    x,
                                                        time.strftime("%c")))
        text_file.write("0,0\n")
        text_file.close()

        file_name =  "vial{0}_chemoconfig.txt".format(x)
        file_path = os.path.join(dir_path,'chemo_config',file_name)
        text_file = open(file_path,"w")
        text_file.write("0,0,0\n")
        text_file.write("0,0,0\n")
        text_file.close()

    for time in sorted([float(x) for x in times if str(x) != 'nan']):
        OD_data = np.empty(len(vials)) * np.nan
        temp_data = np.empty(len(vials)) * np.nan

        for x in vials:
            # do we have this timepoint for this vial?
            data = od_data_all[x]
            tpoint = data[data[:, 0] == time]
            if tpoint.shape[0] > 0:
                # we consider only the first matching timepoint
                OD_data[x] = tpoint[0, 1]
            data = temp_data_all[x]
            tpoint = data[data[:, 0] == time]
            if tpoint.shape[0] > 0:
                # we consider only the first matching timepoint
                temp_data[x] = tpoint[0, 1]

        update_eVOLVER(OD_data, temp_data, time, vials)
