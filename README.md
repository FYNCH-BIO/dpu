min-eVOLVER dpu
===
The Data Processing Module (DPU) portion of the eVOLVER code are Python scripts used to interface with the machine. This is where experimental scripts can be written, feedback loops between parameters can be programmed, or calibration files can be updated on eVOLVER.

For more information about the DPU and installation, see the [wiki](https://khalil-lab.gitbook.io/evolver/extensions/min-evolver/setup/).

## Run experimental scripts code for eVOLVER

#### Mac
```sh
python3 experiment/your_exptdir/eVOLVER.py
```

#### Windows
```sh
py experiment/your_exptdir/eVOLVER.py
```


## Start graphing tool for eVOLVER. Start in new Terminal.

NOTE: Experiment name must have 'expt' to get properly graphed. We are also moving to the GUI for graphing experiment data in real-time.

#### Mac
```sh
python3 graphing/src/manage.py runserver
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
python3 setup.py install
```

#### Windows
```sh
py setup.py install
```
