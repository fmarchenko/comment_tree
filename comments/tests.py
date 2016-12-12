import json

from django.test import TestCase, Client
from django.test.utils import setup_test_environment
from django.contrib.auth import get_user_model
from django.urls.base import reverse
from django.contrib.contenttypes.models import ContentType

from .models import Comment, Post, Photo, HistoryComment

setup_test_environment()
USER_MODEL = get_user_model()


class CommentsMethodsTests(TestCase):
    comments = {}

    def setUp(self):
        self.client = Client()
        self.ct_post = ContentType.objects.get_for_model(Post)
        self.test_user = USER_MODEL(username='test_user')
        self.test_user.set_password('test_user1234')
        self.test_user.save()
        self.test_post = Post(pk=1)
        self.test_post.save()
        self.test_post.subscribers.add(self.test_user)
        self.test_post.save()
        self.test_photo = Photo(pk=2)
        self.test_photo.save()
        self.comments['1l_post'] = Comment(
            owner=self.test_post,
            body='Comment for Post #1',
            user=self.test_user
        )
        self.comments['1l_post'].save()
        self.comments['1l_photo'] = Comment(
            owner=self.test_photo,
            body='Comment for Photo #1',
            user=self.test_user
        )
        self.comments['1l_photo'].save()
        self.comments['2l_post_comment'] = Comment(
            parent=self.comments['1l_post'],
            body='Comment for Comment #1',
            user=self.test_user
        )
        self.comments['2l_post_comment'].save()
        self.comments['2l_photo_comment'] = Comment(
            parent=self.comments['1l_photo'],
            body='Comment for Comment #2',
            user=self.test_user
        )
        self.comments['2l_photo_comment'].save()
        self.comments['3l_comment_comment'] = Comment(
            parent=self.comments['2l_post_comment'],
            body='Comment for Comment #3',
            user=self.test_user
        )
        self.comments['3l_comment_comment'].save()

    def test_create_comments(self):
        # Get list of comments
        response = self.client.get(reverse('comment_list'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['total_count'], 2)

        # Create comments for Post
        response = self.client.post(reverse('comment_list'), data=json.dumps({
            'body': 'API CREATE Comment for Post #1',
            'owner_type': self.ct_post.pk,
            'owner_id': self.test_post.pk
        }), content_type='application/json')
        self.assertEqual(response.status_code, 302)

        # Create comments for Comment
        response = self.client.post(reverse('comment_list'), data=json.dumps({
            'body': 'API CREATE Comment for Comment #%d' %
                    self.comments['2l_post_comment'].pk,
            'parent_id': self.comments['2l_post_comment'].pk
        }), content_type='application/json')
        self.assertEqual(response.status_code, 302)

        # Get list comments for check
        response = self.client.get(reverse('comment_list'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['total_count'], 4)

    def test_change_comment(self):
        # Get info by comment
        response = self.client.get(self.comments['1l_photo'].get_absolute_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        body = data['body']

        # Change comment
        data['body'] *= 2
        response = self.client.post(
            self.comments['1l_photo'].get_absolute_url(),
            data=json.dumps(data), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['body'], body * 2)

        # Check history
        ch = HistoryComment.objects.filter(comment_id=data['id'])\
            .order_by('create_at').last()
        self.assertEqual(json.loads(ch.json_state)['body'], body)

    def test_delete_comment(self):
        # Delete without childs
        response = self.client.delete(
            self.comments['3l_comment_comment'].get_absolute_url()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['result'], 'Success')

        # Delete with childs
        response = self.client.delete(
            self.comments['1l_post'].get_absolute_url()
        )
        self.assertEqual(response.status_code, 405)

    def test_list_comments(self):
        # Getting commentaries for Post #1
        response = self.client.get('{}?owner_type_id={}&owner_id={}'.format(
            reverse('comment_list'), self.ct_post.pk, self.test_post.pk
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['total_count'], 1)

        # Getting commentaries hierarchy for Comment #3
        response = self.client.get('{}?id={}&full_tree=1'.format(
            reverse('comment_list'), self.comments['1l_post'].pk
        ))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(
            len(data['object_list'][0]['childs']),
            self.comments['1l_post'].children.count()
        )
        self.assertEqual(
            len(data['object_list'][0]['childs'][0]['childs']),
            self.comments['1l_post'].children.all()[0].children.count()
        )

        # Getting history of comments for user #1
        response = self.client.get(reverse(
            'user_comments', args=(self.test_user.pk,)
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)['total_count'],
            len(self.comments.keys())
        )

        self.comments['1l_photo'].user = None
        self.comments['1l_photo'].save()
        response = self.client.get(reverse(
            'user_comments', args=(self.test_user.pk,)
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)['total_count'],
            len(self.comments.keys()) - 1
        )

    def test_async_user_history(self):
        # Dump user comments history
        response = self.client.post('{}?user={}'.format(
            reverse('comments_dump'), self.test_user.pk
        ))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Check ready status for dump id
        response = self.client.get(reverse(
            'comments_dump_result', args=(data['id'],)
        ))
        self.assertEqual(response.status_code, 200)

        # Getting history of dumps
        response = self.client.get('{}?user={}'.format(
            reverse('comments_dump'), self.test_user.pk
        ))
        self.assertEqual(response.status_code, 200)
