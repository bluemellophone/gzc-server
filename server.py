#!/usr/bin/env python
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
# Web Internal
import re
import serverfuncs, navbar  # NOQA
# Others
import zipfile
from datetime import date
from os.path import join, exists, realpath  # NOQA
from os import mkdir, listdir  # NOQA

import utool as ut


BROWSER = ut.get_argflag('--browser')
DEFAULT_PORT = 5000
DEFAULT_DATA_DIR = 'data'
app = flask.Flask(__name__)
global_args = {
    'NAVBAR': navbar.NavbarClass(),
    'YEAR':   date.today().year,
}


################################################################################


@app.route('/')
def index():
    return template(None)


@app.route('/images/form')
def images_form():
    return template('images')


@app.route('/gps/form')
def gps_form():
    return template('gps')


@app.route('/review/<car>/<person>')
def review(car, person):
    # Jason will work on this function
    try:
        car_color, car_number = re.findall(r"[^\W\d_]+|\d+", car.lower())
    except:
        car_color, car_number = car, ""
    print("CAR:", car, car_color, car_number)
    print("PARSON:", person)
    return template('review', car_color=car_color, car_number=car_number, person=person)


################################################################################


@app.route('/images/submit', methods=['POST'])
def images():
    print("GET:  ", request.args)
    print("POST: ", request.form)
    print("FILES:", request.files)

    person_letter = request.form['person_letter'].lower()
    car_number = request.form['car_number']
    car_color = request.form['car_color'].lower()
    image_archive = request.files['image_archive']

    data_dir = DEFAULT_DATA_DIR  # this should eventually be an option
    if not exists(data_dir):
        mkdir(data_dir)
    image_dir = join(data_dir, 'images')
    if not exists(image_dir):
        mkdir(image_dir)
    car_dir = join(image_dir, car_number + car_color)
    if not exists(car_dir):
        mkdir(car_dir)
    person_dir = join(car_dir, person_letter)
    if not exists(person_dir):
        mkdir(person_dir)

    with zipfile.ZipFile(image_archive, 'r') as zfile:
        zfile.extractall(person_dir)

    return response()


@app.route('/gps/submit', methods=['POST'])
def gps():
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)

    car_number = request.form['car_number']
    car_color = request.form['car_color']
    gps_data = request.files['gps_data']

    data_dir = DEFAULT_DATA_DIR  # this should eventually be an option
    if not exists(data_dir):
        mkdir(data_dir)
    gps_dir = join(data_dir, 'gps')
    if not exists(gps_dir):
        mkdir(gps_dir)
    car_dir = join(gps_dir, car_number + car_color)
    if not exists(car_dir):
        mkdir(car_dir)

    gps_data.save(join(car_dir, 'dummy_gps.csv'))

    return response()


@app.route('/render/<car>/<person>', methods=['POST'])
def render_html(car, person):
    # Take HTML content, write to file (content.html), call wkhtmltopdf, save the pdf in data/pdfs/car/person/content.pdf
    data_dir = DEFAULT_DATA_DIR  # this should eventually be an option
    if not exists(data_dir):
        mkdir(data_dir)
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)
    try:
        with open(join(data_dir, "/%s/%s/content.html" % (car, person)), 'w') as html_file:
            html_file.write(request.html_content)
    except IOError as ioe:
        return response(code='1', msg='[render_html] Could not write HTML' + str(ioe))
    input_file_path = join(data_dir, "/%s/%s/content.html" % (car, person))
    output_file_path = join(data_dir, "/%s/%s/content.pdf" % (car, person))
    #TODO: Maybe redirect STDERR to something useful so we can read it if needed
    wk_retcode = sp.call('wkhtmltopdf -s Letter -B 0 -L 0 -R 0 -T 0 --zoom 1.1 %s %s' % (input_file_path, output_file_path))
    if wk_retcode != 0:
        return response(code='2', message='[render_html] Failed to convert HTML to PDF')
    # This function needs to call wkhtmltopdf with the HTML content in the POST
    # variable 'html_content'.  The wkhtmltopdf code will take the html file
    # and render it to PDF.  Then, the file needs to be sent to a printer by some
    # Python module, see:
    #     http://stackoverflow.com/questions/12723818/print-to-standard-printer-from-python
    # Return 0 for success, something for failed to write content.pdf
    return response(code='0')


@app.route('/print/<car>/<person>', methods=['POST'])
def print_pdf(car, person):
    # Check for content.pdf in data/pdfs/car/person/, then print it
    # Print using lpr
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)
    # Return 0 for success, <some_code> for failed to print, a different one for failed to find/read content.pdf
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
            1 - Error / File error
            2 - Error / wkhtmltopdf failure
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

    # Reconstruct data state
    # TODO: RECONSTRUCT THE STATE OF THE DATA FROM THE FILES

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
    
    opts, args = parser.parse_args()

    start_tornado(app, opts.port)


if __name__ == '__main__':
    start_from_terminal()
