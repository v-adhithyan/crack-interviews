from datetime import timedelta
import logging
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import PublicBuilderCounter


def metric(event, amount=1):
    """Internal fixed event names and daily totals; never pass request/user data."""
    try:
        with transaction.atomic():
            key = f'metric:{timezone.now().date()}:{event}'
            row, _ = PublicBuilderCounter.objects.get_or_create(key=key, defaults={'expires_at': timezone.now() + timedelta(days=90)})
            PublicBuilderCounter.objects.filter(pk=row.pk).update(count=F('count') + amount)
    except Exception:
        logging.getLogger(__name__).warning('Public resume aggregate metric unavailable event=%s', event)
