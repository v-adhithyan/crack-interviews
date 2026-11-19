from pathlib import Path
from django.core.management.base import BaseCommand
from apps.website.models import BlogPost


class Command(BaseCommand):
    help = 'Publish the three reviewed resume guides; never overwrite existing CMS edits.'

    def handle(self, *args, **options):
        directory = Path(__file__).resolve().parents[2] / 'content'
        for path in sorted(directory.glob('*.md')):
            content = path.read_text()
            title = content.splitlines()[0].removeprefix('# ')
            post, created = BlogPost.objects.get_or_create(slug=path.stem, defaults={
                'title': title, 'excerpt': title + '. Practical guidance, limitations and sources from the HackerLeap team.',
                'content': '\n'.join(content.splitlines()[2:]), 'author_name': 'HackerLeap team', 'status': 'published',
            })
            self.stdout.write(f'{"Published" if created else "Kept existing"}: {post.slug}')
