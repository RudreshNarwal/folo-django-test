from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0018_scasession_scasession_wallet_sca__intent__1556ba_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Ensure required audit columns exist on wallet_sca_session
                ALTER TABLE wallet_sca_session
                    ADD COLUMN IF NOT EXISTS created_on timestamptz NOT NULL DEFAULT NOW();

                ALTER TABLE wallet_sca_session
                    ADD COLUMN IF NOT EXISTS updated_on timestamptz NOT NULL DEFAULT NOW();

                ALTER TABLE wallet_sca_session
                    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT TRUE;

                -- Match model's db_index=True for updated_on
                CREATE INDEX IF NOT EXISTS wallet_sca_session_updated_on_idx
                    ON wallet_sca_session (updated_on);
            """,
            reverse_sql="""
                -- Reverse cautiously (drops added artifacts only)
                DROP INDEX IF EXISTS wallet_sca_session_updated_on_idx;
                ALTER TABLE wallet_sca_session DROP COLUMN IF EXISTS is_active;
                ALTER TABLE wallet_sca_session DROP COLUMN IF EXISTS updated_on;
                ALTER TABLE wallet_sca_session DROP COLUMN IF EXISTS created_on;
            """,
        ),
    ]
