import os
import unittest

from peewee import CharField, BooleanField, ForeignKeyField, SqliteDatabase

from playhouse.db_url import connect
from playhouse.migrate import SqliteMigrator, MySQLMigrator, PostgresqlMigrator
from playhouse.reflection import Introspector

from . import VersionedModel
from . import migrate

# Setup Database
database_url = os.environ.get('DATABASE', None)
if database_url:
    database = connect(database_url)
    if database_url.startswith('mysql'):
        migrator = MySQLMigrator.from_database(database)
    if database_url.startswith('postgres'):
        migrator = PostgresqlMigrator.from_database(database)
    if database_url.startswith('sqlite'):
        migrator = SqliteMigrator.from_database(database)
    
else:
    database = SqliteDatabase(':memory:')
    migrator = SqliteMigrator.from_database(database)
    
introspector = Introspector.from_database(database)

# Basic example class
class BaseClass(VersionedModel):
    class Meta:
        database = database
    
    
class Food(BaseClass):
    name = CharField(null=True)
    is_tasty = BooleanField()
    
class Chow(BaseClass):
    name = CharField(null=True)
    is_tasty = BooleanField()
    
    
class Menu(BaseClass):
    name = CharField()


class TestMigrations(unittest.TestCase):
    def setUp(self):
        Food.create_table()
        Menu.create_table()

    def tearDown(self):
        try:
            Food.drop_table()
        except:
            # Food does not exist after rename_table_test
            Chow.drop_table()
        Menu.drop_table()
    
    ### Helper Functions ###
    
    def assertTableHasColumn(self, table, column, type_=None):
        models = introspector.generate_models()
        self.assertTrue(table in models, "table '{}' should be in models".format(table))
        self.assertTrue(column in models[table]._meta.fields, "column '{}' should be in fields".format(column))
        if type_ is not None:
            self.assertTrue(isinstance(models[table]._meta.fields[column], type_))

    def assertTableDoesNotHaveColumn(self, table, column):
        models = introspector.generate_models()
        self.assertTrue(table in models, "table '{}' should be in models".format(table))
        self.assertFalse(column in models[table]._meta.fields, "column '{}' should be in fields".format(column))

    def assertTableExists(self, table):
        models = introspector.generate_models()
        self.assertTrue(table in models, "table '{}' should be in models".format(table))
        
    def assertTableDoesNotExist(self, table):
        models = introspector.generate_models()
        self.assertFalse(table in models, "table '{}' should be in models".format(table))
    
    ### Tests ###
    
    def test_add_column(self):
        another_column = CharField(null=True)
        migrate(migrator.add_column('food', 'another_column', another_column))
        self.assertTableHasColumn('food', 'another_column', CharField)
        self.assertTableHasColumn('foodversion', 'another_column', CharField)
        
    def test_add_column_foreign_key(self):
        '''
        Versioned Models should not have foreign key references
        '''
        another_column = ForeignKeyField(Menu, related_name='food', null=True, to_field=Menu.id)
        migrate(migrator.add_column('food', 'another_column', another_column))
        self.assertTableHasColumn('food', 'another_column', ForeignKeyField)
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')

    def test_drop_column(self):
        migrate(migrator.drop_column('food', 'is_tasty'))
        self.assertTableDoesNotHaveColumn('food', 'is_tasty')
        self.assertTableDoesNotHaveColumn('foodversion', 'is_tasty')
        
    def test_drop_column_not_in_version(self):
        another_column = ForeignKeyField(Menu, related_name='food', null=True, to_field=Menu.id)
        migrate(migrator.add_column('food', 'another_column', another_column))
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        migrate(migrator.drop_column('food', 'another_column'))
        self.assertTableDoesNotHaveColumn('food', 'another_column')
        
    def test_rename_column(self):
        migrate(migrator.rename_column('food', 'is_tasty', 'was_tasty'))
        self.assertTableDoesNotHaveColumn('food', 'is_tasty')
        self.assertTableDoesNotHaveColumn('foodversion', 'is_tasty')
        self.assertTableHasColumn('food', 'was_tasty')
        self.assertTableHasColumn('foodversion', 'was_tasty')
        
    def test_rename_column_not_in_version(self):
        another_column = ForeignKeyField(Menu, related_name='food', null=True, to_field=Menu.id)
        migrate(migrator.add_column('food', 'another_column', another_column))
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        
        migrate(migrator.rename_column('food', 'another_column', 'new_column'))
        self.assertTableDoesNotHaveColumn('food', 'another_column')
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        self.assertTableHasColumn('food', 'new_column')
        self.assertTableDoesNotHaveColumn('foodversion', 'new_column')
        
    def test_add_not_null(self):
        models = introspector.generate_models()
        food = models['food']
        foodversion = models['foodversion']
        self.assertTrue(food.name.null)
        self.assertTrue(foodversion.name.null)

        migrate(migrator.add_not_null('food', 'name'))
        models = introspector.generate_models() 
        food = models['food']
        foodversion = models['foodversion']
        self.assertFalse(food.name.null)
        self.assertFalse(foodversion.name.null)
        
    def test_add_not_null_not_in_version(self):
        another_column = CharField(null=True, default='')
        migrate(migrator.add_column('food', 'another_column', another_column))
        
        # drop the field from the nested version
        migrator.drop_column('foodversion', 'another_column').run()
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        
        models = introspector.generate_models()
        food = models['food']
        self.assertTrue(food.another_column.null)

        migrate(migrator.add_not_null('food', 'another_column'))
        models = introspector.generate_models() 
        food = models['food']
        self.assertFalse(food.another_column.null)
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        
    def test_drop_not_null(self):
        models = introspector.generate_models()
        food = models['food']
        foodversion = models['foodversion']
        self.assertFalse(food.is_tasty.null)
        self.assertFalse(foodversion.is_tasty.null)

        migrate(migrator.drop_not_null('food', 'is_tasty'))
        models = introspector.generate_models() 
        food = models['food']
        foodversion = models['foodversion']
        self.assertTrue(food.is_tasty.null)
        self.assertTrue(foodversion.is_tasty.null)
        
    def test_drop_not_null_not_in_version(self):
        another_column = CharField(default='')
        migrate(migrator.add_column('food', 'another_column', another_column))
        
        # drop the field from the nested version
        migrator.drop_column('foodversion', 'another_column').run()
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
        
        models = introspector.generate_models()
        food = models['food']
        self.assertFalse(food.another_column.null)

        migrate(migrator.drop_not_null('food', 'another_column'))
        models = introspector.generate_models() 
        food = models['food']
        self.assertTrue(food.another_column.null)
        self.assertTableDoesNotHaveColumn('foodversion', 'another_column')
    
    def test_rename_table(self):
        self.assertTableExists('food')
        self.assertTableExists('foodversion')
        
        # Create some foods
        food_kwargs = ({'name': '1', 'is_tasty': False},
                 {'name': '2', 'is_tasty': False},
                 {'name': '3', 'is_tasty': False},
                 {'name': '4', 'is_tasty': False})
        
        for kwargs in food_kwargs:
            food = Food.create(**kwargs)
            
        migrate(migrator.rename_table('food', 'chow'))
        
        self.assertTableExists('chow')
        self.assertTableExists('chowversion')
        self.assertTableDoesNotExist('food')
        self.assertTableDoesNotExist('foodversion')
        
        # check to make sure the versions still exist
        for kwargs in food_kwargs:
            chow = Chow.get(Chow.name == kwargs['name'])
            self.assertEqual(len(chow._versions), 1)
            version = chow._versions[0]
            for key, value in kwargs.items():
                self.assertEqual(value, getattr(chow, key))
                self.assertEqual(value, getattr(version, key))
                
    def test_add_index(self):
        migrate(migrator.add_index('food', ['name']))
        models = introspector.generate_models()
        self.assertTrue(models['food'].name.index)
        self.assertFalse(models['foodversion'].name.index)
        
    def test_drop_index(self):
        # create an index
        migrate(migrator.add_index('food', ['name']))
        models = introspector.generate_models()
        self.assertTrue(models['food'].name.index)
        
        # Drop the index
        migrate(migrator.drop_index('food', 'food_name'))
        models = introspector.generate_models()
        self.assertFalse(models['food'].name.index)
        self.assertFalse(models['foodversion'].name.index)
            
            
