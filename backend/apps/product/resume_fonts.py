"""Immutable registry shared by Django and the isolated PDF subprocess."""
from pathlib import Path

FONT_ROOT = Path(__file__).parent / 'static' / 'product' / 'fonts'
FAMILIES = {
    'default': 'LiberationSans', 'arial': 'LiberationSans', 'helvetica': 'LiberationSans',
    'calibri': 'Carlito', 'cambria': 'Caladea', 'garamond': 'EBGaramond', 'georgia': 'LiberationSerif',
}


def faces(family):
    if family == 'EBGaramond':
        return [('EBGaramond.ttf', 'normal', '400 800'), ('EBGaramond-Italic.ttf', 'italic', '400 800')]
    return [(f'{family}-{suffix}.ttf', style, weight) for suffix, style, weight in [
        ('Regular', 'normal', '400'), ('Bold', 'normal', '700'),
        ('Italic', 'italic', '400'), ('BoldItalic', 'italic', '700'),
    ]]


FONT_FILES = frozenset(name for family in FAMILIES.values() for name, _, _ in faces(family))
