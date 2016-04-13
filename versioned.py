'''
Provides a subclass of peewee Module ``VersionModule`` that automatically
adds a *_versions class and connects it to the proper signals
'''
import datetime

from six import with_metaclass  # py2 compat
from peewee import BaseModel, Model, DateTimeField, ForeignKeyField, IntegerField, BooleanField


class MetaModel(BaseModel):
    '''
    A MetaClass that automatically creates a nested subclass to track changes

    The nested subclass is referred to as ``VersionModel``
    '''

    # These fields will be added to the nested ``VersionModel``
    _version_fields = {'valid_from': DateTimeField(default=datetime.datetime.now, index=True),
                       'valid_until': DateTimeField(null=True, default=None,),
                       'deleted': BooleanField(default=False),
                       '_original_record_id': None,  # ForeignKeyField. Added later.
                       '_version_id': IntegerField(default=1),
                       '_id': IntegerField(primary_key=True)}  # Make an explicit primary key

    # Attribute of the parent class where the ``VersionModel`` can be accesed: Parent._VersionModel
    _version_model_attr_name = '_VersionModel'

    _version_model_name_suffix = 'Version'  # Example, People -> PeopleVersion

    _version_model_related_name = '_versions'  # Example People._versions.get()

    _RECURSION_BREAK_TEST = object()

    def __new__(self, name, bases, attrs):
        # Because the nested VersionModel shares this metaclass, we need to
        # test for it and act like :class:`peewee.BaseModel`
        if attrs.pop('_RECURSION_BREAK_TEST', None):
            VersionModel = BaseModel.__new__(self, name, bases, attrs)
            # Because ``VersionModel`` inherits from the initial class
            # we need to mask the reference to itself that is inheritied to avoid
            # infinite recursion and for detection
            setattr(VersionModel, self._version_model_attr_name, None)
            return VersionModel

        # This is not our nested ``VersionModel`` class
        # Create the class, create the nested ``VersionModel``, link them together.
        for field in attrs.keys():
            if (field in self._version_fields or
                    field == '_original_record'):  # _id suffix automatically truncated by peewee
                raise ValueError('You can not declare the attribute {}. '
                                 'It is automatically created by VersionedModel'.format(field))

        # Create the new class that has this class as it's metaclass
        new_class = super(MetaModel, self).__new__(self, name, bases, attrs)

        # Mung up the attributes for our ``VersionModel``
        version_model_attrs = self._version_fields.copy()
        version_model_attrs['__qualname__'] = name + self._version_model_name_suffix
        version_model_attrs['_original_record'] = ForeignKeyField(
            new_class, related_name=self._version_model_related_name
        )
        # needed to avoid infinite recursion
        version_model_attrs['_RECURSION_BREAK_TEST'] = self._RECURSION_BREAK_TEST

        # Create a new `*Version`` class that inherits from new_class
        VersionModel = type(name + self._version_model_name_suffix,  # Name
                            (new_class,),  # bases
                            version_model_attrs)  # attributes

        # Modify the newly created class before returning
        setattr(new_class, self._version_model_attr_name, VersionModel)
        setattr(new_class, '_version_model_attr_name', self._version_model_attr_name)
        setattr(new_class, '_version_fields', self._version_fields)

        return new_class


# Needed to allow subclassing with differing metaclasses. In this case, BaseModel and Type
class VersionedModel(with_metaclass(MetaModel, Model)):

    @classmethod
    def _is_version_model(cls):
        '''
        If this class is a nested ``VersionModel`` class created by :class:`MetaModel`
        this will return ``True``

        :return: bool
        '''
        return cls._get_version_model() is None

    @classmethod
    def _get_version_model(cls):
        '''
        :return: nested ``VersionModel``
        '''
        version_model = getattr(cls, cls._version_model_attr_name, None)
        return version_model

    def save(self, *args, **kwargs):
        # Default behaviour if this is a ``VersionModel``
        # Only update ``VersionModel if something has changed
        if (self._is_version_model() or
                not self.is_dirty()):
            return super(VersionedModel, self).save(*args, **kwargs)

        # wrap everything in a transaction: all or none
        with self._meta.database.atomic():
            # Save the parent
            super(VersionedModel, self).save(*args, **kwargs)

            # Finalize the previous version
            self._finalize_current_version()

            # Save the new version
            self._create_new_version()

    def delete_instance(self, *args, **kwargs):
        # default behaviour if this is a ``VersionModel``
        if self._is_version_model():
            return super(VersionedModel, self).delete_instance(*args, **kwargs)

        # wrap everything in a transaction: all or none
        with self._meta.database.atomic():

            # finalize the previous version
            self._finalize_current_version()

            # create a new version initialized to current values
            new_version = self._create_new_version(save=False)
            new_version.deleted = True
            new_version.save()

            # delete the parent
            super(VersionedModel, self).delete_instance(*args, **kwargs)

    @classmethod
    def create_table(cls, *args, **kwargs):
        # create the normal table schema
        super(VersionedModel, cls).create_table(*args, **kwargs)

        if not cls._is_version_model():
            # Create the tables for the nested version model, skip if it is the nested version model
            version_model = getattr(cls, cls._version_model_attr_name, None)
            version_model.create_table(*args, **kwargs)

    @classmethod
    def drop_table(cls, *args, **kwargs):
        # create the normal table schema
        super(VersionedModel, cls).drop_table(*args, **kwargs)
        # Create the tables for the nested version model. skip if it is the nested version model
        if not cls._is_version_model():
            version_model = getattr(cls, cls._version_model_attr_name, None)
            version_model.drop_table(*args, **kwargs)

    @property
    def version_id(self):
        '''
        :return: the version_id of the current version or ``None``

        '''
        if not self._is_version_model():
            current_version = self._get_current_version()
            return current_version.version_id
        else:
            return self._version_id

    def revert(self, version):
        '''
        Changes all attributes to match what was saved in ``version``
        This, in itself creates a new version.

        :param version: May be of type int, or an instance of the ``VersionModel``

        '''
        if self._is_version_model():
            raise RuntimeError('method revert can not be called on a VersionModel')

        VersionModel = self._get_version_model()
        if isinstance(version, VersionModel):
            version_model = version
        else:
            version_model = self._versions.filter(VersionModel._version_id == version).get()

        fields_to_copy = self._get_fields_to_copy()
        for field in fields_to_copy:
            setattr(self, field, getattr(version_model, field))

        self.save()

    @classmethod
    def _get_fields_to_copy(cls):
        version_model_fields_dict = cls._get_version_model()._meta.fields
        fields = []
        for key in version_model_fields_dict.keys():
            if not (key in cls._version_fields or key == '_original_record'):
                fields.append(key)
        return fields

    def _create_new_version(self, save=True):
        '''
        Creates a new row of ``VersionModel`` and initializes
        it's fields to match the parent.

        :param bool save: should the new_version be saved before returning?
        :return: the newly created instance of ``VersionModel``
        '''

        VersionModel = self._get_version_model()
        # Increment the version id to be one higher than the previous
        try:
            old_version = (self._versions
                           .select()
                           .order_by(VersionModel._version_id.desc())
                           .limit(1))[0]
            new_version_id = old_version.version_id + 1
        except IndexError:
            new_version_id = 1

        new_version = VersionModel()

        fields_to_copy = self._get_fields_to_copy()
        for field in fields_to_copy:
            setattr(new_version, field, getattr(self, field))
        new_version._original_record = self
        new_version._version_id = new_version_id
        if save is True:
            new_version.save()
        return new_version

    def _get_current_version(self):
        '''
        :return: current version or ``None`` if not found
        '''
        VersionModel = self._get_version_model()
        try:
            current_version = (self._versions.select()
                               .where(VersionModel.valid_until.is_null())
                               )  # null record
            assert(len(current_version) == 1)
            return current_version[0]
        except VersionModel.DoesNotExist:
            return None
        except AssertionError:
            if len(current_version) == 0:
                return None
            else:
                raise RuntimeError('Problem with the database. '
                                   'More than one current version was found for {}'
                                   .format(self.__class__))

    def _finalize_current_version(self):
        current_version = self._get_current_version()
        if current_version is not None:
            now = datetime.datetime.now()
            current_version.valid_until = now
            current_version.save()
