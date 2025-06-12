import requests
from django.conf import settings
from core_apps.common.models import Occupation


def create_occupation_master():
    """
    It fetches data from the API and populates the database.
    """
    print("Starting to load occupation from API...")

    # API endpoint details
    url = f"{settings.BRIDGE_BASE_URL}/v0/lists/occupation_codes"
    headers = {'Api-Key': settings.BRIDGE_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data from API: {e}")
        return

    occupations_data = response.json()

    occupation_created_count = 0
    occupation_skipped_count = 0

    for occupation_data in occupations_data:
        occupation_name = occupation_data.get('display_name')
        occupation_code = occupation_data.get('code')

        if not occupation_name or not occupation_code:
            print(f"Skipping occupation with missing name or code: {occupation_data}")
            continue

        # Use update_or_create to handle both creation and updates in one go.
        occupation, created = Occupation.objects.update_or_create(
            name=occupation_name,
            defaults={'code': occupation_code}
        )
        if created:
            occupation_created_count += 1
            print(f'Successfully created occupation: {occupation.name}')
        else:
            occupation_skipped_count += 1
            # The 'defaults' in update_or_create handles the update automatically if the code differs.

    print('--- Data loading complete! ---')
    print(f'Occupation created: {occupation_created_count}')
    print(f'Occupation verified/updated: {occupation_skipped_count}')
