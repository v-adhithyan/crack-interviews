class PublicResumePrivacyMiddleware:
    """Cover errors/CSRF failures too, not just successful view responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.path.startswith('/resume-builder/') and request.path != '/resume-builder/') or request.path == '/signup/':
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
            response['Cache-Control'] = 'private, no-store, max-age=0'
            response['Referrer-Policy'] = 'same-origin'
        return response
