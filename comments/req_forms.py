#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "11.12.16"

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType


class LimitOffsetForm(forms.Form):
    limit = forms.IntegerField(initial=10, required=False)
    offset = forms.IntegerField(initial=0, required=False)
    full_tree = forms.BooleanField(initial=False, required=False)


class ListForm(LimitOffsetForm):
    id = forms.IntegerField(required=False)
    owner_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False
    )
    owner_id = forms.IntegerField(required=False)


class DumpForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(),
        required=False
    )
    owner_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False
    )
    owner_id = forms.IntegerField(required=False)
    create_at__gte = forms.DateTimeField(required=False)
    create_at__lte = forms.DateTimeField(required=False)

    def clean(self):
        cleaned_data = super(DumpForm, self).clean()
        user = cleaned_data.get('user')
        owner_type = cleaned_data.get('owner_type')
        owner_id = cleaned_data.get('owner_id')
        if not user or (owner_type and owner_id):
            raise forms.ValidationError('Enter a user or entity')