# -*- coding:utf-8 -*-
import os
import importlib

from app.utils import weight_choice
from app.constants import *

flow_list = {}


def get_flow(site=""):
    cur_dir = os.path.abspath(os.path.dirname(__file__))
    for par, dirs, files in os.walk(cur_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in ["base.py", "__init__.py"]:
                continue
            print f[:-3]
            #mod = __import__(f[:-3])
            mod=importlib.import_module("app.flow.%s" % f[:-3])
            cls = mod.Flow
            if cls.name == site:
                flow_list[cls.name] = cls()
                break
    return flow_list[site]


def get_compatible_flow(line):
    line.check_compatible_lines()
    weights = {}
    for src, line_id in line.compatible_lines.items():
        weights[src] = WEIGHTS.get(src, 500)
    choose = weight_choice(weights)
    from app.models import Line
    new_line = Line.objects.get(line_id=line.compatible_lines[choose])
    return get_flow(choose), new_line
