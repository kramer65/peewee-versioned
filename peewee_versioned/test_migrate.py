import os
import unittest

from peewee import CharField, DateField, BooleanField, ForeignKeyField, SqliteDatabase

from playhouse.db_url import connect
from playhouse.migrate import SqliteMigrator, MySQLMigrator, PostgresqlMigrator

from . import VersionedModel
from . import migrate


database_url = os.environ.get('DATABASE', None)
if database_url:
    database = connect(database_url)
    if database_url.startswith('mysql'):
        Migrator = MySQLMigrator
    if database_url.startswith('postgres'):
        Migrator = PostgresqlMigrator
    if database_url.startswith('sqlite'):
        Migrator = SqliteMigrator
    
else:
    database = SqliteDatabase(':memory:')
    Migrator = SqliteMigrator

# Basic example class
class BaseClass(VersionedModel):
    class Meta:
        database = database
    
    
class Food(BaseClass):
    name = CharField()
    is_tasty = BooleanField()


class TestMigrations(unittest.TestCase):
    def setUp(self):
        Food.create_table()
        self.migrator = Migrator(database)

    def tearDown(self):
        Food.drop_table()

    def test_add_column(self):
        Food.another_column = CharField(null=True)
        migrate(self.migrator.add_column('food', 'another_column', Food.another_column))
        # TODO: How to test if another_column now actually exists in both the `food` table as the `foodversioned` table?

    def test_drop_column(self):
        del Food.is_tasty
        migrate(self.migrator.drop_column('food', 'is_tasty'))
        # TODO: How to test if `is_tasty` has actually been dropped from both the `food` table as the `foodversioned` table?