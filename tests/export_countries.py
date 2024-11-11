# core_apps/users/management/commands/export_countries.py

from django.core.management.base import BaseCommand
from django_countries import countries
import json

class Command(BaseCommand):
    help = 'Export countries to JSON'

    def handle(self, *args, **kwargs):
        country_list = [{"code": code, "name": name} for code, name in countries]
        with open('countries.json', 'w', encoding='utf-8') as f:
            json.dump(country_list, f, ensure_ascii=False, indent=4)
        self.stdout.write(self.style.SUCCESS('Successfully exported countries.json'))
