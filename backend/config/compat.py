import sys


def patch_django_context_copy_for_python_314():
    if sys.version_info < (3, 14):
        return

    from django.template.context import BaseContext

    def copy_context(self):
        duplicate = object.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = copy_context
