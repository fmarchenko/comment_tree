#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "Dec 09, 2016"

from django.conf.urls import url

from .views import (
    CommentListView, CommentDetailView,
    UserCommentListView, CommentsDumpView, AsyncDumpResultView
)

urlpatterns = [
    url(r'^comments/dump/(?P<pk>\d+)/$',
        AsyncDumpResultView.as_view(), name='comments_dump_result'
    ),
    url(r'^comments/dump/$', CommentsDumpView.as_view(), name='comments_dump'),
    url(r'^comments/user/(?P<pk>\d+)/$',
        UserCommentListView.as_view(), name='user_comments'
    ),
    url(r'^comments/(?P<pk>\d+)/$',
        CommentDetailView.as_view(), name='comment_detail'
    ),
    url(r'^comments/', CommentListView.as_view(), name='comment_list')
]
