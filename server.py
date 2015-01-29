# Dependencies: flask, tornado
from __future__ import absolute_import, division, print_function
# HTTP / HTML
import tornado.wsgi
import tornado.httpserver
import flask
from flask import request, redirect, url_for, make_response  # NOQA
import optparse
import logging
import socket
import simplejson as json
# IBEIS
import ibeis
import utool  # NOQA
import utool as ut
# Web Internal
import serverfuncs, navbar  # NOQA
# Others
from datetime import date
from os.path import join  # NOQA


BROWSER = ut.get_argflag('--browser')
DEFAULT_PORT = 5000
app = flask.Flask(__name__)
global_args = {
    'NAVBAR': navbar.NavbarClass(),
    'YEAR':   date.today().year,
}


################################################################################

@app.route('/')
def index():
    return template(None)


@app.route('/images/submit', methods=['POST'])
def images():
    print("GET: ", request.args)
    print("POST:", request.form)
    return response()


@app.route('/images/form')
def images_form():
    return template('images')


@app.route('/gps/submit', methods=['POST'])
def gps():
    print("GET: ", request.args)
    print("POST:", request.form)
    return response()


@app.route('/gps/form')
def gps_form():
    return template('gps')


@app.route('/review/<car>/<person>')
def review(car, person):
    print("CAR:", car)
    print("PARSON:", person)
    return template('review')


@app.route('/print', methods=['POST'])
def print_html(car, person):
    print("GET: ", request.args)
    print("POST:", request.form)
    return response()


################################################################################


def template(template_name=None, **kwargs):
    if template_name is None :
        template_name = 'index'
    template_ = template_name + '.html'
    # Update global args with the template's args
    _global_args = dict(global_args)
    _global_args.update(kwargs)
    print(template_)
    return flask.render_template(template_, **_global_args)


def response(code=0, message='', **kwargs):
    '''
        CODES:
            0 - Sucess / Nominal
    '''
    resp = {
        'status': {
            'code': code,
            'message': message,
        }
    }
    if kwargs:
        resp['data'] = kwargs
    return json.dumps(resp)


################################################################################


def start_tornado(app, port=5000, browser=BROWSER, blocking=False, reset_db=True):
    def _start_tornado():
        http_server = tornado.httpserver.HTTPServer(
            tornado.wsgi.WSGIContainer(app))
        http_server.listen(port)
        tornado.ioloop.IOLoop.instance().start()
    # Initialize the web server
    logging.getLogger().setLevel(logging.INFO)
    try:
        app.server_ip_address = socket.gethostbyname(socket.gethostname())
        app.port = port
    except:
        app.server_ip_address = '127.0.0.1'
        app.port = port
    url = 'http://%s:%s' % (app.server_ip_address, app.port)
    print('[web] Tornado server starting at %s' % (url,))
    if browser:
        import webbrowser
        webbrowser.open(url)
    # Blocking
    _start_tornado()
    # if blocking:
    #     _start_tornado()
    # else:
    #     import threading
    #     threading.Thread(target=_start_tornado).start()


def start_from_terminal():
    '''
    Parse command line options and start the server.
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-p', '--port',
        help='which port to serve content on',
        type='int', default=DEFAULT_PORT)
    parser.add_option(
        '--db',
        help='specify an IBEIS database',
        type='str', default='testdb0')

    opts, args = parser.parse_args()
    app.ibeis = ibeis.opendb(db=opts.db)
    start_tornado(app, opts.port)


if __name__ == '__main__':
    start_from_terminal()
