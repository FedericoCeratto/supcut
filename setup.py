from setuptools import setup, find_packages
import sys, os

version = '0.5'

setup(name='supcut',
      version=version,
      description="Simple unobtrusive Python continuous unit testing",
      long_description="""\
A rather hassle-free tool to run nose based unit testing locally.""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='nose unit-testing',
      author='Federico Ceratto',
      author_email='federico.ceratto@gmail.com',
      url='https://github.com/FedericoCeratto/supcu',
      license='GPLv3',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
