from setuptools import setup, find_packages
import sys, os

version='0.5.1'

setup(name='supcut',
      version=version,
      description="Simple unobtrusive Python continuous unit testing",
      long_description="""\
A rather hassle-free tool to run nose based unit testing locally.
It runs nosetests upon any file change and displays changes in the sets of
failing or successful tests via OSD.
""",
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
        'pyinotify',
        'pygtk',
      ],
      entry_points={
        'console_scripts': ['supcut = supcut.supcut:main'],
      },
)
