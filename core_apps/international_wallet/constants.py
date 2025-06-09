from django.utils.translation import gettext_lazy as _


COUNTRY_CODE_BRIDGE = (
    ('US', _('usa')),
)


def get_country_name_from_code(code):
    """
    Retrieves the country name from COUNTRY_CODE_BRIDGE given a country code.
    """
    for country_code, country_name in COUNTRY_CODE_BRIDGE:
        if country_code == code:
            return str(country_name)
    return None # Return None if the code is not found
