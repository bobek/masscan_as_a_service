#!/usr/bin/env python3

from jinja2 import Template
from masscan_as_a_service.__main__ import _args_parser

with open('README.jinja2.md', 'r') as stream:
    jinga_template = Template(stream.read())


def template_function(func):
    jinga_template.globals[func.__name__] = func
    return func


@template_function
def expand_help(parser):
    return _args_parser()[parser].format_help()


print(jinga_template.render())
