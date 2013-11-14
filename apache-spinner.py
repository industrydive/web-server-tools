"""
Restarts Apache by checking if the site is down.
"""

import os
import subprocess
import logging

# time between two consecutive restart attempts (in seconds)
RESTART_INTERVAL = 10 # 60 * 60
LOCK_FILE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'apache-spinner.lock')
URL = 'http://educationdive.com'
APACHE_LOG_FILE = '/var/log/apache2/error.log'
LOG_FILE = 'apache-spinner.log'

logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, filemode='w')
logger = logging.getLogger(__file__)

def create_lockfile():
    lockfile = open(LOCK_FILE_PATH, 'w')
    return lockfile

def check_page(content):
    needles = ['Education Dive', 'Industry Dive', 
    'Education Industry', 'Dashboard', 'Press Releases']
    missing = filter(lambda x: x not in content, needles)
    if len(missing):
        return (False, 'Missing string "%s" in page content.' % missing[0])
    return (True, 'Success')

def safe_to_restart():
    from datetime import datetime, timedelta
    import time

    def _enough_time_passed():
        try:
            last_restart_line = subprocess.check_output("cat %s | grep 'resuming' | tail -n 1" % APACHE_LOG_FILE, shell=True)
            last_restart = last_restart_line.split(']', 1)[0].lstrip('[')
            last_restart = time.strptime(last_restart, '%a %b %d %H:%M:%S %Y')
            last_restart = datetime.fromtimestamp(time.mktime(last_restart))
            logger.info("Last Apache restart was: %s" % last_restart)
            interval = timedelta(seconds=RESTART_INTERVAL)
            enough_time_passed = datetime.now() > last_restart + interval

            if not enough_time_passed:
                remaining = last_restart + interval - datetime.now()
                msg = "Not enough time passed from last restart. Remaining %s seconds." % remaining.seconds
                return (False, msg)
            else:
                remaining = datetime.now() - last_restart
                msg = "Enough time has passed from last restart (%s seconds)." % remaining.seconds
                return (True, msg)

        except Exception as e:
            logger.info("Exception at function 'enough_time_passed'")
            raise e

    def _lockfile_exists():
        return os.path.isfile(LOCK_FILE_PATH)
   
    (time_passed, msg) = _enough_time_passed()
    logger.info(msg)

    if _lockfile_exists():
        return (False, 'Lock file exists. Another process is running maybe?')
    elif not time_passed:
        return (False, msg)

    return (True, '')

def restart_apache():
    # create lock file
    create_lockfile()
    # restart Apache
    result = subprocess.Popen(['service', 'apache2', 'restart'], stdout=subprocess.PIPE)
    output = result.stdout.read()
    result.wait()
    logger.info(output)
    # destroy lock file
    os.unlink(LOCK_FILE_PATH)
    return result.returncode

def main():
    import requests

    logger.info("Requesting a page from: %s" % URL)
    response = requests.get(URL)
    status = response.status_code
    (success, check_page_msg) = check_page(response.content)
    logger.info("Got response back: %s" % response)

    if status == 200 and success:
        logger.info("Response status code looks okay.")
        logger.info("The fetched page seems fine enough.")
        return
    else:
        if not status:
            logger.warning("Got an unexpected response status code: %s" % status)
        elif not success:
            logger.warning("Got an unexpected page content: %s" % check_page_msg)

    initiate_restart()

def initiate_restart():
    logger.info("Looking to restarting Apache...")
    (okay_to_restart, msg) = safe_to_restart()

    if okay_to_restart:
        logger.info("Restarting Apache...")
        ret = restart_apache()
        if ret == 0:
            logger.info("Apache successfully restarted.")
        else:
            logger.warning("Apache restart got unexpected exit code: %s" % ret)
    else:
        logger.info("Not going to restart apache. Reason: %s" % msg)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", help="Force Apache restart (don't do page checks)", action="store_true")
    args = parser.parse_args()

    logger.info("Program started")
    if args.force:
        logger.info("--force passed. Forcing restart (no page sanity checks).")
        initiate_restart()
    else:
        main()
