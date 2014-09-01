#!/usr/bin/env python
import atexit
import getopt
import json
import os
import pickle
import sys
import time
import datetime
import urlparse
import praw
import signal
import psycopg2
from utils import log, Color

__author__ = 'Henri Sweers'

# DB for caching previous posts
cache_file = "gfy_mirror_DB"

# File with login credentials
propsFile = "login.json"

# for keeping track of if we're on Heroku
running_on_heroku = False

# Dry runs
dry_run = False


class MirroredObject:
    def __init__(self, op_id, original_url, json_data=None):
        if json_data:
            self.__dict__ = json.loads(json_data)
        else:
            self.op_id = op_id
            self.original_url = original_url
            self.gfycat_url = ""
            self.mediacrush_url = ""
            self.fitbamob_url = ""

    def to_json(self):
        return json.dumps(self.__dict__)


# Called when exiting the program
def exit_handler():
    log("SHUTTING DOWN", Color.BOLD)
    if not running_on_heroku:
        with open(cache_file, 'w+') as db_file_save:
            pickle.dump(already_done, db_file_save)


# Called on SIGINT
# noinspection PyUnusedLocal
def signal_handler(input_signal, frame):
    log('\nCaught SIGINT, exiting gracefully', Color.RED)
    sys.exit()


# Function to exit the bot
def exit_bot():
    sys.exit()


# Check cache for string
def check_cache(input_key):
    if running_on_heroku:
        obj = mc.get(str(input_key))
        if not obj or obj != "True":
            return False
        else:
            return True
    else:
        if input_key in already_done:
            return True
    return False


# Cache a key (original url, gfy url, or submission id)
def cache_key(input_key):
    if running_on_heroku:
        mc.set(str(input_key), "True")
        assert str(mc.get(str(input_key))) == "True"
    else:
        already_done.append(input_key)

    log('--Cached ' + str(input_key), Color.GREEN)


# Remove an item from caching
def cache_remove_key(input_submission):
    log("--Removing from cache", Color.RED)
    if running_on_heroku:
        mc.delete(str(input_submission.id))
        mc.delete(str(input_submission.url))
    else:
        already_done.remove(input_submission.id)
        already_done.remove(input_submission.url)

    log('--Deleted ' + str(input_submission.id), Color.RED)


# Login
def retrieve_login_credentials():
    if running_on_heroku:
        login_info = [os.environ['REDDIT_USERNAME'],
                      os.environ['REDDIT_PASSWORD']]
        return login_info
    else:
        # reading login info from a file, it should be username \n password
        with open("login.json", "r") as loginFile:
            login_info = json.loads(loginFile.read())

        login_info[0] = login_info["user"]
        login_info[1] = login_info["pwd"]
        return login_info


# Retrieves the extension
def extension(url):
    return os.path.splitext(url)[1]


# Validates if a submission should be posted
def submission_is_valid(submission):
    # check domain and extension validity
    if submission.domain in allowedDomains \
            or extension(submission.url) in allowedExtensions:
        # Check for submission id and url
        return not (check_cache(submission.id) or check_cache(submission.url))
    return False


# Process a gif post
def process_submission(submission):



# Main bot runner
def bot():
    log("Parsing new 30", Color.BLUE)
    new_count = 0
    for submission in soccer_subreddit.get_new(limit=30):
        if submission_is_valid(submission):
            new_count += 1
            log("New Post", Color.GREEN)
            process_submission(submission)
        else:
            pass
            # cache_key(submission.id)

    if new_count == 0:
        log("Nothing new", Color.BLUE)

# Main method
if __name__ == "__main__":

    try:
        opts, args = getopt.getopt(sys.argv[1:], "fdn", ["flushvalid", "dry", "notify"])
    except getopt.GetoptError:
        print 'check_and_delete.py -f -d -n'
        sys.exit(2)

    if os.environ.get('MEMCACHEDCLOUD_SERVERS', None):
        import bmemcached

        log('Running on heroku, using memcached', Color.BOLD)

        running_on_heroku = True
        mc = bmemcached.Client(os.environ.get('MEMCACHEDCLOUD_SERVERS').
                               split(','),
                               os.environ.get('MEMCACHEDCLOUD_USERNAME'),
                               os.environ.get('MEMCACHEDCLOUD_PASSWORD'))

        urlparse.uses_netloc.append("postgres")
        url = urlparse.urlparse(os.environ["DATABASE_URL"])

        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )

    if len(opts) != 0:
        for o, a in opts:
            if o in ("-d", "--dry"):
                dry_run = True
            elif o in ("-n", "--notify"):
                dry_run = True
            elif o in ("-f", "--flushvalid"):
                response = raw_input("Are you sure? Y/N")
                if response.lower() == 'y':
                    # TODO
                    pass
                sys.exit()
            else:
                sys.exit('No valid args specified')

    # Register the function that get called on exit
    atexit.register(exit_handler)

    # Register function to call on SIGINT
    signal.signal(signal.SIGINT, signal_handler)

    log("Starting Bot", Color.BOLD)

    log("OS is " + sys.platform, Color.BOLD)

    # For logging purposes
    log("CURRENT CST TIMESTAMP: " + datetime.datetime.fromtimestamp(
        time.time() - 21600).strftime('%Y-%m-%d %H:%M:%S'), Color.BOLD)

    args = sys.argv
    loginType = "propFile"

    r = praw.Reddit('/u/gfy_mirror by /u/pandanomic')

    try:
        log("Retrieving login credentials", Color.BOLD)
        loginInfo = retrieve_login_credentials()
        r.login(loginInfo[0], loginInfo[1])
        log("--Login successful", Color.GREEN)
    except praw.errors:
        log("LOGIN FAILURE", Color.RED)
        exit_bot()

    # read off /r/soccer
    soccer_subreddit = r.get_subreddit('soccer')

    allowedDomains = [
        "gfycat.com",
        "vine.co",
        "giant.gfycat.com",
        "fitbamob.com",
        "imgur.com"]

    allowedExtensions = [".gif"]

    # Array with previously linked posts
    # Check the db cache first
    already_done = []
    if not running_on_heroku:
        log("Loading cache", Color.BOLD)
        with open(cache_file, 'w+') as db_file_load:
            pickle_data = db_file_load.read()
            if not pickle_data == "":
                already_done = pickle.load(db_file_load)

        log('--Cache size: ' + str(len(already_done)))

    counter = 0

    if running_on_heroku:
        log("Heroku run", Color.BOLD)
        bot()
    else:
        log("Looping", Color.BOLD)
        while True:
            bot()
            counter += 1
            log('Looped - ' + str(counter), Color.BOLD)
            time.sleep(60)
