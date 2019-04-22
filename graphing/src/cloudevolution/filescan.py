# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 11:32:36 2015

@author: brandonwong
"""

import os

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


sidebar_links, subdir_log = file_scan('BW_temppid_expt2_20151019')
print sidebar_links
print subdir_log
