from __future__ import unicode_literals

import json

from django.db import models, transaction
from django.forms.models import model_to_dict
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


class AbstractTestEntity(models.Model):
    subscribers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='subscriptions_%(class)ss'
    )

    class Meta:
        abstract = True


class Post(AbstractTestEntity):
    pass


class Photo(AbstractTestEntity):
    pass


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
    parent = models.ForeignKey(
        'self', related_name='children',
        blank=True, null=True
    )
    owner_type = models.ForeignKey(ContentType, blank=True, null=True)
    owner_id = models.PositiveIntegerField(blank=True, null=True)
    owner = GenericForeignKey('owner_type', 'owner_id')

    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    body = models.TextField()

    class Meta:
        ordering = ['create_at']

    def delete_links(self):
        CommentClosure.objects.filter(
            child=self, parent=self.parent
        ).delete()

    def create_links(self):
        parents = CommentClosure.objects.filter(child=self.parent)\
            .values('parent', 'depth')
        childrens = CommentClosure.objects.filter(parent=self)\
            .values('child', 'depth')
        newlinks = [
            CommentClosure(
                parent_id=p['parent'], child_id=c['child'],
                depth=p['depth']+c['depth']+1
            )
            for p in parents for c in childrens]
        CommentClosure.objects.bulk_create(newlinks)

    def __unicode__(self):
        return '#{} for owner {} and parent {}'.format(
            self.pk, self.owner, self.parent_id
        )

    def get_absolute_url(self):
        return reverse('comment_detail', kwargs={'pk': self.pk})

    def to_dict(self, with_childs=True):
        dict_obj = model_to_dict(self, fields=(
            'id', 'user', 'parent', 'owner_type', 'owner_id',
            'body'
        ))
        dict_obj.update({
            'create_at': self.create_at.isoformat(),
            'update_at': self.update_at.isoformat()
        })
        if with_childs:
            dict_obj['childs'] = map(
                lambda x: x.child.to_dict(),
                self.childrens.filter(child__parent=self)
            )
        return dict_obj

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        create = self.pk is None
        if create:
            super(Comment, self).save(force_insert, force_update, using,
                                      update_fields)
            closure_instance = CommentClosure(
                parent=self,
                child=self,
                depth=0
            )
            closure_instance.save()
            self.create_links()

            # Send notifications
            from .utils import NotifyTask
            task = NotifyTask(self)
            task.run()
        else:
            orig = Comment.objects.get(pk=self.pk)
            history = HistoryComment(
                json_state=json.dumps(orig.to_dict()),
                comment=orig
            )
            history.save()
            if orig.parent_id != self.parent_id:
                orig.delete_links()
                self.create_links()
            super(Comment, self).save(force_insert, force_update, using,
                                      update_fields)

    def delete(self, using=None, keep_parents=False):
        with transaction.atomic():
            childs = Comment.objects.filter(parents__parent=self)
            closures = CommentClosure.objects.filter(parent=self)
            closures.delete()
            map(lambda x: x.delete(), childs)
            super(Comment, self).delete(using, keep_parents)



class CommentClosure(models.Model):
    parent = models.ForeignKey(Comment, related_name='childrens')
    child = models.ForeignKey(Comment, related_name='parents')
    depth = models.IntegerField(default=0)

    def __unicode__(self):
        return 'Parent #{}, child #{}'.format(self.parent_id, self.child_id)


class HistoryComment(models.Model):
    chenged = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
    json_state = models.TextField()
    comment = models.ForeignKey(Comment)
    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)


class AsyncCommentsDump(models.Model):
    create_at = models.DateTimeField(auto_now_add=True)
    path = models.FileField(upload_to='dumps', blank=True, null=True)
    owner_type = models.ForeignKey(ContentType)
    owner_id = models.PositiveIntegerField()
    owner = GenericForeignKey('owner_type', 'owner_id')
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)

    def is_ready(self):
        return self.path is not None

    def as_dict(self):
        dict_obj = model_to_dict(
            self,
            fields=map(lambda x: x.name, self._meta.get_fields()),
            exclude=('path',)
        )
        dict_obj['path'] = self.path.url
        return dict_obj
