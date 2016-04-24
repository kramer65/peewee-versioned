# peewee_versioned


## Why this is awesome
Ever wanted to "undo" something in your database? Ever wondered what the value of a record was a year ago? Unfortunately the common relational database systems don't provide a way to look back in time, or "undo" changes. This is where peewee versioned comes in.

peewee_versioned provides ``VersionedModel`` which can be used to build ``peewee`` modules that automatically record any database changes. Any `INSERT`, `UPDATE` or `DELETE` action is recorded in an extra ~versioned table so that any record in the database can be reverted back to it's initial state.


## Disclaimer
This module was made for our own needs. If you find it usefull, go ahead and use it, but at your own risk. Also read the notes at the bottom of this readme.


## Usage

Create models like you normally do with peewee, but inherit from VersionModel:

    from peewee import CharField, DateField, BooleanField, SqliteDatabase
    from peewee_versioned import VersionedModel
    from pprint import pprint
    
    # Setup the database
    sqlite_database = SqliteDatabase(':memory:')
    
    
    # The actual tables we are interested in.
    class Person(VersionedModel):
        name = CharField()
        is_relative = BooleanField()
        class Meta:
            database = sqlite_database
    
    Person.create_table()

Now let's create a person:

    person = Person()
    person.name = 'Mike'
    person.is_relative = False
    person.save()

and we'll make some changes to the person and save them:

    person.is_relative = True
    person.save()  # Save the 1st change
    person.name = 'Mighty Mike'
    person.save()  # Save the 2nd change

This is what our person looks like
	
    >>> pprint(vars(person))
    {'_data': {'id': 1, 'is_relative': True, 'name': 'Mighty Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
 
and let's see what id and which version we're on

    >>> print person.id
    1
    >>> print person.version_id
    3

As you can see this is still the same record, but we're on the third version of it.

The best is still to come though. Let's say that we decide Mike is not so Mighty after all, and we want to revert the record back to its previous state. Using the `revert()` method we can do exactly that. We can either revert to a specific version_id by supplying a positive int to the revert method (`person.revert(2)`) or we can simply supply a negative number to go the desired steps back:

	>>> person.revert(-1)
	>>> person.name
	u'Mike'
	>>> person.version_id
	4

As you can see we successfully reverted back a version. Note though, that this adds a new version to the versions table with `_version_id` 4, which is essentially a copy of version 2. This might seem redundant, but for every version we also store from and until which moment in time they were in use. To not mess up this information we always create a new version, even if we revert.

Now let's see how all the previous versions look:
    
    >>> for version in person._versions:
            pprint(vars(version))
            
    {'_data': {'_deleted': False,
               '_id': 1,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 40, 650007),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 27, 49, 81846),
               '_version_id': 1,
               'is_relative': False,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 2,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 49, 83008),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 27, 49, 88289),
               '_version_id': 2,
               'is_relative': True,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 3,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 49, 89568),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 28, 17, 501130),
               '_version_id': 3,
               'is_relative': True,
               'name': u'Mighty Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 4,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 28, 17, 502327),
               '_valid_until': None,
               '_version_id': 4,
               'is_relative': True,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}


As you can see we've got 4 versions. Also, for each record we can see when exactly it was used. This comes in handy when you want to prove which information a person was looking at in the past. 

Now let's delete the person just like we normally do:

    >>> person.delete_instance()
    
Now that the person is gone, we need to go through the Person class to get the versions
    
    >>> versions = Person._VersionModel.select().order_by(person._VersionModel._id)
    >>> for version in versions:
            pprint(vars(version))

    {'_data': {'_deleted': False,
               '_id': 1,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 40, 650007),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 27, 49, 81846),
               '_version_id': 1,
               'is_relative': False,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 2,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 49, 83008),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 27, 49, 88289),
               '_version_id': 2,
               'is_relative': True,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 3,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 27, 49, 89568),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 28, 17, 501130),
               '_version_id': 3,
               'is_relative': True,
               'name': u'Mighty Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': False,
               '_id': 4,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 28, 17, 502327),
               '_valid_until': datetime.datetime(2016, 4, 24, 16, 29, 35, 526023),
               '_version_id': 4,
               'is_relative': True,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_deleted': True,  # <=== CHECK THIS OUT
               '_id': 5,
               '_original_record': 1,
               '_valid_from': datetime.datetime(2016, 4, 24, 16, 29, 35, 528095),
               '_valid_until': None,
               '_version_id': 5,
               'is_relative': True,
               'name': u'Mike'},
     '_dirty': set([]),
     '_obj_cache': {}}

As you can see also the action of deleting a record is stored. So all the actions of `CREATE`, `UPDATE` and `DELETE` are stored and can be retreived.


## Installation

	python setup.py install

installation through `pip` will be added later.


## Notes

Tested on python 3.5 and 2.7

The ``VersionModel`` is saved to the parent class as _VersionModel. eg::
    
    Person._VersionModel
    
The ``VersionModel`` class uses the non-standard ``_id`` attribute instead of ``id`` to store the primary key. This 
is to avoid conflicts. eg::

    order_by(People._VersionModel._id)  # Note ``_id``, not ``id``

The following attributes can not be used in classes that inherit from ``VersionedModel``
    * _valid_from
    * _valid_until
    * _deleted
    * _original_record_id
    * _original_record
    * _id

 - If you bypass the normal ``save()``, ``create()``, and ``delete_instance()`` methods, signals will not be sent, and 
the model history will not be saved. The dangerous commands I've noticed from testing include: (there may be more)

    * .insert()
    * .insert_many()
    * .delete()  # class level

All datetimes in `_valid_from` and `_valid_until` are in UTC. 

## Testing

### Current Environment

    pip install pytest
    py.test test_versioned.py
    
### Multiple versions of python (3.5 and 2.7)

    pip install tox
    tox
