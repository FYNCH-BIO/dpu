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

The DPU requires python 3.9.

#### Mac

```sh
brew install python@3.9
```

#### Windows
Go to the official [python website](https://www.python.org/downloads/release/python-3913/) to download python 3.9. Follow [these instructions](https://docs.python.org/3.9/using/windows.html) to install python on your machine. If you have multiple versions of python3 on your machine, you can set up an [alias](https://martinfritz.medium.com/work-with-multiple-versions-of-python-on-windows-10-eed1e5f52f07) to manage the usage between the different versions.


## Install Dependencies

We use [poetry](https://python-poetry.org/) to manage our python dependencies. Go to their website to download and install it on your machine. If you are using a Mac and have installed homebrew (described above) you can run the following command:

```sh
brew install poetry
```

#### Mac and Windows
```sh
python3.9 -m venv venv
. venv/bin/activate
poetry install
```

On Windows, if you have a different alias or path to python3.9, swap that out in the above command.

You must activate the virtual environment when running DPU scripts. If you close a terminal or re-open it, you'll need to run `. venv/bin/activate` again while in the dpu directory. You can set this up to happen automatically on a Mac or Linux machine by adding a line in your shell run commands (rc) file typically located in your home directory located at `~/.zhrc` (Mac) or `~/.bashrc` (Linux):

`source <path to dpu>/venv/bin/activate`

swapping out `<path to dpu>` with the actual path on your machine to the dpu.

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


