# calibrate.py

## Advanced Users Only:
Currently called by the GUI
Use GUI for calibrations in most cases

## About
The GUI will run calibrations automatically upon completion of the calibration protocols. However, you can still manually run a calibration if you would like to change calibration settings. Can be useful if your GUI calibration fails for some reason.

## Requirements
You have run calibration and logged raw values already
You are in your DPU virtual environment in command line. This is set up when you install the DPU.

## Commands
### List raw calibration files on eVOLVER
**Mac:**

```python3 calibration/calibrate.py -a <ip_address> -g```

For Windows, use py instead of python for all commands.

### Calibrate Temperature
```python3 calibration/calibrate.py -a <ip_address> -n <file_name> -t linear -f <name_after_fit> -p temp```

### List raw OD JSON files logged on evolver
**OD135:**

```python3 calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_135```

**OD90 (Check to ensure mode is configured properly):**

```python3 calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_90```

**3D FIT (Check to ensure mode is configured properly):**

```python3 calibration/calibrate.py -a <ip_address> -n <file_name> -t 3d -f <name_after_fit> -p od_90,od_135```
