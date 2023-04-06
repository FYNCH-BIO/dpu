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
python3 send_command.py <port> <parameter> <value>

About <port>
	<port> tells the program which eVOLVER to connect to
	This is designated in the conf.yml file of the eVOLVER under 'port'
	It is arbitrary, but we can choose something like 5555

To set a parameter on all vials to one value:
	python3 send_command.py <port> <parameter> <value>

	For example:
	python3 send_command.py 5555 stir 8

To run specific pumps (where s is a number of seconds):
	python3 send_command.py <port> pump s,s,s,s,s,s

	For example:
	python3 send_command.py 5555 pump 0,0,0,0,5,5

To set a non-pump parameter on specific vials:
	python3 send_command.py <port> <parameter> <list_of_values>

	For example:
	python3 send_command.py 5555 temp 30000,31000
'''

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        print("Connected to eVOLVER as client")

    def on_disconnect(self, *args):
        print("Discconected from eVOLVER as client")

    def on_reconnect(self, *args):
        print("Reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        print(data)       

def run_test(time_to_wait, selection):
	time.sleep(time_to_wait)
	print('Sending data...')
	# Send temp
	if type(value) == int:
		if parameter == 'pump':
			data = {'param': parameter, 'value': [value] * 6, 'immediate': True}
		else:
			data = {'param': parameter, 'value': [value] * 2, 'immediate': True}
	
	else: # "value" is already a list 
		data = {'param': parameter, 'value': value, 'immediate': True}
	
	print(data)
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run_client():
	global evolver_ns, socketIO
	socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
	evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
	socketIO.wait()

if __name__ == '__main__':
	global parameter
	global value
	try:
		EVOLVER_PORT = int(sys.argv[1])
		parameter = str(sys.argv[2])
		value = int(sys.argv[3])
	except:
		try:
			EVOLVER_PORT = int(sys.argv[1])
			parameter = str(sys.argv[2])
			value = sys.argv[3].split(",")
			print(value)

			if parameter == 'pump' and len(value) != 6:
				print('\nError:: pump commands require 6 values')
				raise IndexError
			elif parameter != 'pump' and len(value) != 2:
				print('\nError:: non-pump commands require 2 values')
				raise IndexError

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
