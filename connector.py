import base64
import hashlib
import json
import sys
from pprint import pprint

import requests

import slumber

api = slumber.API("http://www.cyklistesobe.cz:8000/api/")
debug = False


def get_threads(last_id=None):
    return api.threads.get(
        page=1,
        per_page=4,
        submit_external="zmenteto",
        order_by="created_at",
        order="desc",
        after_id=last_id,
    )


def get_messages():
    return api.messages.get(
        thread_id=thread["id"],
        page=1,
        per_page=1,
        submit_external="zmenteto",
        order_by="created_at",
        order="desc",
    )


def get_issue():
    return api.issues.get(
        id=thread["issue_id"],
    )


def parse_geom(issue):
    if 'geometries' in issue['features'][0]['geometry']:
        geometry = issue['features'][0]['geometry']['geometries'][0]
    else:
        geometry = issue['features'][0]['geometry']

    if geometry['type'] == "Point":
        coordinates = geometry['coordinates']
    elif geometry['type'] == "Polygon":
        coordinates = geometry['coordinates'][0][0]
    else:
        coordinates = geometry['coordinates'][0]

    return "%s, %s" % tuple(reversed(coordinates))


def parse_photo(issue):
    photo_url = issue["features"][0]["properties"]["photo_thumb_url"]
    photo_string = None
    if photo_url:
        photo_url = "http://www.cyklistesobe.cz:8000%s" % photo_url
        response = requests.get(photo_url)
        if response.status_code == 200:
            photo_string = base64.b64encode(response.content)
            photo_md5 = hashlib.md5(response.content)
            return photo_string, photo_md5
    return None, None


def get_email(token):
    return "thread-%s@cyklistesobe.cz" % token


def get_description(message, issue, thread):
    return "%s\r\n\r\nZasláno na základě podnětu %s" % (
        message["body"],
        issue["features"][0]["properties"]["cyclescape_url"],
    )


def get_zmenteto_issue_json(message, issue, thread, photo_count, files, latlon):
    return {
        "formId": 1,
        "subcategoryId": 1,
        "countPhotos": photo_count,
        "values": {
            "name": thread["title"],
            "email": get_email(thread["public_token"]),
            "latlon": latlon,
            "description": get_description(message, issue, thread),
            "full_name": thread["created_by_name"],
            "date": thread["created_at"],
        },
        "files": files,
    }


def get_photo_json(photo_string, photo_md5):
    return {
            "name": "Photo",
            "data": photo_string.decode("UTF-8"),
            "md5": photo_md5.hexdigest(),
            "order": 1,
            # "size": 6,
            # "mimeType": "",
    }


threads = get_threads()

with open("last_id", 'r+') as f:
    try:
        last_id = f.read()
    except Exception:
        last_id = None

threads = get_threads(last_id=last_id)

if threads == []:
    sys.exit()

with open("last_id", 'w+') as f:
    f.seek(0)
    f.write(str(threads[0]["id"]))
    f.truncate()

for thread in threads:
    if debug:
        print("----------------THREAD-----------------")
        pprint(thread)
    issue = get_issue()
    if debug:
        print()
        print("----------------ISSUE-----------------")
        pprint(issue)
    message = get_messages()[0]

    if debug:
        print()
        print("----------------MESSAGE----------------")
        pprint(message)

    latlon = parse_geom(issue)
    photo_string, photo_md5 = parse_photo(issue)

    photo_count = 0
    files = []
    if photo_string:
        photo_json = get_photo_json(photo_string, photo_md5)
        print(json.dumps(photo_json, indent=4))
        photo_count = 1
        files = [1]

    zmenteto_issue_json = get_zmenteto_issue_json(message, issue, thread, photo_count, files, latlon)

    print()
    print("---------------ZMĚŇTE.TO---------------")
    print(json.dumps(zmenteto_issue_json, indent=4))
    print()
    print("============================================================")
