import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DJANGO_SETTINGS_MODULE'] = 'telportal.settings'
import django
django.setup()

# Check if migrations need to be created by comparing state
from django.core.management import call_command

# Force recreate by clearing caches and checking
import importlib
import assessment.models as models
importlib.reload(models)

# Create migration file manually based on what we know the model changes are
from django.db.migrations.state import ProjectState, ModelState
from django.db.migrations.writer import MigrationWriter

# Let's just check the migration directory
from django.conf import settings
print("Migration dir:", settings.BASE_DIR / 'assessment' / 'migrations')
print("MIGRATION_MODULES:", getattr(settings, 'MIGRATION_MODULES', 'not set'))

# Check what migrations exist
from django.db.migrations.loader import MigrationLoader
loader = MigrationLoader(None)
print("Existing assessment migrations:", list(loader.disk_relations.get('assessment', {}).keys()))

# Try creating an empty migration to start fresh
call_command('makemigrations', 'assessment', '--empty', '--name', 'initial_visibility', '--verbosity', '2')
