#!/usr/bin/env python3

from jinja2 import Template
from masscan_as_a_service.__main__ import _args_parser

with open('README.jinja2.md', 'r') as stream:
    jinga_template = Template(stream.read())

def template_function(func):
    jinga_template.globals[func.__name__] = func
    return func

@template_function
def expand_global_help():
    return _args_parser()['global'].format_help()

@template_function
def expand_masscan_help():
    return _args_parser()['masscan'].format_help()

@template_function
def expand_cleanup_help():
    return _args_parser()['cleanup'].format_help()

print(jinga_template.render())
