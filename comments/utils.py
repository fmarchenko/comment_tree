#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "11.12.16"

import os
from threading import Thread

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .models import Comment
from .settings import DUMP_BACKENDS

USER_MODEL = get_user_model()


class CreateCommentList(Thread):
    def __init__(self, acd):
        self.acd = acd

    def run(self):
        qs = Comment.objects.none()
        ct_user = ContentType.objects.get_for_model(USER_MODEL)
        if self.acd.owner_type == ct_user:
            qs = Comment.objects.filter(
                user=self.acd.owner
            )
        else:
            qs = Comment.objects.filter(
                owner=self.acd.owner
            )
        if self.acd.start_at:
            qs = qs.filter(create_at__gte=self.acd.start_at)
        if self.acd.end_at:
            qs = qs.filter(create_at__lte=self.acd.end_at)

        for b_cls in DUMP_BACKENDS:
            backend = b_cls(qs)
            filepath = os.path.join(
                settings.MEDIA_ROOT,
                'dumps',
                '{}.{}'.format(self.acd.pk, backend.ext)
            )
            dirpath = os.path.dirname(filepath)

            if not os.path.exists(dirpath):
                os.makedirs(dirpath)

            fout = open(filepath, 'wb+')
            fout.write(backend.run())
            self.acd.path.name = filepath.split(settings.MEDIA_ROOT)[1]
            self.acd.save()
            fout.close()


class NotifyTask(Thread):
    def __init__(self, comment):
        self.comment = comment

    def run(self):
        qs = self.comment.parents.filter(parent__owner_id__isnull=False)
        for closure in qs:
            for user in closure.parent.owner.subscribers.all():
                filename = os.path.join(
                    settings.MEDIA_ROOT, 'notify',
                    'user_{}'.format(user.pk),
                    'notify_about_{}'.format(self.comment)
                )
                dirpath = os.path.dirname(filename)
                if not os.path.exists(dirpath):
                    os.makedirs(dirpath)

                with open(filename, 'wb+') as fout:
                    fout.write(
                        'New comment for {}'.format(closure.parent.owner)
                    )
