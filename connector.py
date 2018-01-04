import base64
import hashlib
import json
import os
import re
import sys
from pprint import pprint

import requests

import slumber

cyklistesobe_api = slumber.API("http://www.cyklistesobe.cz/api/")
session = requests.session()
session.headers.update(
    {"Authorization": "Bearer %s" % os.environ.get('AUTH_TOKEN')},
)
zmenteto_api = slumber.API("https://zmente.to/api/v3", session=session)
debug = False


def get_threads(last_id=None):
    return cyklistesobe_api.threads.get(
        page=1,
        per_page=4,
        external_service="zmenteto",
        order="created_at",
        order_direction="asc",
        after_id=last_id,
    )


def get_messages(thread):
    return cyklistesobe_api.messages.get(
        thread_id=thread["id"],
        page=1,
        per_page=1,
        order="created_at",
        order_direction="asc",
    )


def translate_date(date):
    return re.sub(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}).(\d{6})Z$", r"\1-\2-\3 \4:\5:\6", date)


def get_issue(thread):
    return cyklistesobe_api.issues.get(
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
        photo_url = "http://www.cyklistesobe.cz%s" % photo_url
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


def get_zmenteto_issue_json(
        message, issue, thread, photo_count, files, latlon,
):
    return {
        "formId": 6,
        "subcategoryId": 18,
        "countPhotos": photo_count,
        "values": {
            "name": thread["title"],
            "email": get_email(thread["public_token"]),
            "latlon": latlon,
            "description": get_description(message, issue, thread),
            "full_name": thread["created_by_name"] or "Uživatel si nepřeje zveřejnit jméno",
            "date": translate_date(thread["created_at"]),
        },
        "files": files,
    }


def get_photo_json(photo_string, photo_md5):
    return {
            "name": "TEST",
            "data": photo_string.decode("UTF-8"),
            "md5": photo_md5.hexdigest(),
            "order": 0,
            # "size": 6,
            # "mimeType": "",
    }


def send_thread(thread, id_file):
    if debug:
        print("----------------THREAD-----------------")
        pprint(thread)
    issue = get_issue(thread)
    if debug:
        print()
        print("----------------ISSUE-----------------")
        pprint(issue)
    message = get_messages(thread)[0]

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
        try:
            response = getattr(zmenteto_api.forms, "post-files").post(photo_json)
            print(response)
            photo_count = 1
            files = [response["fileId"]]
        except (slumber.exceptions.HttpClientError, slumber.exceptions.HttpServerError) as e:
            print(e.response.status_code)
            print(e.content)
            raise

    zmenteto_issue_json = get_zmenteto_issue_json(
        message, issue, thread, photo_count, files, latlon,
    )

    print()
    print("---------------ZMĚŇTE.TO---------------")
    print(json.dumps(zmenteto_issue_json, indent=4))
    try:
        response = zmenteto_api.forms.save.post(zmenteto_issue_json)
        print(response)
        id_file.write(str(thread["id"]) + "\r\n")
    except (slumber.exceptions.HttpClientError, slumber.exceptions.HttpServerError) as e:
        print(e.response.status_code)
        print(e.content)
        raise
    print()
    print("============================================================")


last_id = None
with open("last_id", 'r+') as f:
    for cur_id in f:
        last_id = cur_id.strip()

threads = get_threads(last_id=last_id)

if threads == []:
    sys.exit()

with open("last_id", 'w+') as id_file:
    for thread in threads:
        send_thread(thread, id_file)
