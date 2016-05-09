from copy import copy

from peewee import ForeignKeyField

from playhouse.migrate import Operation
from playhouse.reflection import Introspector



NOOP_OPERATIONS = {
    'add_index', # no-op
    'drop_index' # no-op
}


def _rename_table(operation, migrator, introspector, old_name, new_name):
    version_old_name = old_name + 'version'
    version_new_name = new_name + 'version'
    
    # save all of the foreign key references
    models = introspector.generate_models()
    OldVersion = models[version_old_name]
    
    # The name of the original record's primary key
    to_field_name = OldVersion._original_record.to_field.name
    
    version_id__original_id = []
    for version in OldVersion.select(OldVersion._id, OldVersion._original_record):
        version_id__original_id.append((version._id, version._original_record_id))
        
    # drop the foreign key field in the OldVersion model
    drop_field = Operation(migrator, 'drop_column', version_old_name, '_original_record_id')
    drop_field.run()
    
    # rename the original table
    operation.run()
    # rename the version table
    version_rename_table = Operation(migrator, 'rename_table', version_old_name, version_new_name)
    version_rename_table.run()
    
    # lookup the new model so we can add a foreign key to it
    models = introspector.generate_models()
    NewModel = models[new_name]
    
    # Add a new Foregin key reference
    _original_record = ForeignKeyField(
        NewModel, null=True, on_delete="SET NULL",
        to_field=getattr(NewModel, to_field_name)
    )
    add_foregin_key = Operation(migrator, 'add_column', version_new_name, '_original_record_id', _original_record)
    add_foregin_key.run()
    
    # load the new version model with the foregin key
    models = introspector.generate_models()
    NewModel = models[new_name]
    NewVersionModel = models[version_new_name]
    
    # re link all versions
    for _id, _original_record_id in version_id__original_id:
        version = NewVersionModel.get(NewVersionModel._id == _id)
        # ``to_field_name`` is the name of the original record's primary key
        model = NewModel.get(getattr(NewModel, to_field_name) == _original_record_id)
        version._original_record = model
        version.save() 


def migrate(*operations, **kwargs):
    '''
    A wraper around :func:playhouse.migrate.migrate:
    
    This method ensures that the same migrations are performed on nested :class:peewee_versioned.VersionedModel:'s
    '''
    
    # Collect nested classes
    for operation in operations:
        migrator = operation.migrator
        database = operation.migrator.database
        method = operation.method
        args = list(copy(operation.args))
        kwargs = operation.kwargs.copy()
        
        # Exit early for NOOP methods
        if method in NOOP_OPERATIONS:
            operation.run()
            continue
        
        # potential arguments to be used with the nested class
        version_args = copy(args)
        version_kwargs = kwargs.copy()
        
        # potential operation to run on the nested class
        version_operation = None
        
        # Get the table name of the operation
        # Update version args/kwargs
        if method == 'rename_table':
            table = kwargs.get('old_name', None)
            if table is not None:
                version_kwargs['old_name'] = table + 'version'
        else:
            table = kwargs.get('table', None)
            if table is not None:
                version_kwargs['table'] = table + 'version'
        if table is None:
            table = args[0]
            version_args[0] = table + 'version'
        
        # Read models from the database and cache
        introspector = Introspector.from_database(database)
        models = introspector.generate_models(skip_invalid=True)
        
        # Test if the model has a version model associated with it
        version_name = table + 'version'
        if version_name in models:
            version_model = models[version_name]
            version_fields = version_model._meta.fields
            
            # Handle special cases first
            if method == 'add_column':
                # Don't add foreign keys
                field = kwargs.get('field', None)
                if field is None:
                    field = args[2]
                if isinstance(field, ForeignKeyField):
                    operation.run()
                    continue
            elif method == 'drop_column':
                column_name = kwargs.get('column_name', None)
                if column_name is None:
                    column_name = args[1]
                if column_name not in version_fields:
                    operation.run()
                    continue
            elif method == 'rename_column':
                old_name = kwargs.get('old_name', None)
                if old_name is None:
                    old_name = args[1]
                if old_name not in version_fields:
                    operation.run()
                    continue
            elif method in ('add_not_null', 'drop_not_null'):
                column = kwargs.get('column', None)
                if column is None:
                    column = args[1]
                if column not in version_fields:
                    operation.run()
                    continue
            elif method == 'rename_table':
                old_name = kwargs.get('old_name', None)
                if old_name is None:
                    old_name = args[0]
                new_name = kwargs.get('new_name', None)
                if new_name is None:
                    new_name = version_args[1]
                
                _rename_table(operation, migrator, introspector, old_name, new_name)
                continue
                
                    
            # I guess we have a valid operation, so we will create and run it for the nested verion model
            version_operation = Operation(migrator, method, *version_args, **version_kwargs)
            
        
        # Run the operations
        operation.run()
        if version_operation is not None:
            version_operation.run()
