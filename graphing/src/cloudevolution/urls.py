"""cloudevolution URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import patterns,include, url
from django.contrib import admin

urlpatterns = [
	
	url(r'^$', 'cloudevolution.views.home',name = 'home'),
    url(r'^simple_chart/$', 'cloudevolution.views.simple_chart', name="simple_chart"),

    url(r'^(?P<experiment>\w+)/$', 'cloudevolution.views.expt_name', name='expt_name'),

    url(r'^(?P<experiment>\w+)/(?P<vial>[0-9]+)/$', 'cloudevolution.views.vial_num', name='vial_num'),

    url(r'^admin/', include(admin.site.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,document_root= settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,document_root= settings.MEDIA_ROOT)
