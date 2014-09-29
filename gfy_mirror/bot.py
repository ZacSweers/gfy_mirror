#!/usr/bin/env python
import atexit
import getopt
import json
import logging
import os
import pickle
import sys
import time
import datetime
import urlparse
import praw
import praw.helpers
import signal
import psycopg2
from utils import log, Color, retrieve_vine_video_url, gfycat_convert, get_id, mediacrush_convert, get_gfycat_info, \
    fitbamob_convert, imgur_upload, get_fitbamob_info, notify_mac, retrieve_vine_cdn_url

__author__ = 'Henri Sweers'

# DB for caching previous posts
cache_file = "gfy_mirror_DB"

# File with login credentials
propsFile = "login.json"

# for keeping track of if we're on Heroku
running_on_heroku = False

# Dry runs
dry_run = False

# Notify on mac
notify = False

# Bot name
bot_name = "gfy_mirror"

# Already processed posts
already_done = set()

allowedDomains = [
        "gfycat.com",
        "vine.co",
        "giant.gfycat.com",
        "mediacru.sh",
        "fitbamob.com",
        "i.imgur.com",
        "v.cdn.vine.co"]

allowed_extensions = [".gif", ".mp4"]
disabled_extensions = [".jpg", ".jpeg", ".png"]

# Comment strings
comment_intro = """
Mirrored links
------
"""

comment_info = """\n\n------
[^Source ^Code](https://github.com/hzsweers/gfy_mirror) ^|
[^Feedback/Bugs?](http://www.reddit.com/message/compose?to=pandanomic&subject=gfymirror) ^|
^By ^/[u/pandanomic](http://reddit.com/u/pandanomic)

^Please ^don't ^run ^this ^bot ^under ^your ^own ^account. ^Ask ^to ^have ^your ^sub ^added ^instead.
"""

vine_warning = "*NOTE: The original url was a Vine, which has audio. Gfycat removes audio, but the others should be fine*\n\n"


class MirroredObject():
    op_id = None
    original_url = None
    gfycat_url = None
    mediacrush_url = None
    fitbamob_url = None
    imgur_url = None

    def __init__(self, op_id, original_url, json_data=None):
        if json_data:
            self.__dict__ = json.loads(json_data)
        else:
            self.op_id = op_id
            self.original_url = original_url

    def comment_string(self):
        s = "\n"
        if self.original_url:
            if "vine.co" in self.original_url:
                s += vine_warning
            s += "* [Original](%s)" % self.original_url
        if self.gfycat_url:
            gfy_id = get_id(self.gfycat_url)
            urls = self.gfycat_urls(gfy_id)
            s += "\n\n"
            s += "* [Gfycat](%s) | [mp4](%s) - [webm](%s) - [gif](%s)" % (
                self.gfycat_url, urls[0], urls[1], urls[2])
        if self.mediacrush_url:
            s += "\n\n"
            mc_id = get_id(self.mediacrush_url)
            s += "* [Mediacrush](%s) | " % self.mediacrush_url
            s += "[mp4](%s)" % self.mc_url("mp4", mc_id)
            s += " - [webm](%s)" % self.mc_url("webm", mc_id)
            if "gfycat" not in self.original_url:
                s += " - [gif](%s)" % self.mc_url("gif", mc_id)
            s += " - [ogg](%s)" % self.mc_url("ogv", mc_id)
        if self.fitbamob_url:
            s += "\n\n"
            s += "* [Fitbamob](%s)" % self.fitbamob_url
            # TODO Re-enable this when possible
            # fit_id = get_id(self.fitbamob_url)
            # urls = self.fitbamob_urls(fit_id)
            # s += "* [Fitbamob](%s) | [mp4](%s) - [webm](%s) - [gif](%s)" % (
            #     self.fitbamob_url, urls[0], urls[1], urls[2])
        if self.imgur_url:
            s += "\n\n"
            s += "* [Imgur](%s) (gif only)" % self.imgur_url
        s += "\n"
        return s

    def to_json(self):
        return json.dumps(self.__dict__)

    def gfycat_urls(self, gfy_id):
        info = get_gfycat_info(gfy_id)
        return info['mp4Url'], info['webmUrl'], info['gifUrl']

    def fitbamob_urls(self, fit_id):
        info = get_fitbamob_info(fit_id)['source']
        return info['mp4_url'], info['webm_url'], info['gif_url']

    def mc_url(self, media_type, mc_id):
        return "https://cdn.mediacru.sh/%s.%s" % (mc_id, media_type)


# Called when exiting the program
def exit_handler():
    log("SHUTTING DOWN", Color.BOLD)
    store_cache(cache_file, already_done)


# Called on SIGINT
# noinspection PyUnusedLocal
def signal_handler(input_signal, frame):
    log('\nCaught SIGINT, exiting gracefully', Color.RED)
    sys.exit()


# Function to exit the bot
def exit_bot():
    sys.exit()


def load_caches():
    # Set with previously linked posts
    # Check the db cache first
    log("Loading cache", Color.BOLD)
    global already_done
    if running_on_heroku:
        already_done = mc.get(cache_file)
    else:
        if os.path.isfile(cache_file):
            with open(cache_file, 'r+') as db_file_load:
                already_done = pickle.load(db_file_load)

    if not already_done:
        already_done = set()
    log('--Cache size: ' + str(len(already_done)))


# Check cache for string
def check_key_exists(cache, key):
    return key in cache


# Cache a submission
def cache_submission(submission):
    cache_key(already_done, str(submission.id))
    cache_key(already_done, str(submission.url))


# Cache a key (original url, gfy url, or submission id)
def cache_key(cache, key, data=None):

    if dry_run:
        return

    if data:
        cache[key] = data
    elif key not in cache:
        if isinstance(cache, set):
            cache.add(key)
        elif isinstance(cache, list):
            cache.append(key)

        log('--Cached ' + str(key), Color.GREEN)


# Store cache
def store_cache(cache_name, data):
    if running_on_heroku:
        mc.set(cache_name, data)
    else:
        with open(cache_file, 'w+') as db_file_save:
            pickle.dump(already_done, db_file_save)


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
def extension(url_to_split):
    return os.path.splitext(url_to_split)[1]


# Checks if we've already commented there
def previously_commented(submission):
    flat_comments = praw.helpers.flatten_tree(submission.comments)
    for comment in flat_comments:
        try:
            if comment.author.name == bot_name:
                log("----Previously commented, caching", Color.RED)
                cache_key(already_done, submission.id)
                return True
        except:
            return False

    return False


# Validates if a submission should be posted
def submission_is_valid(submission):
    # check domain/extension validity, caches, and if previously commented
    ext = extension(submission.url)
    if (submission.domain in allowedDomains and ext not in disabled_extensions) or ext in allowed_extensions:
        # Check for submission id and url
        if check_key_exists(already_done, submission.id) or check_key_exists(already_done, submission.url):
            return False
        elif previously_commented(submission):
            return False
        else:
            return True
    return False


# Process a gif post
def process_submission(submission):
    new_mirror = MirroredObject(submission.id, submission.url)

    already_gfycat = False
    already_imgur = False

    url_to_process = submission.url

    if submission.domain == "vine.co":
        url_to_process = retrieve_vine_video_url(url_to_process)
    elif submission.domain == "v.cdn.vine.co":
        url_to_process = retrieve_vine_cdn_url(url_to_process)
    elif submission.domain == "gfycat.com":
        already_gfycat = True
        new_mirror.gfycat_url = url_to_process
        url_to_process = get_gfycat_info(get_id(url_to_process))['mp4Url']
    elif submission.domain == "mediacru.sh":
        new_mirror.mediacrush_url = url_to_process
        url_to_process = "https://cdn.mediacru.sh/%s.mp4" % get_id(url_to_process)
    elif submission.domain == "fitbamob.com":
        new_mirror.fitbamob_url = url_to_process
        url_to_process = get_fitbamob_info(get_id(url_to_process))['mp4_url']

    if submission.domain == "giant.gfycat.com":
        # Just get the gfycat url
        url_to_process = url_to_process.replace("giant.", "")
        new_mirror.gfycat_url = url_to_process
        already_gfycat = True

    if submission.domain == "imgur.com" and extension(url_to_process) == ".gif":
        new_mirror.imgur_url = url_to_process
        already_imgur = True

    # Get converting
    log("--Beginning conversion, url to convert is " + url_to_process)
    if not already_gfycat:
        gfy_url = gfycat_convert(url_to_process)
        if gfy_url:
            new_mirror.gfycat_url = gfy_url
            log("--Gfy url is " + new_mirror.gfycat_url)
        else:
            cache_submission(submission)
            return

    if submission.domain != "mediacru.sh":
        # TODO check file size limit (50 mb)
        new_mirror.mediacrush_url = mediacrush_convert(url_to_process)
        log("--MC url is " + new_mirror.mediacrush_url)

    if submission.domain != "fitbamob.com":
        fitba_url = fitbamob_convert(submission.title, url_to_process)
        if fitba_url:
            new_mirror.fitbamob_url = fitba_url
            log("--Fitbamob url is " + new_mirror.fitbamob_url)

    # TODO Re-enable this once "animated = false" issue resolved
    # if not already_imgur:
    # # TODO need to check 10mb file size limit
    #     new_mirror.imgur_url = imgur_upload(submission.title, url_to_process)
    #     log("--Imgur url is " + new_mirror.imgur_url)

    comment_string = comment_intro + new_mirror.comment_string() + comment_info
    add_comment(submission, comment_string)
    cache_submission(submission)
    if not already_gfycat:
        # Take some time to avoid rate limiting. Annoying but necessary
        log('-Waiting 60 seconds', Color.CYAN)
        time.sleep(60)


# Add the comment with info
def add_comment(submission, comment_string):
    log("--Adding comment", Color.BLUE)

    if dry_run:
        log("--Dry run, comment below", Color.BLUE)
        log(comment_string, Color.GREEN)
        return

    try:
        submission.add_comment(comment_string)
    except praw.errors.RateLimitExceeded:
        log("--Rate Limit Exceeded", Color.RED)
    except praw.errors.APIException:
        log('--API exception', Color.RED)
        logging.exception("Error on followupComment")


# Main bot runner
def bot():
    log("Parsing new 30", Color.BLUE)
    new_count = 0
    for submission in soccer_subreddit.get_new(limit=30):
        if submission_is_valid(submission):
            new_count += 1
            log("New Post - " + submission.url, Color.GREEN)
            process_submission(submission)
            if dry_run:
                sys.exit("Done")
        else:
            cache_key(already_done, submission.id)

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

        # TODO Eventually we'll want to DB this instead
        # urlparse.uses_netloc.append("postgres")
        # url = urlparse.urlparse(os.environ["DATABASE_URL"])
        #
        # conn = psycopg2.connect(
        # database=url.path[1:],
        # user=url.username,
        # password=url.password,
        # host=url.hostname,
        # port=url.port
        # )

    if len(opts) != 0:
        for o, a in opts:
            if o in ("-d", "--dry"):
                dry_run = True
            elif o in ("-n", "--notify"):
                notify = True
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
    log("CURRENT PST TIMESTAMP: " + datetime.datetime.fromtimestamp(
        time.time() - 28800).strftime('%Y-%m-%d %H:%M:%S'), Color.BOLD)

    args = sys.argv
    loginType = "propFile"

    r = praw.Reddit(user_agent='/u/gfy_mirror by /u/pandanomic')

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

    load_caches()
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
            if notify:
                notify_mac("Looped")
            time.sleep(60)
