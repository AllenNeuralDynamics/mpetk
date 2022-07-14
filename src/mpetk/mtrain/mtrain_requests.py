from mpetk import mpeconfig
import importlib
from functools import partial
import json
import requests
from . import exceptions
import logging
import datetime
from pprint import pformat

_module = importlib.import_module(__name__)
_module = importlib.import_module(_module.__package__)

_config = mpeconfig.source_configuration("mtraintk", fetch_logging_config=False, send_start_log=False)


def mtrain_logging_spoof(log_message, extra=None):
    if extra:
        logging.info(log_message, extra=extra)
    else:
        logging.info(log_message)


if not hasattr(logging, 'mtrain'):
    setattr(logging, 'mtrain', mtrain_logging_spoof)


def raise_bad_response(post_type, response, url, status_code):
    err = exceptions.MTrainBadResponse(f"{post_type} request to {url} failed with status {status_code}.")
    err.status_code = status_code
    err.response = response
    raise err


def endpoint_request(mtrain_url, timeout=None):
    t1 = datetime.datetime.now()
    response = requests.get(mtrain_url, timeout=timeout)
    t_delta = datetime.datetime.now() - t1
    logging.mtrain(f'MTRAIN_GET, {mtrain_url}, status_code, {response.status_code}, response_time_s, {t_delta.total_seconds():.2f}')
    if response.status_code != 200:
        raise_bad_response("GET", response, mtrain_url, response.status_code)
    return json.loads(response.text)


def view_get_request(mtrain_url, data, timeout=None):
    t1 = datetime.datetime.now()
    response = requests.get(mtrain_url, timeout=timeout, data=json.dumps(data))
    t_delta = datetime.datetime.now() - t1
    logging.mtrain(f'MTRAIN_GET, {mtrain_url}, status_code, {response.status_code}, response_time_s, {t_delta.total_seconds():.2f}, args, {data}')
    if response.status_code != 200:
        raise_bad_response("GET", response, mtrain_url, response.status_code)
    return json.loads(response.text)


def view_post_request(mtrain_url, data,  timeout=None):
    try:
        t1 = datetime.datetime.now()
        response = requests.post(mtrain_url, json=data, timeout=timeout)
        t_delta = datetime.datetime.now() - t1
    except requests.exceptions.ConnectionError:
        logging.warning(f"Post request to {mtrain_url} failed with no response.")
        raise exceptions.MTrainUnavailableError(f"Post request to {mtrain_url} failed with no response.")
    logging.mtrain(f'MTRAIN_GET, {mtrain_url}, status_code, {response.status_code}, response_time_s, {t_delta.total_seconds():.2f}, {data}',
                 extra={'weblog': True})
    logging.info(f'POST data: {pformat(json.dumps(data))}')

    if response.status_code != 200:
        raise_bad_response("POST", response, mtrain_url, response.status_code)

    return response.status_code


for name, url in _config["endpoints"].items():
    setattr(_module, name, partial(endpoint_request, url))
for name, url in _config['get_views'].items():
    setattr(_module, name, partial(view_get_request, url))
for name, url in _config['post_views'].items():
    setattr(_module, name, partial(view_post_request, url))


