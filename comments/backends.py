#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "11.12.16"

from django.core import serializers


class XMLDump(object):
    _ext = 'xml'

    def __init__(self, qs):
        self.qs = qs

    @property
    def ext(self):
        return self._ext

    def run(self):
        data = serializers.serialize(self._ext, self.qs)
        return data
