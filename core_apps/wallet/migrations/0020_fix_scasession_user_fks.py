from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0019_fix_scasession_columns"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=r"""
                -- Add missing nullable FK columns to match GenericModel
                ALTER TABLE wallet_sca_session
                    ADD COLUMN IF NOT EXISTS created_by_id bigint NULL,
                    ADD COLUMN IF NOT EXISTS updated_by_id bigint NULL;

                -- Indexes for FK columns
                CREATE INDEX IF NOT EXISTS wallet_sca_session_created_by_idx
                    ON wallet_sca_session (created_by_id);
                CREATE INDEX IF NOT EXISTS wallet_sca_session_updated_by_idx
                    ON wallet_sca_session (updated_by_id);

                -- Add FK constraints to users_user(pkid) if not present
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'wallet_sca_session_created_by_id_fk'
                    ) THEN
                        ALTER TABLE wallet_sca_session
                            ADD CONSTRAINT wallet_sca_session_created_by_id_fk
                            FOREIGN KEY (created_by_id) REFERENCES users_user(pkid) DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END$$;

                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'wallet_sca_session_updated_by_id_fk'
                    ) THEN
                        ALTER TABLE wallet_sca_session
                            ADD CONSTRAINT wallet_sca_session_updated_by_id_fk
                            FOREIGN KEY (updated_by_id) REFERENCES users_user(pkid) DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END$$;
            """,
            reverse_sql=r"""
                -- Drop constraints, indexes, and columns added by this migration
                ALTER TABLE wallet_sca_session
                    DROP CONSTRAINT IF EXISTS wallet_sca_session_created_by_id_fk,
                    DROP CONSTRAINT IF EXISTS wallet_sca_session_updated_by_id_fk;

                DROP INDEX IF EXISTS wallet_sca_session_created_by_idx;
                DROP INDEX IF EXISTS wallet_sca_session_updated_by_idx;

                ALTER TABLE wallet_sca_session
                    DROP COLUMN IF EXISTS created_by_id,
                    DROP COLUMN IF EXISTS updated_by_id;
            """,
        ),
    ]
