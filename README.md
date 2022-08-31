dpu
===
The Data Processing Module (DPU) portion of the eVOLVER code are Python scripts used to interface with the machine. This is where experimental scripts can be written, feedback loops between parameters can be programmed, or calibration files can be updated on eVOLVER.

For more information about the DPU and installation, see the [wiki](https://khalil-lab.gitbook.io/evolver/getting-started/software-installation/dpu-installation).

## Run experimental scripts code for eVOLVER

#### Mac
```sh
python experiment/your_exptdir/eVOLVER.py
```

#### Windows
```sh
py experiment/your_exptdir/eVOLVER.py
```


## Start graphing tool for eVOLVER. Start in new Terminal.

NOTE: Experiment name must have 'expt' to get properly graphed. We are also moving to the GUI for graphing experiment data in real-time.

#### Mac
```sh
python graphing/src/manage.py runserver
```
#### Windows
```sh
py graphing/src/manage.py runserver
```


See plots locally on http://127.0.0.1:8000




## Setup before running eVOLVER for the first time

#### Mac

#### Install Homebrew

```sh
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

```sh
brew install openssl
brew install sqlite
```

## Install Dependencies

#### Mac
```sh
python setup.py install
```

#### Windows
```sh
py setup.py install
```

## Run calibration code (after the raw values have been logged on the eVOLVER)
The GUI will run calibrations automatically upon completion of the calibration protocols. However, you can still manually run a calibration if you would like to change calibration settings.

### List raw calibration files on eVOLVER 

#### Mac
```sh
python calibration/calibrate.py -a <ip_address> -g
```

For Windows, use py instead of python for all commands.

### Calibrate Temperature

```sh
python calibration/calibrate.py -a <ip_address> -n <file_name> -t linear -f <name_after_fit> -p temp
```

### List raw OD JSON files logged on evolver 

#### OD135
```sh
python calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_135
```

#### OD90 (Check to ensure mode is configured properly)
```sh
python calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_90
```

#### 3D FIT (Check to ensure mode is configured properly)
```sh
python calibration/calibrate.py -a <ip_address> -n <file_name> -t 3d -f <name_after_fit> -p od_90,od_135
```


