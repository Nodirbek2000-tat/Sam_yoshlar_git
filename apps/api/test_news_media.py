"""Yangilik: bir nechta rasm (galereya) va video yuklash."""

import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.content.models import NEWS_PHOTO_LIMIT, News, NewsPhoto

from .auth_views import tokens_for
from .tests import _png

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='yangilik-test-')


def video(name='lavha.mp4', size=1024):
    return SimpleUploadedFile(name, b'\x00' * size, content_type='video/mp4')


@override_settings(MEDIA_ROOT=MEDIA, SITE_URL='https://samarqandyoshlari.uz')
class NewsMediaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.admin)['access']}"}

    def create(self, **extra):
        data = {'title': "Yoshlar forumi bo'lib o'tdi", 'category': 'forum',
                'excerpt': "Qisqacha", 'body': "Matn", 'is_published': 'true', **extra}
        return self.client.post('/api/v1/panel/news/', data, **self.auth)

    def test_several_photos_and_video_reach_the_site(self):
        response = self.create(new_photos=[_png('1.png'), _png('2.png'), _png('3.png')],
                               video=video())
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(len(body['photos']), 3)
        self.assertIn('/media/news/videos/', body['video_url'])

        public = self.client.get(f"/api/v1/news/{body['slug']}/").json()
        self.assertEqual(len(public['photos']), 3)
        self.assertTrue(public['photos'][0].startswith('https://samarqandyoshlari.uz/media/news/gallery/'))
        self.assertIn('/media/news/videos/', public['video'])

    def test_photos_can_be_added_and_removed_later(self):
        news = self.create(new_photos=[_png('1.png'), _png('2.png')]).json()
        first = news['photos'][0]['id']
        path = NewsPhoto.objects.get(pk=first).image.path

        response = self.client.patch(
            f"/api/v1/panel/news/{news['id']}/tahrir/",
            data=self._multipart({'new_photos': [_png('3.png')], 'remove_photos': [first]}),
            content_type=self._boundary, **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        ids = [photo['id'] for photo in response.json()['photos']]
        self.assertEqual(len(ids), 2)
        self.assertNotIn(first, ids)
        self.assertFalse(os.path.exists(path))

    def test_video_limits(self):
        too_big = self.create(video=video(size=25 * 1024 * 1024 + 1))
        self.assertEqual(too_big.status_code, 400)
        self.assertIn('25 MB', str(too_big.json()))

        wrong = self.create(video=video('lavha.avi'))
        self.assertEqual(wrong.status_code, 400)

    def test_video_replace_and_remove_deletes_old_file(self):
        news = self.create(video=video('birinchi.mp4')).json()
        old = News.objects.get(pk=news['id']).video.path

        self.client.patch(f"/api/v1/panel/news/{news['id']}/tahrir/",
                          data=self._multipart({'video': video('ikkinchi.mp4')}),
                          content_type=self._boundary, **self.auth)
        self.assertFalse(os.path.exists(old))
        current = News.objects.get(pk=news['id']).video.path

        response = self.client.patch(f"/api/v1/panel/news/{news['id']}/tahrir/",
                                     {'remove_video': True}, content_type='application/json',
                                     **self.auth)
        self.assertIsNone(response.json()['video_url'])
        self.assertFalse(os.path.exists(current))

    def test_photo_limit(self):
        response = self.create(new_photos=[_png(f'{i}.png') for i in range(NEWS_PHOTO_LIMIT + 1)])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(News.objects.exists())

    def test_delete_removes_gallery_and_video_files(self):
        news = self.create(new_photos=[_png('1.png')], video=video()).json()
        item = News.objects.get(pk=news['id'])
        files = [item.video.path, item.photos.get().image.path]

        response = self.client.delete(f"/api/v1/panel/news/{news['id']}/", **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NewsPhoto.objects.exists())
        for path in files:
            self.assertFalse(os.path.exists(path))

    # -- multipart PATCH -------------------------------------------------------

    _boundary = 'multipart/form-data; boundary=BoUnDaRy'

    def _multipart(self, data):
        from django.test.client import encode_multipart
        return encode_multipart('BoUnDaRy', data)
