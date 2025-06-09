import requests
from django.conf import settings
from core_apps.common.models import Country, State


def create_state_country_master():
    """
    It fetches data from the API and populates the database.
    """
    print("Starting to load countries and states from API...")

    # API endpoint details
    url = f"{settings.BRIDGE_BASE_URL}/v0/lists/countries"
    headers = {'Api-Key': settings.BRIDGE_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data from API: {e}")
        return

    data = response.json()
    countries_data = data.get('data', [])

    countries_created_count = 0
    states_created_count = 0
    countries_skipped_count = 0
    states_skipped_count = 0

    for country_data in countries_data:
        country_name = country_data.get('name')
        country_code = country_data.get('alpha3')

        if not country_name or not country_code:
            print(f"Skipping country with missing name or code: {country_data}")
            continue

        # Use update_or_create to handle both creation and updates in one go.
        country, created = Country.objects.update_or_create(
            name=country_name,
            postal_code_format=country_data.get('postal_code_format', ''),
            defaults={'code': country_code}
        )

        if created:
            countries_created_count += 1
            print(f'Successfully created country: {country.name}')
        else:
            countries_skipped_count += 1
            # The 'defaults' in update_or_create handles the update automatically if the code differs.

        subdivisions = country_data.get('subdivisions', [])
        if subdivisions:
            for state_data in subdivisions:
                state_name = state_data.get('name')
                state_code = state_data.get('code')

                if not state_name or not state_code:
                    print(f"Skipping state with missing name or code for country {country.name}: {state_data}")
                    continue

                state, created = State.objects.update_or_create(
                    name=state_name,
                    country=country,
                    defaults={'code': state_code}
                )

                if created:
                    states_created_count += 1
                    print(f'  - Created state: {state.name} for {country.name}')
                else:
                    states_skipped_count += 1

    print('--- Data loading complete! ---')
    print(f'Countries created: {countries_created_count}')
    print(f'Countries verified/updated: {countries_skipped_count}')
    print(f'States created: {states_created_count}')
    print(f'States verified/updated: {states_skipped_count}')
