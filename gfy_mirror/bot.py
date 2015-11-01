#!/usr/bin/env python
import atexit
import getopt
import json
import logging
import os
import sys
import time
import datetime
import praw
import praw.helpers
import signal
from utils import log, Color, retrieve_vine_video_url, gfycat_convert, get_id, imgrush_convert, get_gfycat_info, \
    offsided_convert, imgur_upload, get_offsided_info, notify_mac, retrieve_vine_cdn_url, get_streamable_info, \
    streamable_convert

__author__ = 'Henri Sweers'

# DB for caching previous posts
cache_file = "gfy_mirror_DB"

# File with login credentials
propsFile = "credentials.json"

# for keeping track of if we're on Heroku
running_on_heroku = False

# Dry runs
dry_run = False

# Notify on mac
notify = False

# Bot name
bot_name = "gfy_mirror"

allowedDomains = [
    "gfycat.com",
    "vine.co",
    "giant.gfycat.com",
    "zippy.gfycat.com",
    "fat.gfycat.com",
    "imgrush.com",
    "offsided.com",
    "i.imgur.com",
    "v.cdn.vine.co",
    "giffer.co",
    "streamable.com"
]

allowed_extensions = [".gif", ".mp4"]
disabled_extensions = [".jpg", ".jpeg", ".png"]

approved_subs = ['soccer', 'reddevils', 'LiverpoolFC', 'swanseacity', 'OmarTilDeath']

# Comment strings
comment_intro = """
Mirrored links
------
"""

comment_info = """\n\n------

[^Source ^Code](https://github.com/hzsweers/gfy_mirror) ^|
[^Feedback/Bugs?](http://www.reddit.com/message/compose?to=pandanomic&subject=gfymirror) ^|
^By ^/[u/pandanomic](http://reddit.com/u/pandanomic)
"""

vine_warning = """*NOTE: The original url was a Vine, which has audio.
Gfycat removes audio, but the others should be fine*\n\n"""


class MirroredObject:
    op_id = ""
    original_url = ""
    gfycat_url = ""
    imgrush_url = ""
    offsided_url = ""
    imgur_url = ""
    streamable_url = ""

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
        # Gfycat disabled for now because their random string generation isn't
        # if self.gfycat_url:
        #     gfy_id = get_id(self.gfycat_url)
        #     urls = self.gfycat_urls(gfy_id)
        #     s += "\n\n"
        #     s += "* [Gfycat](%s) | [mp4](%s) - [webm](%s) - [gif](%s)" % (
        #         self.gfycat_url, urls[0], urls[1], urls[2])
        if self.imgrush_url:
            s += "\n\n"
            mc_id = get_id(self.imgrush_url)
            s += "* [Imgrush](%s) | " % self.imgrush_url
            s += "[mp4](%s)" % self.mc_url("mp4", mc_id)
            s += " - [webm](%s)" % self.mc_url("webm", mc_id)
            if "gfycat" not in self.original_url:
                s += " - [gif](%s)" % self.mc_url("gif", mc_id)
            s += " - [ogg](%s)" % self.mc_url("ogv", mc_id)
        if self.offsided_url:
            s += "\n\n"
            s += "* [Offsided](%s)" % self.offsided_url
            # TODO Re-enable this when possible
            # fit_id = get_id(self.offsided_url)
            # urls = self.offsided_urls(fit_id)
            # s += "* [Offsided](%s) | [mp4](%s) - [webm](%s) - [gif](%s)" % (
            # self.offsided_url, urls[0], urls[1], urls[2])
        if self.imgur_url:
            s += "\n\n"
            s += "* [Imgur](%s) (gif only)" % self.imgur_url
        if self.streamable_url:
            s += "\n\n"
            s += "* [Streamable](%s)" % self.streamable_url
            # TODO Implement this from https://streamable.com/documentation when I have a good method for
            # s += "* [Streamable](%s) | " % self.streamable_url
            # for mediaType, url in self.streamable_urls(get_id(self.streamable_url)):
            # s += "[%s](%s) - " % mediaType, url
            # s = s[0::-2]  # Shave off the last "- "
        s += "\n"
        return s

    def to_json(self):
        return json.dumps(self.__dict__)

    @staticmethod
    def gfycat_urls(gfy_id):
        info = get_gfycat_info(gfy_id)
        return info['mp4Url'], info['webmUrl'], info['gifUrl']

    @staticmethod
    def offsided_urls(fit_id):
        info = get_offsided_info(fit_id)['source']
        return info['mp4_url'], info['webm_url'], info['gif_url']

    @staticmethod
    def mc_url(media_type, mc_id):
        return "https://imgrush.com/%s.%s" % (mc_id, media_type)

    @staticmethod
    def streamable_urls(s_id):
        info = get_offsided_info(s_id)
        return [{x: "https:" + info["url_root"] + x} for x in info["formats"]]


# Called when exiting the program
def exit_handler():
    log("SHUTTING DOWN", Color.BOLD)


# Called on SIGINT
# noinspection PyUnusedLocal
def signal_handler(input_signal, frame):
    log('\nCaught SIGINT, exiting gracefully', Color.RED)
    sys.exit()


# Function to exit the bot
def exit_bot():
    sys.exit()


# Login
def retrieve_login_credentials():
    if running_on_heroku:
        login_info = [os.environ['REDDIT_USERNAME'],
                      os.environ['REDDIT_PASSWORD'],
                      os.environ['STREAMABLE_PASSWORD']
                      ]
        return login_info
    else:
        # reading login info from a file, it should be username \n password
        with open("credentials.json", "r") as loginFile:
            login_info = json.loads(loginFile.read())

        login_info[0] = login_info["REDDIT_USERNAME"]
        login_info[1] = login_info["REDDIT_PASSWORD"]
        login_info[2] = login_info["STREAMABLE_PASSWORD"]
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
                log("----Previously commented, skipping")
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
        if previously_commented(submission):
            return False, True
        else:
            return True, False
    return False, False


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
    elif submission.domain == "imgrush.com":
        new_mirror.imgrush_url = url_to_process
        url_to_process = "https://imgrush.com/%s.mp4" % get_id(url_to_process)
    elif submission.domain == "offsided.com":
        new_mirror.offsided_url = url_to_process
        url_to_process = get_offsided_info(get_id(url_to_process))['mp4_url']
    elif submission.domain == "streamable.com":
        new_mirror.streamable_url = url_to_process
        url_to_process = "https:%s.mp4" % get_streamable_info(get_id(url_to_process))["url_root"]

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

    if submission.domain != "imgrush.com":
        # TODO check file size limit (50 mb)
        new_mirror.imgrush_url = imgrush_convert(url_to_process)
        log("--MC url is " + new_mirror.imgrush_url)

    if submission.domain != "offsided.com":
        fitba_url = offsided_convert(submission.title, url_to_process)
        if fitba_url:
            new_mirror.offsided_url = fitba_url
            log("--Offsided url is " + new_mirror.offsided_url)

    if submission.domain != "streamable.com":
        new_mirror.streamable_url = streamable_convert(url_to_process, retrieve_login_credentials()[2])
        log("--Streamable url is " + new_mirror.streamable_url)

    # TODO Re-enable this once "animated = false" issue resolved
    # if not already_imgur:
    # # TODO need to check 10mb file size limit
    # new_mirror.imgur_url = imgur_upload(submission.title, url_to_process)
    #     log("--Imgur url is " + new_mirror.imgur_url)

    comment_string = comment_intro + new_mirror.comment_string() + comment_info
    add_comment(submission, comment_string)
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
    for sub in approved_subs:
        log("Checking for posts in /r/" + sub, Color.BLUE)
        now = datetime.datetime.utcnow()
        now_minus_10 = now + datetime.timedelta(minutes=-10)
        float_now_minus_10 = time.mktime(now_minus_10.timetuple())
        subreddit = r.get_subreddit(sub)
        submissions = [p for p in subreddit.get_new(limit=200) if p.created_utc > float_now_minus_10]
        for submission in sorted(submissions, key=lambda p: p.created_utc):
            is_valid, has_commented = submission_is_valid(submission)
            log("Analyzing " + submission.title)
            if is_valid:
                log("New Post in /r/" + submission.subreddit.display_name + " - " + submission.url, Color.GREEN)
                process_submission(submission)
                if dry_run:
                    sys.exit("Done")
            elif has_commented:
                return
            else:
                continue

        if len(submissions) == 0:
            log("Nothing new", Color.BLUE)


# Main method
if __name__ == "__main__":

    try:
        opts, args = getopt.getopt(sys.argv[1:], "fdn", ["flushvalid", "dry", "notify"])
    except getopt.GetoptError:
        print('bot.py -f -d -n')
        sys.exit(2)

    if os.environ.get('HEROKU', None):
        running_on_heroku = True

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
                response = input("Are you sure? Y/N")
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
        r.login(loginInfo[0], loginInfo[1], disable_warning=True)
        log("--Login successful", Color.GREEN)
    except praw.errors:
        log("LOGIN FAILURE", Color.RED)
        exit_bot()

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
