import numpy as np
import os.path
import pandas as pd

#### FUNCTIONS FOR READING FILES ####
def tail_to_np(path, window=10, BUFFER_SIZE=512):
    """
    Reads file from the end and returns a numpy array with the data of the last 'window' lines.
    Alternative to np.genfromtxt(path) by loading only the needed lines instead of the whole file.
    """
    try:
        f = open(path, 'rb')
    except OSError as e:
        print(f"Unable to open file: {path}\n\tError: {e}")
        return np.asarray([])

    if window == 0:
        return np.asarray([])

    f.seek(0, os.SEEK_END)
    remaining_bytes = f.tell()
    size = window + 1  # Read one more line to avoid broken lines
    block = -1
    data = []

    while size > 0 and remaining_bytes > 0:
        if remaining_bytes - BUFFER_SIZE > 0:
            # Seek back one whole BUFFER_SIZE
            f.seek(block * BUFFER_SIZE, os.SEEK_END)
            # read BUFFER
            bunch = f.read(BUFFER_SIZE)
        else:
            # file too small, start from beginning
            f.seek(0, 0)
            # only read what was not read
            bunch = f.read(remaining_bytes)

        bunch = bunch.decode('utf-8')
        data.append(bunch)
        size -= bunch.count('\n')
        remaining_bytes -= BUFFER_SIZE
        block -= 1

    f.close()
    data = ''.join(reversed(data)).splitlines()[-window:]

    if len(data) < window:
        # Not enough data
        return np.asarray([])

    for c, v in enumerate(data):
        data[c] = v.split(',')

    try:
        data = np.asarray(data, dtype=np.float64)
        return data
    except:
        try:
            return np.asarray(data)
        except e:
            print(f"tail_to_np: Unable to read file as numpy array: {path}\n\tError: {e}")
            return np.asarray([])

def get_last_n_lines(var_name, vial, n_lines, exp_dir):
    """
    Retrieves the last lines of the file for a given variable name and vial number.
    Args:
        var_name (str): The name of the variable.
        vial (int): The vial number.
        n_lines (int): The number of lines to retrieve.
    Returns:
        numpy.ndarray: Returns the last n lines of the file.
    """
    # Construct file name and path
    file_name = f"vial{vial}_{var_name}.txt"
    if var_name == "gr":
        var_name = "growthrate"
    file_path = os.path.join(exp_dir, f'{var_name}', file_name)

    try:
        data = tail_to_np(file_path, n_lines)
        if data.ndim == 0:
            return data[0]
        return data
    except Exception as e:
        print(f"Unable to read file using tail_to_np: {file_path}.\n\tError: {e}")
        try:
            data = np.genfromtxt(file_path, delimiter=',', skip_header=0)  # Adjust delimiter as necessary
            return data[-n_lines:]
        except Exception as e:
            print(f"Unable to read file using np.genfromtxt: {file_path}.\n\tError: {e}")
            return np.asarray([])
        
def labeled_last_n_lines(var_name, vial, n_lines, exp_dir):
    """
    Gets the last n lines of a variable in a vial's data, then labels them with the header from the CSV file.
    Args:
        var_name (str): The name of the variable.
        vial (int): The vial number.
        n_lines (int): The number of lines to retrieve.
    Returns:
        pd.DataFrame: The last n lines of the variable, with headers.
    """
    file_name = f"vial{vial}_{var_name}.txt"
    path = os.path.join(exp_dir, var_name, file_name)

    with open(path, 'r') as file:
        heading = file.readline().strip().split(',')
    
    data = get_last_n_lines(var_name, vial, n_lines, exp_dir)
    if data.ndim == 0:
        return pd.DataFrame(data, columns=[heading])
    return pd.DataFrame(data, columns=heading)

#### FUNCTIONS FOR WRITING FILES ####
def update_log(vial, log_name, elapsed_time, message, exp_dir):
    """
    Updates a log file with a new message.
    Args:
        vial (int): The vial number to identify the log file.
        elapsed_time (float): The elapsed time of the experiment.
        message (str): The message to write to the log file.
        exp_dir (str): The directory where the log files are stored.
        log_name (str): The name of the log file.
    Returns:
        None
    """
    file_name = f"vial{vial}_{log_name}.txt"
    file_path = os.path.join(exp_dir, log_name, file_name)
    
    with open(file_path, "a+", encoding="utf-8") as text_file:
        text_file.write(f"{elapsed_time},{message}\n")

if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
