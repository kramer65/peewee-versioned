from copy import copy

from peewee import RelationDescriptor

from playhouse.migrate import Operation
from playhouse.reflection import Introspector



NOOP_OPERATIONS = {
    'add_index', # no-op
    'drop_index' # no-op
}



def migrate(*operations, **kwargs):
    '''
    A wraper around :func:playhouse.migrate.migrate:
    
    This method ensures that the same migrations are performed on nested :class:peewee_versioned.VersionedModel:'s
    '''
    
    # Collect nested classes
    databases_models_map = {}
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
        version_args = args.copy()
        version_kwargs = kwargs.copy()
        
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
        models = databases_models_map.get(database, None)
        if models is None:
            introspector = Introspector.from_database(database)
            models = introspector.generate_models(skip_invalid=True)
            databases_models_map[database] = models
        
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
                if isinstance(field, RelationDescriptor):
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
                new_name = kwargs.get('new_name', None)
                if new_name is not None:
                    version_kwargs['new_name'] = new_name + 'version'
                else:
                    version_args[1] = new_name + 'version'
                    
            # I guess we have a valid operation, so we will create and run it for the nested verion model
            version_operation = Operation(migrator, method, *version_args, **version_kwargs)
            version_operation.run()
        
        # Run the original operation too!
        operation.run()


