import json
import os
import random
import string
import subprocess
import sys
import time
from urllib import request
from urllib.parse import quote

import requests
from pyquery import pyquery

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


# If you're on mac, install terminal-notifier ("brew install terminal-notifier")
#   to get nifty notifications when it's done
def notify_mac(message):
    if sys.platform == "darwin":
        try:
            subprocess.call(
                ["terminal-notifier", "-message", message, "-title", "FB_Bot",
                 "-sound", "default"])
        except OSError:
            print("If you have terminal-notifier, this would be a notification")


# Log method. If there's a color argument, it'll stick that in first
def log(message, *colorargs):
    if len(colorargs) > 0:
        print(colorargs[0] + message + Color.END)
    else:
        print(message)


# Convert gifs to gfycat
def gfycat_convert(url_to_convert):
    log('--Converting to gfycat')
    encoded_url = quote(url_to_convert, '')

    # Convert
    key = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(8))
    transcode_url = 'http://upload.gfycat.com/transcodeRelease/' + key + '?noMd5=true&fetchUrl=' + encoded_url
    conversion_response = requests.get(transcode_url)
    if conversion_response.status_code == 200:
        j = conversion_response.json()
        if 'error' in j.keys():
            log('----Error: ' + j['error'], Color.RED)
            return None
    else:
        print(conversion_response)
        log('----failed', Color.RED)
        return "Error"

    timeout = 60
    while timeout > 0:
        status_url = 'http://upload.gfycat.com/status/' + key
        status_response = requests.get(status_url)
        j = status_response.json()
        if 'error' in j.keys():
            log('----Error: ' + j['error'], Color.RED)
            return None
        if 'task' in j.keys() and j['task'] == 'complete':
            log('----success', Color.GREEN)
            gfyname = j["gfyname"]
            return "http://gfycat.com/" + gfyname
        timeout -= 1
        time.sleep(1)

    log("----conversion timed out", Color.RED)
    return None


def offsided_convert(title, url_to_convert):
    log('--Converting to offsided')
    req_data = {
        'url': url_to_convert,
        'title': title
    }
    r = requests.post(
        'http://offsided.com/api/v1/upload-url',
        data=json.dumps(req_data),
        headers={
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
    )
    if r.status_code != 200:
        log('----Error uploading gif: Status code ' + str(r.status_code), Color.RED)
        return None
    error_text = r.json().get('error')
    if error_text:
        log('----Error uploading gif: ' + error_text, Color.RED)
        return None
    else:
        upload_id = r.json()['id']
        canonical_url = r.json()['canonical_url']

    timeout = 60
    while timeout > 0:
        r = requests.get(
            'http://offsided.com/api/v1/' + upload_id,
            headers={
                'Accept': 'application/json'
            }
        )
        if r.json()['status'] == 'complete':
            log('----Video is complete at ' + r.json()['canonical_url'], Color.GREEN)
            log('----success', Color.GREEN)
            return canonical_url
        elif r.json()['status'] == 'error':
            log('----Conversion failed.', Color.RED)
            return None
        else:
            timeout -= 1
            time.sleep(1)


def get_offsided_info(f_id):
    req_url = "http://offsided.com/link/%s" % f_id
    r = requests.get(req_url)
    data = r.json()
    return data


def streamable_convert(url_to_convert, streamable_pwd):
    log('--Converting to streamable')
    url = "https://api.streamable.com/import?url=%s&noresize" % url_to_convert
    r = requests.get(url, auth=('gfy_mirror', streamable_pwd))
    upload_id = r.json()["shortcode"]
    return "https://streamable.com/%s" % upload_id


def get_streamable_info(s_id):
    req_url = "https://api.streamable.com/videos/%s" % s_id
    r = requests.get(req_url, auth=('gfy_mirror', 'WinYeaUsEyZ7W4'))
    data = r.json()
    return data


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
        print('link is ' + link)
        return link
    else:
        print("error")


# Returns the .mp4 url of a vine video
def retrieve_vine_video_url(vine_url):
    log('--Retrieving vine url')
    d = pyquery.PyQuery(url=vine_url)
    video_url = d("meta[property=twitter\\:player\\:stream]").attr['content']
    video_url = video_url.partition("?")[0]
    return video_url


def retrieve_vine_cdn_url(cdn_url):
    idx = cdn_url.find('.mp4')
    idx += 4
    s = cdn_url[0:idx]
    return s


# Generate a random 10 letter string
# Borrowed from here: http://stackoverflow.com/a/16962716/3034339
def gen_random_string():
    return ''.join(random.sample(string.ascii_letters * 10, 10))


# Gets the id of a video assuming it's of the "website.com/<id>" type
def get_id(url_to_get):
    if url_to_get[-1] == '/':
        url_to_get = url_to_get[:-1]

    end = url_to_get.split('/')[-1]
    if '.' in end:
        # Truncate the extension if need be
        return os.path.splitext(end)[0]
    else:
        return end


# Get gfycat info
def get_gfycat_info(gfy_id):
    response = requests.get("http://www.gfycat.com/cajax/get/%s" % gfy_id)
    jdata = response.json()
    return jdata['gfyItem']


def get_remote_file_size(url):
    d = request.urlopen(url)
    return d.length
