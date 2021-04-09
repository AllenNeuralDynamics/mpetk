import mpeconfig
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
        raise exceptions.LIMSUnavailableError(
            "GET request to {} failed with status {}.".format(_request, response.status_code)
        )
    return json.loads(response.text)


def request_from_file(path, *args):
    try:
        filename = f"{path}\\{args[0]}\\{args[1]}.json"
    except:
        filename = f"{path}\\{args[0]}.json"
    if os.path.exists(filename):
        logging.info(f'loading data file: {filename}')
        return json.load(open(filename, 'r'))
    else:
        raise FileNotFoundError(f'Could not find test data file: {filename}')


def post(url, data, *args, timeout=None):
    if args:
        _request = url.format(*args).replace(";", "%3B")
    else:
        _request = url
    try:
        t1 = datetime.datetime.now()
        response = requests.post(_request, json=data, timeout=timeout)
        t_delta = datetime.datetime.now() - t1
    except exceptions.LIMSUnavailableError:
        raise exceptions.LIMSUnavailableError(f"Post request to {_request} failed with no response.")
    logging.lims(f'LIMS POST: {_request}, status code: {response.status_code}, {t_delta.total_seconds():.2f} seconds',
                 extra={'weblog': True})
    logging.info(f'POST data: {pformat(json.dumps(data))}')

    if response.status_code != 200:
        raise exceptions.LIMSUnavailableError(f"Post request to {_request} failed with status {response.status_code}.")


def post_to_file(filepath, data, *args):
    timestamp = datetime.datetime.now().timestamp()
    os.makedirs(filepath, mode=777, exist_ok=True)
    filename = f'{timestamp}.json'
    logging.info(f'Writing post file to {filepath}/{filename}')
    json.dump(data, open(f'{filepath}/{filename}', 'w'))
    if args:
        meta_file = f'{timestamp}.meta'
        json.dump(args, open(f'{filepath}/{meta_file}', 'w'))


def query_table(table_name, key, value, timeout=None):
    lims_url = _config["lims_url"]
    return request(f"{lims_url}/{table_name}.json/?{key}={value}", timeout=timeout)


lims_data_path = os.getenv('LIMSTK_DATA_PATH')
if lims_data_path:
    lims_data_path = lims_data_path.strip()
    logging.lims(f'USING LIMSTK_DATA_PATH: {lims_data_path}')
for name, url in _config["apis"].items():
    if not lims_data_path:
        setattr(_module, name, partial(request, url))
    else:
        path = f'{lims_data_path}/{name}'
        setattr(_module, name, partial(request_from_file, path))

for name, url in _config['post_apis'].items():
    if not lims_data_path:
        setattr(_module, f'post_{name}', partial(post, url))
    else:
        path = f'{lims_data_path}\\posts\\{name}'
        setattr(_module, f'post_{name}', partial(post_to_file, path))


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
    if lims_data_path:
        path = lims_data_path
        mouse_details = request_from_file(path, 'donor_info_with_parent', mouse_id)
        if mouse_details[0]['water_restricted']:
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
