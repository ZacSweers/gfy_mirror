import random
import string
import urllib
from pyquery import pyquery
import requests

__author__ = 'Henri Sweers'


# Color class, used for colors in terminal
class Color:
    def __init__(self):
        pass

    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


# Log method. If there's a color argument, it'll stick that in first
def log(message, *colorargs):
    if len(colorargs) > 0:
        print colorargs[0] + message + Color.END
    else:
        print message


# Convert gifs to gfycat
def gfycat_convert(url_to_convert):
    log('--Converting to gfycat')
    encoded_url = urllib.quote(url_to_convert, '')

    # Convert
    url_string = 'http://upload.gfycat.com/transcode/' + gen_random_string() + \
                 '?fetchUrl=' + encoded_url
    conversion_response = requests.get(url_string)
    if conversion_response.status_code == 200:
        log('----success', Color.GREEN)
        j = conversion_response.json()
        gfyname = j["gfyname"]
        return "http://gfycat.com/" + gfyname
    else:
        log('----failed', Color.RED)
        return "Error"


# Returns the .mp4 url of a vine video
def retrieve_vine_video_url(vine_url):
    log('--Retrieving vine url')
    d = pyquery.PyQuery(url=vine_url)
    video_url = d("meta[property=twitter\\:player\\:stream]").attr['content']
    video_url = video_url.partition("?")[0]
    return video_url


# Generate a random 10 letter string
# Borrowed from here: http://stackoverflow.com/a/16962716/3034339
def gen_random_string():
    return ''.join(random.sample(string.letters * 10, 10))