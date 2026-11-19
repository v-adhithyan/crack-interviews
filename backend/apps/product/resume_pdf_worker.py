"""Bounded, short-lived PDF worker; accepts only server-rendered fixed-template HTML."""
import sys

if __package__:
    from .resume_fonts import FONT_ROOT, FONT_FILES
else:
    from resume_fonts import FONT_ROOT, FONT_FILES


def deny_resource(url, *args, **kwargs):
    # Never delegate to the default fetcher: only exact bundled font IDs are valid.
    if url.startswith('resume-font:'):
        name = url[len('resume-font:'):]
        if name in FONT_FILES:
            path = FONT_ROOT / name
            if path.is_symlink() or path.resolve().parent != FONT_ROOT.resolve():
                raise ValueError('Invalid bundled font path')
            from weasyprint.urls import URLFetcherResponse
            return URLFetcherResponse(url, path.read_bytes(), {'Content-Type': 'font/ttf'})
    raise ValueError("External resources are disabled for resumes")


# Missing bundled fonts must fail the export rather than silently substitute a font.
deny_resource._fail_on_errors = True


def main():
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    html = sys.stdin.buffer.read(300001)
    if len(html) > 300000:
        raise ValueError('Document too large')
    document = HTML(string=html.decode('utf-8'), url_fetcher=deny_resource).render(font_config=FontConfiguration())
    if len(document.pages) > 15:
        raise ValueError('Too many pages')
    sys.stdout.buffer.write(document.write_pdf())
    if sys.platform in ('linux', 'darwin'):
        import resource
        import json
        usage = resource.getrusage(resource.RUSAGE_SELF)
        sys.stderr.write('PDF_METRICS ' + json.dumps({
            'peak_memory_bytes': int(usage.ru_maxrss * (1024 if sys.platform == 'linux' else 1)),
            'cpu_ms': int((usage.ru_utime + usage.ru_stime) * 1000),
            'pages': len(document.pages),
        }) + '\n')


if __name__ == '__main__':
    main()
