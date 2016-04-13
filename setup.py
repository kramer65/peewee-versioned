from setuptools import setup, find_packages


setup(
    name='peewee-versioned',
    version='0.1',
    packages=find_packages(exclude=['test', 'test.*']),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'peewee',
        'six'
    ],
)
