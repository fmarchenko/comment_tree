#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

from django.contrib.contenttypes.models import ContentType

__author__ = "Fedor Marchenko"
__email__ = "mfs90@mail.ru"
__date__ = "Dec 09, 2016"

import json

from django.views.generic import ListView, DetailView, TemplateView
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.forms import modelform_factory

from .models import Comment, AsyncCommentsDump
from .req_forms import DumpForm, ListForm
from .utils import CreateCommentList

CommentForm = modelform_factory(Comment, fields=('user', 'parent', 'owner_type', 'owner_id', 'body'))


# Mixin class from Django Documentation.
class JSONResponseMixin(object):
    """
    A mixin that can be used to render a JSON response.
    """
    def render_to_json_response(self, context, **response_kwargs):
        """
        Returns a JSON response, transforming 'context' to make the payload.
        """
        return JsonResponse(
            self.get_data(context),
            **response_kwargs
        )

    def get_data(self, context):
        """
        Returns an object that will be serialized as JSON by json.dumps().
        """
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return context


class CommentListView(JSONResponseMixin, ListView):
    model = Comment
    queryset = Comment.objects.filter(parent__isnull=True)
    filter_fields = ('id', 'owner_type_id', 'owner_id')

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    def get_queryset(self):
        if 'id' in self.request.GET.keys():
            return self.model.objects.all()
        return super(CommentListView, self).get_queryset()

    def get_context_data(self, **kwargs):
        form = ListForm(self.request.GET)
        if form.is_valid():
            cd = form.cleaned_data
            limit = cd.pop('limit') or 10
            offset = cd.pop('offset') or 0
            full_tree = cd.pop('full_tree', False)
            queryset = kwargs.pop('object_list', self.object_list).filter(
                **{k: v for k, v in cd.items() if v}
            )

            ctx = {
                'total_count': queryset.count(),
                'object_list': map(
                    lambda x: x.to_dict(full_tree),
                    queryset[offset:offset+limit]
                ),
                'limit': limit,
                'offset': offset
            }
        else:
            ctx = dict(form.errors)
        return ctx

    def post(self, request, *args, **kwargs):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            form = CommentForm(data)
            if form.is_valid():
                obj = form.save()
                return HttpResponseRedirect(obj.get_absolute_url())
            return self.render_to_json_response(form.errors)
        except ValueError as e:
            return self.render_to_json_response({'error': e.message})


class CommentDetailView(JSONResponseMixin, DetailView):
    model = Comment

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        ctx = {}
        full_tree = self.request.GET.get('full_tree', False) == '1'
        if self.object:
            ctx = self.object.to_dict(full_tree)
        return ctx

    def put(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            if self.request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            form = CommentForm(data, instance=self.object)
            if form.is_valid():
                form.save()
                return self.render_to_response(
                    self.get_context_data(object=self.object)
                )
            return self.render_to_json_response(form.errors)
        except ValueError as e:
            return self.render_to_json_response({'error': e.message})

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            if self.object.children.count() > 0:
                return self.render_to_json_response(
                    {'error': 'Comment parent for many children'},
                    status=405
                )
            self.object.delete()
        except Exception as e:
            return self.render_to_json_response({'error': e.message})
        return self.render_to_json_response({'result': 'Success'})


class UserCommentListView(JSONResponseMixin, DetailView):
    model = get_user_model()

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        ctx = {}
        if self.object:
            # qs = self.model.objects.filter(parents__parent=self.object)
            qs = self.object.comment_set.all().order_by('create_at')
            limit = self.request.GET.get('limit', 10)
            offset = self.request.GET.get('offset', 0)
            ctx = {
                'total_count': qs.count(),
                'object_list': map(
                    lambda x: x.to_dict(False), qs[offset:offset+limit]
                ),
                'limit': limit,
                'offset': offset
            }
        return ctx


class CommentsDumpView(JSONResponseMixin, TemplateView):
    model = Comment
    queryset = Comment.objects.none()

    def get(self, request, *args, **kwargs):
        form = DumpForm(request.GET)
        if not form.is_valid():
            return self.render_to_json_response(dict(form.errors), status=406)
        cd = form.cleaned_data
        if cd['user']:
            owner = cd['user']
        else:
            owner = cd['owner_type'].model_class().objects.get(
                pk=cd['owner_id']
            )
        qs = AsyncCommentsDump.objects.filter(
            owner_type=ContentType.objects.get_for_model(owner.__class__),
            owner_id=owner.id
        )
        if qs.count() == 0:
            return self.render_to_json_response(
                {'error': 'Not found comments unloading'}, status=404
            )

        limit = self.request.GET.get('limit', 10)
        offset = self.request.GET.get('offset', 0)
        return self.render_to_json_response({
            'total_count': qs.count(),
            'object_list': map(
                lambda x: x.as_dict(),
                qs[offset:offset+limit]
            ),
            'offset': offset,
            'limit': limit
        })

    def post(self, request, *args, **kwargs):
        form = DumpForm(request.POST)
        if not form.is_valid():
            return self.render_to_json_response(dict(form.errors), status=406)
        cd = form.cleaned_data
        qs = self.model.objects.filter(
            **{k: v for k, v in cd.items() if v is not None}
        )
        if cd['user']:
            owner = cd['user']
        else:
            owner = cd['owner_type'].model_class().objects.get(
                pk=cd['owner_id']
            )
        if qs.count() == 0:
            return self.render_to_json_response(
                {'error': 'Not found comments'}, status=404
            )

        acd = AsyncCommentsDump(owner=owner)
        acd.save()

        async = CreateCommentList(acd)
        async.run()

        return self.render_to_json_response({
            'result': 'Start proccess for build history list',
            'id': acd.pk
        })


class AsyncDumpResultView(JSONResponseMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk', None)
        if pk:
            try:
                self.object = AsyncCommentsDump.objects.get(pk=pk)
            except AsyncCommentsDump.DoesNotExist as e:
                return self.render_to_json_response(
                    {'error': e.message},
                    status=404
                )
            ctx = {
                'id': self.object.pk,
                'ready': self.object.is_ready()
            }
            if self.object.is_ready():
                ctx['path'] = self.object.path.url
            return self.render_to_json_response(ctx)
        return self.render_to_json_response({})
