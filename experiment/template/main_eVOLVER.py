#!/usr/bin/env python3

import time
import os.path
import logging
import argparse
import eVOLVER_module
import custom_script



logger = logging.getLogger('main')

def get_options():
    description = 'Run an eVOLVER experiment from the command line'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--always-yes', action='store_true',
                        default=False,
                        help='Answer yes to all questions '
                             '(i.e. continues from existing experiment, '
                             'overwrites existing data and blanks OD '
                             'measurements)')
    parser.add_argument('--log-path',
                        default='evolver.log',
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

def start_exp():
    stop_exp()
    logger.info('starting/restarting experiment')
    eVOLVER_module.restart_chemo()
    update_eVOLVER()

def stop_exp():
    logger.info('stopping all pumps')
    # stop all pumps, including chemostat commands
    eVOLVER_module.stop_all_pumps()

def update_eVOLVER():
    logger.debug('updating eVOLVER')
    global OD_data, temp_data
    # read and record OD
    elapsed_time = round((time.time() - start_time)/3600,4)
    logger.debug('elapsed time: %.4f hours' % elapsed_time)
    print("{0}: {1} Hours".format(custom_script.EXP_NAME,elapsed_time))
    OD_data, temp_data = eVOLVER_module.read_data(vials)
    if OD_data is not None and temp_data is not None:
        if OD_data == 'empty':
            print("Data Empty! Skipping data log...")
            logger.warning('empty OD data received! Skipping data log...')
        else:
            for x in vials:
                OD_data[x] = OD_data[x] - OD_initial[x]
        eVOLVER_module.parse_data(OD_data, elapsed_time, vials, 'OD')
        eVOLVER_module.parse_data(temp_data, elapsed_time, vials, 'temp')

        # make decision
        custom_functions(elapsed_time)

        # save Variables
        eVOLVER_module.save_var(start_time, OD_initial)

def custom_functions(elapsed_time):
    global OD_data, temp_data
    if OD_data == 'empty':
        print("UDP Empty, did not execute program!")
        logger.warning('empty OD data received! Skipping custom routine...')
    else:
        # load user script from custom_script.py
        if custom_script.OPERATION_MODE == 'turbidostat':
            custom_script.turbidostat(OD_data, temp_data, vials, elapsed_time)
        if custom_script.OPERATION_MODE == 'chemostat':
            custom_script.chemostat(OD_data, temp_data, vials, elapsed_time)

if __name__ == '__main__':
    options = get_options()

    print('\x1B]0;eVOLVER EXPERIMENT : PRESS Ctrl-C TO PAUSE\x07') #changes terminal tab title in OSX
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

    vials = range(0, 16)
    start_time, OD_initial = eVOLVER_module.initialize_exp(vials,
                                                 always_yes=options.always_yes)
    loop_start = time.time()
    while True:
        try:
            # run update if at least a 10th of second has passed
            loop_time = time.time()
            if loop_time - loop_start >= 0.1:
                update_eVOLVER()
                loop_start = time.time()
        except KeyboardInterrupt:
            try:
                print('Ctrl-C detected, pausing experiment')
                logger.warning('interrupt received, pausing experiment')
                stop_exp()
                while True:
                    key = input('Experiment paused. Press enter key to restart '
                                ' or hit Ctrl-C again to terminate experiment')
                    logger.warning('resuming experiment')
                    break
            except KeyboardInterrupt:
                print('Second Ctrl-C detected, shutting down')
                logger.warning('second interrupt received, terminating '
                               'experiment')
                stop_exp()
                print('Experiment stopped, goodbye!')
                logger.warning('experiment stopped, goodbye!')
                break
        except Exception as e:
            logger.critical('exception %s stopped the experiment' % str(e))
            stop_exp()
            print('Experiment stopped, goodbye!')
            logger.warning('experiment stopped, goodbye!')
            break
