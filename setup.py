from setuptools import setup

setup (
  name='wsk',
  version='0.1.7',
  packages=['wsk'],
  description="A light wrapper for LexisNexis's Web Services Kit API",
  url='https://github.com/YaleDHLab/lexis-nexis-wsk',
  author='Douglas Duhaime',
  author_email='douglas.duhaime@gmail.com',
  license='MIT',
  install_requires=[
    'beautifulsoup4==4.5.1',
    'pymongo==3.3.1',
  ],
)