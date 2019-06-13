eVOLVER test script
===================

The `test_eVOLVER.py` script can be used to verify that the user-defined
functions in the `custom_script.py` file behave as expected and are bug-free
without having to run an actual eVOLVER experiment. Data from a previous
eVOLVER run or a simulation can be used.

Usage
-----

Place the `test_eVOLVER.py` script in the same folder with the
`eVOLVER_module.py`, `main_eVOLVER.py` and the `custom_script.py` files.
Run `python3 test_eVOLVER.py -h` to see the full list of options.

The script expects a mock directory with previous/simulated data, specifically
the `OD` and `temp` directories, containing one file for each vial. The other
directories (if present) are ignored.

The script uses the OD and temp information as if they were coming from an
actual eVOLVER device and will work as if each command sent by the
`custom_script.py` file was executed successfully. A results directory called
`test_exp` is created and used by this script to log the data.
