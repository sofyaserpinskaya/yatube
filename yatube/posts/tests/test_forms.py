import shutil
import tempfile

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post, User


AUTHOR_USERNAME = 'TestAuthor'
GROUP_TITLE_1 = 'Тестовая группа'
GROUP_SLUG_1 = 'test-slug'
GROUP_DESCRIPTION_1 = 'Тестовое описание'
GROUP_TITLE_2 = 'Тестовая группа 2'
GROUP_SLUG_2 = 'test-slug2'
GROUP_DESCRIPTION_2 = 'Тестовое описание 2'
POST_TEXT_1 = '1й текст'
POST_TEXT_2 = '2й текст'
POST_TEXT_3 = 'Редактированный текст'
SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x02\x00'
    b'\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
    b'\x00\x00\x00\x2C\x00\x00\x00\x00'
    b'\x02\x00\x01\x00\x00\x02\x02\x0C'
    b'\x0A\x00\x3B'
)
COMMENT = 'Тестовый комментарий'

PROFILE_URL = reverse('posts:profile', args=[AUTHOR_USERNAME])
POST_CREATE_URL = reverse('posts:post_create')
LOGIN_URL = reverse('users:login')

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author_user = User.objects.create_user(username=AUTHOR_USERNAME)
        cls.group_1 = Group.objects.create(
            title=GROUP_TITLE_1,
            slug=GROUP_SLUG_1,
            description=GROUP_DESCRIPTION_1,
        )
        cls.group_2 = Group.objects.create(
            title=GROUP_TITLE_2,
            slug=GROUP_SLUG_2,
            description=GROUP_DESCRIPTION_2,
        )
        cls.post = Post.objects.create(
            text=POST_TEXT_1,
            author=cls.author_user,
            group=cls.group_1,
        )
        cls.POST_EDIT_URL = reverse('posts:post_edit', args=[cls.post.id])
        cls.POST_DETAIL_URL = reverse('posts:post_detail', args=[cls.post.id])
        cls.COMMENT_URL = reverse('posts:add_comment', args=[cls.post.id])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.author = Client()
        self.author.force_login(self.author_user)

    def test_create_post(self):
        Post.objects.all().delete()
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=SMALL_GIF,
            content_type='image/gif'
        )
        form_data = {
            'text': POST_TEXT_2,
            'group': self.group_1.id,
            'image': uploaded,
        }
        response = self.author.post(
            POST_CREATE_URL,
            data=form_data,
            follow=True
        )
        self.assertEqual(Post.objects.count(), 1)
        post = Post.objects.first()
        self.assertEqual(post.text, form_data['text'])
        self.assertEqual(post.group.id, form_data['group'])
        self.assertEqual(post.author, self.author_user)
        self.assertEqual(post.image, f"posts/{form_data['image'].name}")
        self.assertRedirects(response, PROFILE_URL)

    def test_edit_post(self):
        self.assertEqual(Post.objects.count(), 1)
        form_data = {
            'text': POST_TEXT_3,
            'group': self.group_2.id,
        }
        response = self.author.post(
            self.POST_EDIT_URL,
            data=form_data,
            follow=True
        )
        self.assertEqual(Post.objects.count(), 1)
        post = Post.objects.get(pk=self.post.pk)
        self.assertRedirects(response, self.POST_DETAIL_URL)
        self.assertEqual(post.text, form_data['text'])
        self.assertEqual(post.group.id, form_data['group'])
        self.assertEqual(post.author, self.post.author)

    def test_create_edit_pages_show_correct_context(self):
        urls = [POST_CREATE_URL, self.POST_EDIT_URL]
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for url in urls:
            form = self.author.get(url).context.get('form')
            for value, expected in form_fields.items():
                with self.subTest(value=value):
                    form_field = form.fields.get(value)
                    self.assertIsInstance(form_field, expected)

    def test_comment_on_post_detail_page(self):
        self.assertEqual(Comment.objects.count(), 0)
        form_data = {
            'text': COMMENT,
        }
        response = self.author.post(
            self.COMMENT_URL,
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.text, form_data['text'])
        self.assertRedirects(response, self.POST_DETAIL_URL)
        post_comments = self.author.get(
            self.POST_DETAIL_URL).context['comments']
        self.assertEqual(len(post_comments), 1)
        self.assertEqual(post_comments[0].text, comment.text)

    def test_guest_client_cannot_write_comments(self):
        self.assertEqual(Comment.objects.count(), 0)
        guest = Client()
        form_data = {
            'text': COMMENT,
        }
        response = guest.post(
            self.COMMENT_URL,
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.count(), 0)
        self.assertRedirects(response, f'{LOGIN_URL}?next={self.COMMENT_URL}')