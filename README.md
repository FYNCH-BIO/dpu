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

### List raw temperature JSON files logged on evolver 

#### Mac
```sh
python3.6 calibration/calibrate.py -t -a 192.168.1.2 -g
```

#### Windows
```sh
py calibration/calibrate.py -t -a 192.168.1.2 -g
```

### Choose temperature raw data file to update calibration with

#### Mac
```sh
python3.6 calibration/calibrate.py -t -a 192.168.1.2 -f 'Temp-2019-03-19 06:20:58.json'
```
#### Windows
```sh
py calibration/calibrate.py -t -a 192.168.1.2 -f 'Temp-2019-03-19 06:20:58.json'
```

### List raw OD JSON files logged on evolver 

#### Mac
```sh
python3.6 calibration/calibrate.py -o -a 192.168.1.2 -g 
```

#### Windows
```sh
py calibration/calibrate.py -o -a 192.168.1.2 -g 
```

### Choose OD raw data file to update calibration with (3D, necessary for algal growth module)

```sh
python3.6 calibration/calibrate.py -o -a 192.168.1.2 -f <filename> 
```

#### Windows

```sh
py calibration/calibrate.py -o -a 192.168.1.2 -f <filename> 
```



