from django.core.management.base import BaseCommand
from django_countries import countries
import json
import os

class Command(BaseCommand):
    help = 'Export countries to JSON'

    def handle(self, *args, **kwargs):
        country_list = [{"code": code, "name": name} for code, name in countries]

        output_path = os.path.join('core_apps', 'users', 'management', 'commands', 'countries.json')

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(country_list, f, ensure_ascii=False, indent=4)
            self.stdout.write(self.style.SUCCESS(f'Successfully exported countries.json to {output_path}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error exporting countries.json: {e}'))
