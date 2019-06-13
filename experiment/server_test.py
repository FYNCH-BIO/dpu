import socket
from socketIO_client import SocketIO, BaseNamespace
import asyncio
from threading import Thread
import random
import time

STIR_VALUES = [[0] * 16, [8] * 16] # flip between on and off
TEMP_VALUES = [4095] * 16 # always off

EVOLVER_IP = '192.168.1.8'
EVOLVER_PORT = 8081
evolver_ns = None
socketIO = None

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
	data = {'param': 'temp', 'value': [4095] * 16, 'immediate': True}
	print(data)
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')

	# Send stir
	data = {'param': 'stir', 'value': STIR_VALUES[selection], 'immediate': True}
	print(data)
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')

	# Set things for the next one
	selection = 1 - selection
	time_to_wait = random.randint(1, 31)
	print('Seconds to wait: ' + str(time_to_wait))
	run_test(time_to_wait, selection)

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
	    new_loop = asyncio.new_event_loop()
	    t = Thread(target = start_background_loop, args = (new_loop,))
	    t.daemon = True
	    t.start()
	    new_loop.call_soon_threadsafe(run_client)
	    time.sleep(5)
	    run_test(0, 0)
	except KeyboardInterrupt:
		socketIO.disconnect()
