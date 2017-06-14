from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='PyElk',
        version='0.1.4.dev1',
        description='Python module to talk to Elk M1 Gold and M1 EZ8  security / integration panels.',
        long_description=readme(),
        url='https://github.com/BioSehnsucht/pyelk',
        author='Jonathan Vaughn',
        author_email='biosehnsucht+pyelk@gmail.com',
        license='Apache License 2.0',
        packages=[
            'PyElk',
            'PyElk.Area',
            'PyElk.Event',
            'PyElk.Keypad',
            'PyElk.Node',
            'PyElk.Output',
            'PyElk.Thermostat',
            'PyElk.X10',
            'PyElk.Zone',
            ],
        include_package_data=True,
        classifiers=[
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Development Status :: 3 - Alpha',
            'License :: OSI Approved :: Apache Software License',
            'Programming Language :: Python :: 3',
            'Topic :: Software Development :: Libraries :: Python Modules'
            ],
        zip_safe=False)
