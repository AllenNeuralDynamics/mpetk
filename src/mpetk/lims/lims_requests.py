from .. import mpeconfig
from functools import partial
import json
import requests
from . import exceptions
import os
import logging
import datetime
from pprint import pprint, pformat

_module = __import__(__name__)

_config = mpeconfig.source_configuration("limstk", fetch_logging_config=False, send_start_log=False)

training_mode = False

def lims_logging_spoof(log_message, extra=None):
    if extra:
        logging.info(log_message, extra=extra)
    else:
        logging.info(log_message)

if not hasattr(logging, 'lims'):
    setattr(logging, 'lims', lims_logging_spoof)

def raise_bad_response(post_type, response, request, status_code):
    print("in bad response")
    err = exceptions.LIMSBadResponse(
            "{} request to {} failed with status {}.".format(post_type, request, status_code)
        )
    err.status_code = status_code
    err.response = response
    raise err

def request(url, *args, timeout=None):
    try:
        _request = url.format(*args).replace(";", "%3B")
    except IndexError:
        raise exceptions.LIMSURLFormatError(f"Error formatting URL: {url} and args: {args}")
    t1 = datetime.datetime.now()
    response = requests.get(_request, timeout=timeout)
    t_delta = datetime.datetime.now() - t1
    logging.lims(f'LIMS GET: {_request}, status code: {response.status_code}, {t_delta.total_seconds():.2f} seconds')
    if response.status_code != 200:
        raise_bad_response("GET", response, _request, response.status_code)

    return json.loads(response.text)

def post(url, data, *args, timeout=None):
    if args:
        _request = url.format(*args).replace(";", "%3B")
    else:
        _request = url
    try:
        t1 = datetime.datetime.now()
        response = requests.post(_request, json=data, timeout=timeout)
        t_delta = datetime.datetime.now() - t1
    except requests.exceptions.ConnectionError:
        logging.warning(f"Post request to {_request} failed with no response.")
        raise exceptions.LIMSUnavailableError(f"Post request to {_request} failed with no response.")
    logging.lims(f'LIMS POST: {_request}, status code: {response.status_code}, {t_delta.total_seconds():.2f} seconds',
                 extra={'weblog': True})
    logging.info(f'POST data: {pformat(json.dumps(data))}')

    if response.status_code != 200:
        raise_bad_response("POST", response, _request, response.status_code)

    return response.status_code

def query_table(table_name, key, value, timeout=None):
    lims_url = _config["lims_url"]
    return request(f"{lims_url}/{table_name}.json/?{key}={value}", timeout=timeout)

def begin_training_mode():
    training_mode = True
    for name, url in _config["apis"].items():
        delattr(_module, name)
    for name, url in _config['post_apis'].items():
        delattr(_module, f'post_{name}')
    
    for name, url in _config["training_apis"].items():
        setattr(_module, name, partial(request,url))
    for name, url in _config["training_apis"].items():
        setattr(_module, f'post_{name}', partial(request,url))

if hasattr(_module, "training_mode"):
    for name, url in _config["training_apis"].items():
        setattr(_module, name, partial(request,url))
for name, url in _config["apis"].items():
    setattr(_module, name, partial(request, url))

for name, url in _config['post_apis'].items():
    setattr(_module, f'post_{name}', partial(post, url))


def mouse_is_active(mouse_id, timeout=None):
    session = requests.session()
    t1 = datetime.datetime.now()
    response = session.get(f'{_config["mtrain_url"]}/get_script/', data=json.dumps({'LabTracks_ID': mouse_id}),
                           timeout=timeout)
    t_delta = datetime.datetime.now() - t1
    logging.lims(
        f'MTRAIN Request: {_config["mtrain_url"]}/get_script/{mouse_id}, '
        f'status code: {response.status_code}, {t_delta.total_seconds():.2f} seconds')
    if response.status_code == 200:
        return True
    return False

    # LIMS API will return True/ False/ Null.  Null should return False


setattr(_module, 'mouse_is_active', mouse_is_active)


def mouse_is_restricted(mouse_id):
    if hasattr(_module, "training_mode"):
        url = _config["training_apis"]["donor_info_with_parent"]
        response = requests.get(url.format(mouse_id))
        if response.json()[0]["water_restricted"]:
            return True
        else:
            return False
    else:
        t1 = datetime.datetime.now()
        url = f'http://lims2/donors/info/details.json?external_donor_name={mouse_id}&parent_specimens=true'
        response = requests.get(url)
        t_delta = datetime.datetime.now() - t1
        details = json.loads(response.content)
        logging.lims(
            f'LIMS GET: http://lims2/donors/info/details.json?external_donor_name={mouse_id}&parent_specimens=true, '
            f'status code: {response.status_code}, {t_delta.total_seconds():.2f} seconds')
        if details[0]['water_restricted']:
            return True
        else:
            return False

        # LIMS API will return True/ False/ Null.  Null should return False


setattr(_module, 'mouse_is_restricted', mouse_is_restricted)
