from __future__ import unicode_literals

import json

from django.db import models
from django.forms.models import model_to_dict
from django.core.urlresolvers import reverse
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
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
    parent = models.ForeignKey('self', related_name='children', blank=True, null=True)
    owner_type = models.ForeignKey(ContentType, blank=True, null=True)
    owner_id = models.PositiveIntegerField(blank=True, null=True)
    owner = GenericForeignKey('owner_type', 'owner_id')

    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    body = models.TextField()

    class Meta:
        ordering = ['create_at']

    def delete_links(self):
        CommentClosure.objects.filter(models.Q(child=self) | models.Q(child__parent=self)).delete()

    def create_links(self):
        parents = CommentClosure.objects.filter(child=self.parent)\
            .values('parent', 'depth')
        childrens = CommentClosure.objects.filter(parent=self)\
            .values('child', 'depth')
        newlinks = [
            CommentClosure(parent_id=p['parent'], child_id=c['child'], depth=p['depth']+c['depth']+1)
            for p in parents for c in childrens]\
            + [
                CommentClosure(parent=self, child=x) for x in self.children.all()
            ]
        CommentClosure.objects.bulk_create(newlinks)

    def __unicode__(self):
        return '#{} for owner {} and parent {}'.format(self.pk, self.owner, self.parent_id)

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
            dict_obj['childs'] = map(lambda x: x.child.to_dict(), self.childrens.filter(child__parent=self))
        return dict_obj

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.pk is not None:
            orig = Comment.objects.get(pk=self.pk)
            history = HistoryComment(
                json_state=json.dumps(orig.to_dict()),
                comment=orig
            ).save()
        super(Comment, self).save(force_insert, force_update, using,
                                  update_fields)


class CommentClosure(models.Model):
    parent = models.ForeignKey(Comment, related_name='childrens')
    child = models.ForeignKey(Comment, related_name='parents')
    depth = models.IntegerField(default=0)


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


@receiver(pre_delete, sender=Comment)
def comment_model_delete(sender, **kwargs):
    instance = kwargs['instance']
    instance.delete_links()
    Comment.objects.filter(parents__parent=instance).delete()
    CommentClosure.objects.filter(parent=instance).delete()


@receiver(post_save, sender=Comment)
def comment_model_save(sender, **kwargs):
    instance = kwargs['instance']
    created = kwargs['created']
    instance.delete_links()
    closure_instance = CommentClosure(
        parent=instance,
        child=instance,
        depth=0
    ).save()
    instance.create_links()

    if created:
        from .utils import NotifyTask
        task = NotifyTask(instance)
        task.run()
