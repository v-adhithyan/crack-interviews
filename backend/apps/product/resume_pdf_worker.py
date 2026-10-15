"""Bounded, short-lived PDF worker; accepts only server-rendered fixed-template HTML."""
import sys


def deny_resource(url, *args, **kwargs):
    raise ValueError("External resources are disabled for resumes")


def main():
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    from weasyprint import HTML
    html = sys.stdin.buffer.read(300001)
    if len(html) > 300000:
        raise ValueError('Document too large')
    document = HTML(string=html.decode('utf-8'), url_fetcher=deny_resource).render()
    if len(document.pages) > 15:
        raise ValueError('Too many pages')
    sys.stdout.buffer.write(document.write_pdf())


if __name__ == '__main__':
    main()
