#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "11.12.16"

from django.conf import settings

from .backends import XMLDump

DUMP_BACKENDS = getattr(settings, 'DUMP_BACKENDS', [
    XMLDump
])
