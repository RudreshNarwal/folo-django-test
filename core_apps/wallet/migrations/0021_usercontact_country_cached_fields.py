# Generated migration for UserContact cached country fields

from django.db import migrations, models


def populate_cached_country_fields(apps, schema_editor):
    """Populate cached country fields for existing UserContact records."""
    UserContact = apps.get_model('wallet', 'UserContact')

    # Import here to avoid circular imports in migration
    from core_apps.users.utils import get_country_from_country_code
    import phonenumbers

    contacts_updated = 0
    contacts_failed = 0

    for contact in UserContact.objects.all():
        if contact.phone_number:
            try:
                # Extract country code from phone number using the same logic as the property
                phone_str = str(contact.phone_number).strip()

                # PhoneNumberField should store in E164 format, so try to extract country code
                if phone_str.startswith('+'):
                    # E164 format: +254712345678 -> country_code = +254
                    try:
                        parsed = phonenumbers.parse(phone_str, None)
                        country_code = f"+{parsed.country_code}"
                    except:
                        # If parsing fails, assume it's Kenyan (most common case)
                        country_code = '+254'
                else:
                    # Fallback for any non-E164 format (shouldn't happen with PhoneNumberField)
                    country_code = '+254'

                # Get country from mapping
                country = get_country_from_country_code(country_code)

                # Update cached fields
                contact.country_code_cached = country_code
                contact.country_cached = country
                contact.save(update_fields=['country_code_cached', 'country_cached'])

                contacts_updated += 1

            except Exception as e:
                # Log errors but continue processing other contacts
                phone_str = str(contact.phone_number)[:20] + "..." if len(str(contact.phone_number)) > 20 else str(contact.phone_number)
                print(f"Error processing contact {contact.id} (phone: {phone_str}): {e}")
                contacts_failed += 1
                continue

    print(f"Migration completed: {contacts_updated} contacts updated, {contacts_failed} failed")


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0020_usercontact_source_alter_usercontact_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usercontact',
            name='country_cached',
            field=models.CharField(
                blank=True,
                help_text='Cached country ISO code (e.g., KE) for performance',
                max_length=2,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='usercontact',
            name='country_code_cached',
            field=models.CharField(
                blank=True,
                help_text='Cached country code (e.g., +254) for performance',
                max_length=5,
                null=True
            ),
        ),
        migrations.RunPython(
            populate_cached_country_fields,
            reverse_code=migrations.RunPython.noop
        ),
    ]