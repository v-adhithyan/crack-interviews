import uuid

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.product.models import MockInterviewSession


class Command(BaseCommand):
    help = "Backfill public share UUIDs for existing mock interview sessions."

    def handle(self, *args, **options):
        updated = 0

        missing_session_ids = MockInterviewSession.objects.filter(share_uuid__isnull=True).values_list("id", flat=True)
        for session_id in missing_session_ids.iterator():
            MockInterviewSession.objects.filter(id=session_id).update(share_uuid=uuid.uuid4())
            updated += 1

        duplicate_values = (
            MockInterviewSession.objects.values("share_uuid")
            .exclude(share_uuid__isnull=True)
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for duplicate in duplicate_values:
            session_ids = list(
                MockInterviewSession.objects.filter(share_uuid=duplicate["share_uuid"])
                .order_by("id")
                .values_list("id", flat=True)
            )
            for session_id in session_ids[1:]:
                MockInterviewSession.objects.filter(id=session_id).update(share_uuid=uuid.uuid4())
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Backfilled {updated} mock interview share link(s)."))
