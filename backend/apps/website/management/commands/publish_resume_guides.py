from pathlib import Path
from django.core.management.base import BaseCommand
from apps.website.models import BlogPost


class Command(BaseCommand):
    help = 'Publish the reviewed resume guides; never overwrite existing CMS edits.'

    def handle(self, *args, **options):
        directory = Path(__file__).resolve().parents[2] / 'content'
        for path in sorted(directory.glob('*.md')):
            lines = path.read_text(encoding='utf-8').splitlines()
            title = lines[0].removeprefix('# ')
            body = lines[2:]
            excerpt = title + '. Practical guidance, limitations and sources from the HackerLeap team.'
            if body and body[0].startswith('Excerpt: '):
                excerpt = body[0].removeprefix('Excerpt: ')
                body = body[2:]
            post, created = BlogPost.objects.get_or_create(slug=path.stem, defaults={
                'title': title, 'excerpt': excerpt,
                'content': '\n'.join(body), 'author_name': 'HackerLeap team', 'status': 'published',
            })
            self.stdout.write(f'{"Published" if created else "Kept existing"}: {post.slug}')
