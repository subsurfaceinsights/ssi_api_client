#!/usr/bin/env python3

"""
Subpackage for SSI API client calls and functionality.
"""

import threading
import os
from pprint import pprint
from typing import Optional
import requests
import requests.utils
import json
import websocket


class ApiException(Exception):
    """
    Exception for SSI API Call.
    """

    def __init__(self, request, msg=None):
        super(ApiException, self).__init__(msg)
        self.request = request
        self.status_code = request.status_code
        self.msg = msg

    def __str__(self):
        if self.msg is not None:
            return f"{self.request.status_code}: {self.msg}"
        return repr(self.request)

class JsonWebSocket(websocket.WebSocket):
    """
    WebSocket that sends and receives JSON.
    """
    def __init__(self, ws: websocket.WebSocket):
        self.__dict__.update(ws.__dict__)

    def send_json(self, data):
        """
        Send JSON data.
        """
        return self.send(json.dumps(data))

    def recv_json(self):
        """
        Receive JSON data.
        """
        return json.loads(self.recv())

class ApiClient():
    """
    Class for simplifying SSI API REST Calls.
    """

    def __init__(self,
                 token: Optional[str] =None,
                 url: Optional[str] =None,
                 project=None):

        if not url:
            url = os.getenv("SSI_API_URL")
            if not url:
                raise Exception("No URL specified to ApiClient and no "
                                "SSI_API_URL env variable found")
        if not token:
            token = os.getenv("SSI_API_TOKEN")

        if not project:
            project = os.getenv("SSI_API_PROJECT")
        self.trace = os.environ.get("SSI_API_TRACE")

        self.url = url
        self.token = token
        self.project = project

    def _get_request_headers(self):
        """
        Request headers.
        """

        headers = {}
        if self.project:
            headers.update({
                'X-Paf-Project': self.project,
            })
        if self.token:
            headers.update({
                'X-Paf-Token': self.token,
            })
        return headers

    def check_status_error(self, r, call):
        """
        Check for status errors.
        """
        if r.status_code != 200:
            if r.headers.get('Content-Type', None) == 'application/json':
                msg = r.json()
            else:
                msg = r.text
            msg = msg.strip()
            if r.status_code == 404:
                raise ApiException(
                    request=r,
                    msg=f"Call \"{call}\" was not found." if msg == "Not Found" else msg
                )
            if r.status_code >= 500:
                raise ApiException(
                    request=r,
                    msg=f"Call \"{call}\" failed with server error." if msg == "Internal Server Error" else msg
                )
            else:
                raise ApiException(
                    request=r,
                    msg=msg
                )

    def ws(self, path: str, params: Optional[dict] = None, timeout:
           Optional[int] = None, headers: Optional[dict] = None, **kwargs):
        """
        Perform a SSI API websocket call.
        """
        if params is None:
            params = {}
        if not isinstance(path, str):
            raise TypeError("Path must be a string.")
        if not isinstance(params, dict):
            raise TypeError("Parameters must be a dictionary.")
        querystring = ""
        if params:
            querystring = "?"
            for key, value in params.items():
                key = requests.utils.requote_uri(key)
                value = requests.utils.requote_uri(str(value))
                querystring += f"{key}={value}&"
        headers = self._get_request_headers()
        if headers:
            headers.update(headers)
        url = self.url.replace("https://", "wss://").replace("http://", "ws://")
        full_url = f"{url}/ws/{path}{querystring}"
        if self.trace:
            print(f"WS: {full_url}")
        ws = websocket.create_connection(
            full_url,
            timeout=timeout,
            header=headers,
            **kwargs
        )
        return JsonWebSocket(ws)

    def call(self, call: str, params: Optional[dict] = None, get_params:
             Optional[dict] = None, method: Optional[str] = None, raw_response:
             bool = False, headers: Optional[dict] = None, **kwargs):
        """
        Perform a SSI API call.
        """
        if not method:
            method = 'post'
        if not headers:
            headers = {}
        if self.trace:
            print("")
            print(f"call: {call}")
            if params:
                print(f"params: {params}")
            if get_params:
                print(f"get_params: {get_params}")
            print(f"method: {method}")
        request_method = None
        method = method.lower()
        if method == 'post':
            request_method = requests.post
        elif method == 'get':
            request_method = requests.get
        elif method == 'put':
            request_method = requests.put
        elif method == 'delete':
            request_method = requests.delete
        elif method == 'patch':
            request_method = requests.patch
        elif method == 'head':
            request_method = requests.head
        else:
            raise Exception(f"Unknown method: {method}")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise TypeError("Parameters must be a dictionary.")
        if not isinstance(call, str):
            raise TypeError("Call must be a string.")
        headers.update(self._get_request_headers())
        kwargs.update({
            'url': f"{self.url}/api/{call}",
            'headers': self._get_request_headers(),
        });
        if not params:
            params = {}
        files = kwargs.get('files', None)
        if not files:
            kwargs.update({
                'json': params,
            })
        else:
            kwargs.update({
                'data': params,
            })
        if get_params:
            kwargs.update({
                'params': get_params,
            })
        r = request_method(**kwargs)
        if self.trace:
            print(f"API TRACE: {r.url}")
            print("API PARAMS:")
            pprint(params)
        if raw_response:
            return r
        self.check_status_error(r, call)
        ret = None
        if r.headers.get('Content-Type', None) == 'application/json':
            ret = r.json()
        else:
            ret = r.text
        if self.trace:
            print("API RESPONSE:")
            pprint(ret)
        return ret

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def _async_call_helper(self, call: str, params: dict, files: dict,
                           timeout: int, return_handler: callable,
                           exception_handler: callable):
        """
        Asynchronous call helper.
        """

        try:
            ret = self.call(call, params, files, timeout)
        except Exception as e:  # pylint: disable=broad-except
            if exception_handler:
                exception_handler(e)
            else:
                raise
        if return_handler:
            return_handler(ret)

    def async_call(self, call: str, params: dict = None, files: dict = None,
                   timeout: int = None, return_handler: callable = None,
                   exception_handler: callable = None):
        """
        Perform an asynchronous SSI API call. Note that this uses threading, we
        should support async/await in the future.
        """

        thread = threading.Thread(target=self._async_call_helper, kwargs={
            'call': call,
            'params': params,
            'files': files,
            'timeout': timeout,
            'return_handler': return_handler,
            'exception_handler': exception_handler,
        })
        thread.daemon = True
        thread.start()
        return thread

    def file(self, path, params=None, out_filename=None, print_progress=False,
             timeout=None):
        """
        Perform a SSI API file pulling call.
        """

        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise TypeError("Parameters must be a dictionary.")
        if not isinstance(path, str):
            raise TypeError("Path must be a string.")

        if self.token is not None:
            params['token'] = self.token

        r = requests.get('/'.join([self.url, 'api', path]), params=params,
                          headers=self._get_request_headers(), timeout=timeout,
                          stream=True)
        self.check_status_error(r, path)
        if out_filename is None:
            raise ValueError("out_filename must be specified.")
        with open(out_filename, 'wb') as f:
            if print_progress:
                print(f"Downloading file {out_filename}:")
            downloaded = 0
            for data in r.iter_content(chunk_size=4096):
                downloaded += len(data)
                f.write(data)
                if print_progress:
                    print(f"{downloaded/1024} KB downloaded.")
            if print_progress:
                print("Done downloading.")
