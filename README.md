dpu
===
The Data Processing Module (DPU) portion of the eVOLVER code are Python scripts used to interface with the machine. This is where experimental scripts can be written, feedback loops between parameters can be programmed, or calibration files can be updated on eVOLVER.

## Run experimental scripts code for eVOLVER

#### Mac
```sh
python3.6 experiment/your_exptdir/main_eVOLVER.py
```

#### Windows
```sh
py experiment/your_exptdir/main_eVOLVER.py
```


## Start graphing tool for eVOLVER. Start in new Terminal.

NOTE: Experiment name must have 'expt' to get properly graphed.

#### Mac
```sh
python3.6 graphing/src/manage.py runserver
```
#### Windows
```sh
py graphing/src/manage.py runserver
```


See plots locally on http://127.0.0.1:8000




## Setup before running eVOLVER for the first time

#### Mac

#### Install Homebrew and Python 3.6

```sh
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

```sh
brew install --ignore-dependencies https://raw.githubusercontent.com/Homebrew/homebrew-core/f2a764ef944b1080be64bd88dca9a1d80130c558/Formula/python.rb
```

```sh
brew install openssl
brew install sqlite
```

#### Windows

Install from https://www.python.org/downloads/release/python-368/




## Install Dependencies

#### Mac
```sh
python3.6 setup.py install
```

#### Windows
```sh
py setup.py install
```



## Run calibration code (after the raw values have been logged on the eVOLVER)

### List raw calibration files on eVOLVER 

#### Mac
```sh
python3.6 calibration/calibrate.py -a <ip_address> -g
```

For Windows, use py instead of python3.6 for all commands.

### Calibrate Temperature

```sh
python3.6 calibration/calibrate.py -a <ip_address> -n <file_name> -t linear -f <name_after_fit> -p temp
```

### List raw OD JSON files logged on evolver 

#### OD135
```sh
python3.6 calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_135
```

#### OD90 (Check to ensure mode is configured properly)
```sh
python3.6 calibration/calibrate.py -a <ip_address> -n <file_name> -t sigmoid -f <name_after_fit> -p od_90
```

#### 3D FIT (Check to ensure mode is configured properly)
```sh
python3.6 calibration/calibrate.py -a <ip_address> -n <file_name> -t 3d -f <name_after_fit> -p od_90,od_135
```


