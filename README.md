# peewee_versioned

## Why this is awesome
Ever wanted to "undo" something in your database? Ever wondered what the value of a record was a year ago? Unfortunately the common relational database systems (MySQL, Postgres etc.) don't provide a way to look back in time, or "undo" changes. This is where peewee versioned comes in.

peewee_versioned provides ``VersionedModel`` which can be used to build ``peewee`` modules that automatically record any database changes. Any `INSERT`s, `UPDATE`s and `DELETE`s are recorded in an extra ~versioned table so that any record in the database can be reverted back to it's initial state.

This module was made for our own needs. If you find it usefull, go ahead and use it, but at your own risk.


## Installation

	python setup.py install

## Basic Usage

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

    >>> person = Person()
    >>> person.name = 'Mike'
    >>> person.is_relative = False
    >>> person.save()

and we'll make some changes to the person and save them:

    >>> person.is_relative = True
    >>> person.save()  # Save the 1st change
	>>> person.name = 'Mighty Mike'
    >>> person.save()  # Save the 2nd change

This is what our person looks like
	
    >>> pprint(vars(person))
	{'_data': {'id': 1, 'is_relative': True, 'name': 'Mighty Mike'},
	 '_dirty': set([]),
	 '_obj_cache': {}}
 
And this is what the versions look like:

    >>> versions = person._versions.order_by(person._VersionModel._id)
    >>> for version in versions:
            pprint(vars(version))
    {'_data': {'_id': 1,
               '_original_record': 1,
               '_version_id': 1,
               'deleted': False,
               'is_relative': False,
               'name': u'Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 58, 14, 280888),
               'valid_until': datetime.datetime(2016, 4, 19, 15, 58, 27, 580842)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 2,
               '_original_record': 1,
               '_version_id': 2,
               'deleted': False,
               'is_relative': True,
               'name': u'Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 58, 27, 582761),
               'valid_until': datetime.datetime(2016, 4, 19, 15, 59, 37, 886377)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 3,
               '_original_record': 1,
               '_version_id': 3,
               'deleted': False,
               'is_relative': True,
               'name': u'Mighty Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 59, 37, 887238),
               'valid_until': None},
     '_dirty': set([]),
     '_obj_cache': {}}


As you can see we've got 3 versions with a `_version_id` which is incremented by one. Also, for each record we can see when exactly it was used. This comes in handy when you want to prove which information a person was looking at in the past. 

The best is still to come though. Let's say that we decide Mike is not so Mighty after all, and we want to revert the record back to its previous state. Using the `revert()` method we can do exactly that. We'll revert to version 2:

	>>> person.revert(2)
	>>> print person.name
	u'Mike'

As you can see we successfully reverted back a version. Note though, that this adds a new version to the versions table with `_version_id` 4 which is essentially a copy of version 2. This might seem redundant, but if you would simply go back to version id 2, the valid_from and valid_until wouldn't make sense anymore.

Now let's delete the person:

    >>> person.delete_instance()
    
Now that the person is gone, we need to go through the Person class to get the versions
    
    >>> versions = Person._VersionModel.select().order_by(person._VersionModel._id)
    >>> for version in versions:
            pprint(vars(version))

    {'_data': {'_id': 1,
               '_original_record': 1,
               '_version_id': 1,
               'deleted': False,
               'is_relative': False,
               'name': u'Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 58, 14, 280888),
               'valid_until': datetime.datetime(2016, 4, 19, 15, 58, 27, 580842)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 2,
               '_original_record': 1,
               '_version_id': 2,
               'deleted': False,
               'is_relative': True,
               'name': u'Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 58, 27, 582761),
               'valid_until': datetime.datetime(2016, 4, 19, 15, 59, 37, 886377)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 3,
               '_original_record': 1,
               '_version_id': 3,
               'deleted': False,
               'is_relative': True,
               'name': u'Mighty Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 59, 37, 887238),
               'valid_until': datetime.datetime(2016, 4, 19, 16, 3, 47, 915535)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 4,
               '_original_record': 1,
               '_version_id': 4,
               'deleted': False,
               'is_relative': True,
               'name': u'Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 15, 59, 37, 887238),
               'valid_until': datetime.datetime(2016, 4, 19, 16, 3, 47, 915535)},
     '_dirty': set([]),
     '_obj_cache': {}}
    {'_data': {'_id': 5,
               '_original_record': 1,
               '_version_id': 5,
               'deleted': True,
               'is_relative': True,
               'name': u'Mighty Mike',
               'valid_from': datetime.datetime(2016, 4, 19, 16, 3, 47, 917835),
               'valid_until': None},
     '_dirty': set([]),
     '_obj_cache': {}}
     
     

## Notes


Tested on python 3.5 and 2.7

The ``VersionModel`` is saved to the parent class as _VersionModel. eg::
    
    Person._VersionModel
    
The ``VersionModel`` class uses the non-standard ``_id`` attribute instead of ``id`` to store the primary key. This 
is to avoid conflicts. eg::

    order_by(People._VersionModel._id)  # Note ``_id``, not ``id``

The following attributes can not be used in classes that inherit from ``VersionedModel``
    * valid_from
    * valid_until
    * deleted
    * _original_record_id
    * _original_record
    * _id

 - If you bypass the normal ``save()``, ``create()``, and ``delete_instance()`` methods, signals will not be sent, and 
the model history will not be saved. The dangerous commands I've noticed from testing include: (there may be more)

    * .insert()
    * .insert_many()
    * .delete()  # class level


## Testing


### Current Environment


    pip install pytest
    py.test
    
### Multiple versions of python (3.5 and 2.7)

    pip install tox
    tox
