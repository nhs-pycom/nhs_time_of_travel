#!/bin/bash

# A shell script to run before committing, sending a pull request, etc.
# The aim is for this to run all the standard tasks to make sure nothing
# is broken, eg:
# - virtual environments
# - reformatting
# - running unit tests
# All current developers on the team are working on MacOS or linux, so
# so it has been tested on those environments.

# It is assumed this file will be run from the root directory of the project (.)

#
# Top level pipenv (for the nhs travel library)
#

# Make sure the Pipfile.lock is up to date with Pipfile
echo 'Making sure Pipfile.lock consistent with Pipfile'
pipenv install
# Make sure requirements.txt is up to date with Pipfile
echo 'Making sure requirements.txt consistent with Pipfile'
pipenv requirements > requirements.txt
# Run all the unit tests for the nhstravel library
echo 'Running nhstravel library unit tests'
pipenv run python3 -m unittest discover -s nhstraveltests

#
# Streamlit pipenv
#
cd streamlit
# Make sure the Pipfile.lock is up to date with Pipfile
echo 'Making sure streamlit Pipfile.lock consistent with Pipfile'
pipenv install
# Make sure requirements.txt is up to date with Pipfile
echo 'Making sure requirements.txt consistent with Pipfile'
pipenv requirements > requirements.txt
# Run all unit tests for streamlit within the streamlit pipenv
# This needs to discover from within the tests directory, but needs the top level directory to be streamlit (.)
echo 'Running streamlit functions unit tests'
pipenv run python3 -m unittest discover -s tests -t . -p '*_test.py'
cd ..



