import json
import random
import string
import urllib
from pyquery import pyquery
import requests
from pycrush import Media

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


# Convert to mediacrush
def mediacrush_convert(url_to_convert):
    log('--Converting to mediacrush')

    # Convert
    media = Media()
    response = media.upload(str(url_to_convert))
    log('----success', Color.GREEN)
    return "https://mediacru.sh/%s" % response.hash


def fitbamob_convert(title, url_to_convert):
    log('--Converting to fitbamob')
    req_data = {
        'url': url_to_convert,
        'title': title
    }
    r = requests.post(
        'http://fitbamob.com/api/v1/upload-url',
        data=json.dumps(req_data),
        headers={
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
    )
    assert r.status_code == 200
    error_text = r.json().get('error')
    if error_text:
        log('----Error uploading gif: ' + error_text, Color.RED)
        print('Error uploading gif: ' + error_text)
        return None
    else:
        upload_id = r.json()['id']
        canonical_url = r.json()['canonical_url']
        log('----Started conversion of gif, video will be available under ' + canonical_url, Color.GREEN)
        log('----success', Color.GREEN)
        return canonical_url


def imgur_upload(title, url_to_process):
    log('--Uploading to imgur')

    headers = {"Authorization": "Client-ID c4f5de959205bb4",
               'Content-type': 'application/json',
               'Accept': 'application/json'}

    req_data = {
        'image': url_to_process,
        'title': title,
        'type': 'URL'
    }

    r = requests.post(
        'https://api.imgur.com/3/upload',
        data=json.dumps(req_data),
        headers=headers
    )

    assert r.status_code == 200
    jdata = r.json()
    if jdata['success']:
        link = jdata['data']['link']
        print 'link is ' + link
        return link
    else:
        print "error"


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


# Gets the id of a video assuming it's of the "website.com/<id>" type
def get_id(url_to_get):
    if url_to_get[-1] == '/':
        url_to_get = url_to_get[:-1]
    return url_to_get.split('/')[-1]


# Get gfycat info
def get_gfycat_info(gfy_id):
    response = requests.get("http://www.gfycat.com/cajax/get/%s" % gfy_id)
    jdata = json.loads(response.content)
    return jdata['gfyItem']
