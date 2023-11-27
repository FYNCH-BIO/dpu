import socket
from socketIO_client import SocketIO, BaseNamespace
import asyncio
from threading import Thread
import random
import time
import sys

EVOLVER_IP = 'localhost'
EVOLVER_PORT = 5555
evolver_ns = None
socketIO = None

usage = '''

=====================PROGRAM USAGE=====================
Command:
	python3 test_hardware.py <port>

About <port>
	<port> tells the program which eVOLVER to connect to
	This is designated in the conf.yml file of the eVOLVER under 'port'
	It is arbitrary, but we can choose something like 5555

Example Command:
	python3 test_hardware.py 5555

'''

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        print("Connected to eVOLVER as client")

    def on_disconnect(self, *args):
        print("Discconected from eVOLVER as client")

    def on_reconnect(self, *args):
        print("Reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        print("\nData from min-eVOLVER:\n",data)       

def run_test(time_to_wait, selection):
	time.sleep(time_to_wait)
	print('Sending data...')

	# Turn Heat ON
	print("\nHeat ON:")
	data = {'param': 'temp', 'value': [25000,25000], 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	print(data)
	time.sleep(4)

	# Test each pump by turning on for 3 seconds
	print("\nTesting Pumps:")
	numPumps = 6
	for i in range(numPumps):
		valList = [0] * numPumps
		valList[i] = 3
		data = {'param': 'pump', 'value': valList, 'immediate': True}
		evolver_ns.emit('command', data, namespace = '/dpu-evolver')
		print(data)
		time.sleep(4)

	time.sleep(3)

	# Test stirring
	print("\nStir OFF:")
	data = {'param': 'stir', 'value': [0,0], 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	print(data)
	time.sleep(5)
	print("Stir ON:")
	data = {'param': 'stir', 'value': [11,11], 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	print(data)
	time.sleep(5)

	# Test OD
	print("\n==========TESTING OD==========")
	print("Check that the od_90 values decrease when OD LED is turned on")
	print("It takes several seconds for a command to change the od_led and for od_90 to change as a result")

	data = {'param': 'od_led', 'value': [0,0], 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	time.sleep(20)
	print("\nODLED OFF:")
	print("\tCommand:",data)
	print("\tExample values: 'od_90': ['65208', '65190']")
	time.sleep(5)

	data = {'param': 'od_led', 'value': [4095,4095], 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	time.sleep(20)
	print("\nODLED ON:")
	print("\tCommand:",data)
	print("\tExample values: od_90': ['62515', '59678']")
	time.sleep(20)

	print("\nCheck to see that the temperature values decreased towards [25000,25000] over time")
	print("\tExample start values: 'temp': ['35514', '35440']")
	print("\tExample end values:   'temp': ['30618', '31029']")

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run_client():
	global evolver_ns, socketIO
	socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
	evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
	socketIO.wait()

if __name__ == '__main__':
	try:
		EVOLVER_PORT = int(sys.argv[1])

	except:
		print(usage)
		sys.exit()

	try:
	    new_loop = asyncio.new_event_loop()
	    t = Thread(target = start_background_loop, args = (new_loop,))
	    t.daemon = True
	    t.start()
	    new_loop.call_soon_threadsafe(run_client)
	    time.sleep(5)
	    run_test(0, 0)
	except KeyboardInterrupt:
		socketIO.disconnect()
