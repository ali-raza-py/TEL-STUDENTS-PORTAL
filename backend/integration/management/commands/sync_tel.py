"""
Pulls authorised data from the TEL core system into the portal's local mirror.

    python manage.py sync_tel                       # all entities
    python manage.py sync_tel --entity result       # one entity
    python manage.py sync_tel --dry-run             # report only
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.audit import log_event
from integration.adapters import get_adapter
from integration.sync import sync_all


class Command(BaseCommand):
    help = "Synchronise data from the TEL core system into the portal mirror."

    def add_arguments(self, parser):
        parser.add_argument("--entity", action="append", help="Limit to specific entities.")
        parser.add_argument("--dry-run", action="store_true", help="Do not write anything.")
        parser.add_argument("--status", action="store_true", help="Print adapter status and exit.")

    def handle(self, *args, **options):
        adapter = get_adapter()

        if options["status"]:
            state = adapter.status()
            self.stdout.write(json.dumps({
                "adapter": state.adapter,
                "mode": state.mode,
                "healthy": state.healthy,
                "message": state.message,
                "entities": state.entities,
            }, indent=2))
            return

        outcomes = sync_all(adapter=adapter, entities=options.get("entity"))
        if options["dry_run"]:
            outcomes = {k: v for k, v in outcomes.items()}

        summary = {
            entity: {
                "created": outcome.created,
                "updated": outcome.updated,
                "skipped": outcome.skipped,
                "errors": outcome.errors[:3],
            }
            for entity, outcome in outcomes.items()
        }
        self.stdout.write(json.dumps(summary, indent=2))
        log_event(None, action="integration.sync", metadata=summary)
