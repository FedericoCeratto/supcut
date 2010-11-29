from setuptools import setup, find_packages
import sys, os

from supcut.supcut import __version__ as version

setup(name='supcut',
      version=version,
      description="Simple unobtrusive Python continuous unit testing",
      long_description="""\
A rather hassle-free tool to run nose based unit testing locally.""",
      classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: Software Development :: Testing',
        'Development Status :: 4 - Beta',
      ],
      keywords='nose unit-testing',
      author='Federico Ceratto',
      author_email='federico.ceratto@gmail.com',
      url='http://github.com/FedericoCeratto/supcut',
      license='GPLv3',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points={
        'console_scripts': ['supcut = supcut.supcut:main'],
      },
)
