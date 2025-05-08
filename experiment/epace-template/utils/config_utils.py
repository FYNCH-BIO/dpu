import os
import pandas as pd
import numpy as np

#### UTILITIES FOR WORKING WITH CONFIG FILES ####
def validate_chemostat_schedule(schedule):
    """
    Validates that chemostat_schedule is well‑formed. 
    Each schedule dict must have:
      - 'OD_start'    (non‑neg number)
      - 'flow_rates'  (list of non‑neg numbers)
      - 'times'       (list of non‑neg numbers, ascending)
      - 'flow_rate_mode' ('stepwise' or 'linear')
    And for 'stepwise', len(times) must equal len(flow_rates).
    
    Raises:
        ValueError: on any validation failure, listing all errors.
    Returns:
        True: if no errors found.
    """
    required = {'OD_start','flow_rates','times','flow_rate_mode'}
    errors = []
    
    for vial_name, conf in schedule.items():
        # must be a dict
        if not isinstance(conf, dict):
            errors.append(f"• '{vial_name}': should be a dict")
            continue
        
        # check for missing keys
        missing = required - conf.keys()
        if missing:
            errors.append(f"• '{vial_name}' missing keys: {', '.join(missing)}")
            continue
        
        # OD_start
        val = conf['OD_start']
        if not isinstance(val, (int, float)) or val < 0:
            errors.append(f"• '{vial_name}': 'OD_start' must be a non‑negative number")
        
        # flow_rates
        fr = conf['flow_rates']
        if not isinstance(fr, (list, tuple)) or not fr:
            errors.append(f"• '{vial_name}': 'flow_rates' must be a non‑empty list")
        else:
            for r in fr:
                if not isinstance(r, (int, float)) or r < 0:
                    errors.append(f"• '{vial_name}': each flow rate must be a non‑neg number (got {r})")
                    break
        
        # times
        ts = conf['times']
        if not isinstance(ts, (list, tuple)) or not ts:
            errors.append(f"• '{vial_name}': 'times' must be a non‑empty list")
        else:
            for t in ts:
                if not isinstance(t, (int, float)) or t < 0:
                    errors.append(f"• '{vial_name}': each time must be a non‑neg number (got {t})")
                    break
            else:
                # check ascending
                if list(ts) != sorted(ts):
                    errors.append(f"• '{vial_name}': 'times' must be in ascending order")
        
        # flow_rate_mode
        mode = conf['flow_rate_mode']
        if mode not in ('stepwise','linear'):
            errors.append(f"• '{vial_name}': 'flow_rate_mode' must be 'stepwise' or 'linear' (got '{mode}')")
        
        # length check for stepwise
        if mode == 'stepwise' and isinstance(fr, (list,tuple)) and isinstance(ts, (list,tuple)):
            if len(ts) != len(fr):
                errors.append(
                    f"• '{vial_name}': for 'stepwise', len(times) ({len(ts)}) "
                    f"must equal len(flow_rates) ({len(fr)})"
                )
    
    if errors:
        raise ValueError("Chemostat schedule validation failed:\n" + "\n".join(errors))
    return True

def update_config(config_name, vial, current_config, exp_dir):
    """
    Update a configuration file with a new configuration.
    Args:
        vial (int): The vial number to identify the configuration file.
        config_name (str): The name of the configuration.
        current_config (list of str): The new configuration as a list of strings. The first position is the elapsed time.
        exp_dir (str): The directory where the configuration files are stored.
    Returns:
        None
    """

    config_path = os.path.join(exp_dir, f'{config_name}', f'vial{vial}_{config_name}.txt')
    
    with open(config_path, "a+") as text_file:
        line = ','.join(str(config) for config in current_config) # Convert the list to a string with commas as separators
        text_file.write(line+'\n') # Write the string to the file, including a newline character

def compare_configs(config_name, vial, current_config, exp_dir, ignore_time=True):
    """
    Compare the current configuration with the last configuration for a given variable and vial. Ignores the time in index 0.
    Args:
        config_name (str): The name of the variable.
        vial (int): The name of the vial.
        current_config (list of strings): The current configuration as a list of strings.
        exp_dir (str): The directory where the configuration files are stored.
        ignore_time (bool): Whether to ignore the time in index 0 when comparing configurations.
    Returns:
        bool: True if the current configuration is different from the last configuration, False otherwise.
    """
    # Turn the current_config into a list of strings
    current_config = [str(config) for config in current_config]

    # Open the config file
    file_name = f"vial{vial}_{config_name}.txt"
    if config_name == "gr":
        config_name = "growthrate"
    config_path = os.path.join(exp_dir, f'{config_name}', file_name)
    with open(config_path, 'r') as file:
        # Read all lines from the file
        lines = file.readlines()
        # Get the last line
        last_config = lines[-1].strip().split(',')
    
    # Check if config has changed
    if len(current_config) != len(last_config):
        return True
    for i in range(ignore_time, len(current_config)): # ignore the times in index 0
        if current_config[i] != last_config[i]:
            return True
    return False # If the arrays are the same, return False

if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
