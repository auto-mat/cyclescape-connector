import base64
import hashlib
import json
from pprint import pprint

import requests

import slumber

api = slumber.API("http://www.cyklistesobe.cz:8000/api/")
debug = False


def get_threads():
    return api.threads.get(
        page=1,
        per_page=4,
        submit_external="zmenteto",
        order_by="created_at",
        order="desc",
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


threads = get_threads()

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
        photo_json = {
                "name": "Photo",
                "data": photo_string.decode("UTF-8"),
                "md5": photo_md5.hexdigest(),
                "order": 1,
                # "size": 6,
                # "mimeType": "",
        }
        print(json.dumps(photo_json, indent=4))
        photo_count = 1
        files = [1]

    zmenteto_issue_json = {
        "formId": 1,
        "subcategoryId": 1,
        "countPhotos": photo_count,
        "values": {
            "name": thread["title"],
            "email": "info@cyklistesobe.cz",
            "latlon": latlon,
            "description": message["body"],
            "full_name": thread["created_by_name"],
            "date": thread["created_at"],
        },
        "files": files,
    }

    print()
    print("---------------ZMĚŇTE.TO---------------")
    print(json.dumps(zmenteto_issue_json, indent=4))
    print()
    print("============================================================")