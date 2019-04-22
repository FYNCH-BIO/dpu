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
	evolver_dir = rootdir + '/experiment'
	OD_dir = evolver_dir + "/%s/%s/OD/vial%s_OD.txt" % (expt_subdir[0],experiment,vial)
	temp_dir = evolver_dir + "/%s/%s/temp/vial%s_temp.txt" % (expt_subdir[0],experiment,vial)


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




def file_scan(tag):
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = rootdir + '/experiment'
	url_string = '{%s url "home" %s}' % ('%','%')

	sidebar_links =[]
	subdir_log = []

	for subdir in next(os.walk(evolver_dir))[1]:
	    subdirname = os.path.join(next(os.walk(evolver_dir))[0], subdir)

	    for subsubdir in next(os.walk(subdirname))[1]:
	        if tag in subsubdir:
	            #add_string = "<li><a href='http://127.0.0.1:8000/%s'>%s</a></li>" % (subsubdir,subsubdir)
	            #add_string = "<li><a href='%s'>%s</a></li>" % (url_string,subsubdir)
	            sidebar_links.append(subsubdir)
	            subdir_log.append(subdir)

	return sidebar_links,subdir_log
