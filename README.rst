About
=====

Craptastic ES scraper.


Run it
------

`tox -e pyNN`


Known Issues
------------

 - Currently only checks against neutron
 - It takes about 10 minutes to run.
 - If ES barfs a timeout right at the start (first 30 seconds) try re-running it a few times. (Todo: handle this in app)


Maybe Todo
----------

 - Check logs for obvious known failures, ex grep for tox exploading due to envlist bug
 - Fix ES barf
 - Make it accept options for project to check
 - reduce # of dropped checks
