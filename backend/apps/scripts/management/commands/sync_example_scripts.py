"""
Management command: sync_example_scripts

Reads the canonical example scripts from the examples/ directory and upserts
the matching Script records in the database.

Usage:
    python manage.py sync_example_scripts            # dry-run (shows diff summary)
    python manage.py sync_example_scripts --apply    # write to DB
    python manage.py sync_example_scripts --apply --name "Linux Collector — Parser"
"""

import os
from difflib import unified_diff

from django.core.management.base import BaseCommand

from apps.scripts.models import Script

# Map DB script name → path relative to the project root (one level above backend/)
_SCRIPT_MAP = {
    'Linux Collector — Collector':   'examples/linux_baseline_collector.sh',
    'Linux Collector — Parser':      'examples/linux_baseline_parser.py',
    'Windows Collector — Collector': 'examples/windows_baseline_collector.ps1',
    'Windows Collector — Parser':    'examples/windows_baseline_parser.py',
    'ESXi Collector — Collector':    'examples/esxi_baseline_collector.sh',
    'ESXi Collector — Parser':       'examples/esxi_baseline_parser.py',
    'Cisco Switch Collector — Collector': 'examples/cisco_ios_baseline_collector.py',
    'Cisco Switch Collector — Parser':    'examples/cisco_ios_baseline_parser.py',
    'OpenVMS Collector — Collector': 'examples/openvms_baseline_collector.py',
    'OpenVMS Collector — Parser':    'examples/openvms_baseline_parser.py',
}


class Command(BaseCommand):
    help = 'Sync example scripts from the examples/ directory into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Write changes to the database (omit for dry-run).',
        )
        parser.add_argument(
            '--name',
            type=str,
            default=None,
            help='Only sync the script with this exact name.',
        )

    def handle(self, *args, **options):
        apply   = options['apply']
        only    = options['name']

        # Resolve the examples/ directory relative to this file:
        # backend/apps/scripts/management/commands/ → 5 levels up → backend/
        # then one more → project root
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
        )

        updated = 0
        skipped = 0
        missing = 0

        for name, rel_path in _SCRIPT_MAP.items():
            if only and name != only:
                continue

            file_path = os.path.join(base_dir, rel_path)
            if not os.path.isfile(file_path):
                self.stderr.write(self.style.WARNING(f'  MISSING file: {rel_path}'))
                missing += 1
                continue

            with open(file_path, 'r', encoding='utf-8') as fh:
                new_content = fh.read()

            try:
                script = Script.objects.get(name=name)
            except Script.DoesNotExist:
                self.stderr.write(self.style.WARNING(f'  NOT IN DB:   {name!r}'))
                missing += 1
                continue

            if script.content == new_content:
                self.stdout.write(f'  unchanged    {name}')
                skipped += 1
                continue

            # Show a compact diff
            old_lines = script.content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff = list(unified_diff(old_lines, new_lines, lineterm='', n=1))
            added   = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
            removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))

            if apply:
                script.content = new_content
                script.save(update_fields=['content', 'updated_at'])
                self.stdout.write(self.style.SUCCESS(
                    f'  updated      {name}  (+{added}/-{removed} lines)'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  would update {name}  (+{added}/-{removed} lines)'
                ))
            updated += 1

        self.stdout.write('')
        if apply:
            self.stdout.write(self.style.SUCCESS(
                f'Done. {updated} updated, {skipped} unchanged, {missing} not found.'
            ))
        else:
            self.stdout.write(
                f'Dry run. {updated} would update, {skipped} unchanged, {missing} not found.'
                '\nRe-run with --apply to write changes.'
            )
