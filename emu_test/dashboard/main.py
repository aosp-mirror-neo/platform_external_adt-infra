import logging
import os

from oauth2client.appengine import oauth2decorator_from_clientsecrets
import webapp2

import bqclient
from gviz_data_table import encode
from gviz_data_table import Table

from google.appengine.api import memcache
from google.appengine.ext.webapp.template import render

from run_query import RunQuery

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
SCOPES = [
    'https://www.googleapis.com/auth/bigquery'
]
decorator = oauth2decorator_from_clientsecrets(
    filename=CLIENT_SECRETS,
    scope=SCOPES,
    cache=memcache)

mem = memcache.Client()

class MainPage(webapp2.RequestHandler):
    @decorator.oauth_required
    def get(self):
        data = {}
        mem.set('natality', data)
        template = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(render(template, data))

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/run_query', RunQuery),
    (decorator.callback_path, decorator.callback_handler())
], debug=True)
