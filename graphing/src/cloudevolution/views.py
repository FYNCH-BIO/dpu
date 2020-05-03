from django.shortcuts import render
from django.http import HttpResponse
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import Range1d
import numpy as np
import itertools
import os
import time

# Create your views here.
def home(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "home.html", context)

# Create your views here.
def simple_chart(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "simple_chart.html", context)

def vial_num(request, experiment, vial):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	OD_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "OD", "vial{0}_OD.txt".format(vial))
	temp_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "temp", "vial{0}_temp.txt".format(vial))


	with open(OD_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 5), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(OD_dir, delimiter=',')


	last_OD_update = time.ctime(os.path.getmtime(OD_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(-.05, 2)
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Optical Density'
	p.line(data[:,0], data[:,1], line_width=1)
	OD_script, OD_div = components(p)

	with open(temp_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 10), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(temp_dir, delimiter=',')

	last_temp_update = time.ctime(os.path.getmtime(temp_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(25, 45)
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Temp (C)'
	p.line(data[:,0], data[:,1], line_width=1)
	temp_script, temp_div = components(p)

	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
		"vial": vial,
		"OD_script": OD_script,
		"OD_div": OD_div,
		"temp_script": temp_script,
		"temp_div": temp_div,
		"last_OD_update": last_OD_update,
		"last_temp_update": last_temp_update,
	}

	return render(request, "vial.html", context)

def expt_name(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)

	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
	}

	return render(request, "experiment.html", context)

def dilutions(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	pump_cal = os.path.join(evolver_dir, expt_subdir[0], "pump_cal.txt")

	cal = np.genfromtxt(pump_cal, delimiter="\t")
	diluted = []
	efficiency = []
	last = []

	for vial in vial_count:
		pump_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "pump_log", "vial{0}_pump_log.txt".format(vial))
		ODset_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "ODset", "vial{0}_ODset.txt".format(vial))
		data = np.genfromtxt(pump_dir, delimiter=',', skip_header=2)

		dil_triggered = len(data)

		if dil_triggered != 0:
			volume = str(round(sum(data[:, 1]) * cal[0, vial] / 1000, 2))

			dil_intervals = len(np.genfromtxt(ODset_dir, delimiter=",", skip_header=2)) / 2
			if dil_intervals != 0:
				extra_dils = dil_triggered - dil_intervals
				vial_eff = (dil_intervals - extra_dils) / dil_intervals * 100
			else:
				# Experiment is chemostat or vial is not used
				vial_eff = 0

		else:
			volume = 0
			vial_eff = 0

		diluted.append(volume)
		efficiency.append(str(round(vial_eff, 1)))
		last.append(time.ctime(os.path.getmtime(pump_dir)))

	last_dilution = max(last)

	if efficiency == ['0']*16:
		# All vials were chemostats or not used
		efficiency = None

	context = {
	"sidebar_links": sidebar_links,
	"experiment": experiment,
	"vial_count": vial_count,
	"diluted": diluted,
	"efficiency": efficiency,
	"last_dilution": last_dilution
	}

	return render(request, "dilutions.html", context)


def file_scan(tag):
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, "experiment")
	url_string = '{%s url "home" %s}' % ('%','%')

	sidebar_links =[]
	subdir_log = []

	for subdir in next(os.walk(evolver_dir))[1]:
		subdirname = os.path.join(next(os.walk(evolver_dir))[0], subdir)

		for subsubdir in next(os.walk(subdirname))[1]:
			if tag in subsubdir:
				#add_string = "<li><a href='%s'>%s</a></li>" % (url_string,subsubdir)
				sidebar_links.append(subsubdir)
				subdir_log.append(subdir)
				subdir_log.append(subdir)

	return sidebar_links,subdir_log
