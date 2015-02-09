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
import operator
import subprocess as sp
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
    car = car.lower()
    person = person.lower()
    try:
        car_number, car_color = re.findall(r"[^\W\d_]+|\d+", car)
        if car_color.isdigit():
            # Flip - color entered first
            car_number, car_color = car_color, car_number
        car_str = car_number + car_color
    except:
        car_number, car_color = '&#8734;', car
        car_str = car
    # Print Processing
    print("CAR:", car_str, car_color, car_number)
    print("PARSON:", person)
    # Build analysis list
    valid = False
    analysis_list = []
    gps_path = 'data/gps/%s/track.json' % (car_str, )
    gps_url = url_for('static', filename=gps_path)
    if exists(gps_path):
        # Get GPS url
        # Get analysis
        for species in ['zebra', 'giraffe']:
            analysis_path = join('data', 'analysis', car_str, person, species)
            confidence_path = join(analysis_path, 'confidences.json')
            if exists(confidence_path):
                with open(confidence_path) as f:
                    data = json.load(f)
                    confidence_list = sorted(data.items(), key=operator.itemgetter(1), reverse=True)
                # Load sorted prefixes
                for (file_prefix, conf) in confidence_list:
                    # Load metadata
                    metadata_list = []
                    with open(join(analysis_path, file_prefix + '_data.json')) as f:
                        data = json.load(f)
                        for key in sorted(data.keys()):
                            metadata = 'metadata-%s="%s"' % (key, data[key], )
                            metadata_list.append(metadata)
                    # Load image paths
                    correspondences = url_for('static', filename=join(analysis_path, file_prefix + '_correspondences.jpg'))
                    original        = url_for('static', filename=join(analysis_path, file_prefix + '_original.jpg'))
                    match           = url_for('static', filename=join(analysis_path, file_prefix + '_match.jpg'))
                    metadata        = ' '.join(metadata_list)
                    # Build analysis
                    analysis = (len(analysis_list), correspondences, original, match, metadata)
                    analysis_list.append(analysis)
            else:
                print('ERROR: %s has no analysis' % (analysis_path, ))
        # Set valid flag
        if len(analysis_list) >= 1:
            valid = True
    return template('review', car_str=car_str, car_color=car_color,
                    car_number=car_number, person=person, gps_url=gps_url,
                    analysis_list=analysis_list, valid=valid)


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
    car_color = request.form['car_color'].lower()
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
    # print("GET: ", request.args)
    # print("POST:", request.form)
    # print("FILES:", request.files)
    # Take HTML content, write to file (content.html), call wkhtmltopdf, save the pdf in data/pdfs/car/person/content.pdf
    data_dir = DEFAULT_DATA_DIR  # this should eventually be an option
    if not exists(data_dir):
        mkdir(data_dir)
    image_dir = join(data_dir, 'pdfs')
    if not exists(image_dir):
        mkdir(image_dir)
    car_dir = join(image_dir, car)
    if not exists(car_dir):
        mkdir(car_dir)
    person_dir = join(car_dir, person)
    if not exists(person_dir):
        mkdir(person_dir)
    try:
        with open(join(data_dir, "pdfs/%s/%s/content.html" % (car, person)), 'w') as html_file:
            printable = url_for('static', filename='css/printable.css')
            head_content = request.form['head_content']
            html_content = request.form['html_content']
            content = '''
            <!DOCTYPE html>
            <html>
                <head>
                    %s
                    <link type="text/css" rel="stylesheet" href="%s"/>
                </head>
                <body>
                    <div class="printarea">
                        <div class="printarea-document">
                            %s
                        </div>
                    </div>
                </body>
            <html>'
            ''' % (head_content, printable, html_content)
            content = content.replace('/static/', request.url_root + 'static/')
            content = content.encode('utf-8')
            html_file.write(content)
    except IOError as ioe:
        return response(code='1', msg='[render_html] Could not write HTML' + str(ioe))
    input_file_path = join(data_dir, "pdfs/%s/%s/content.html" % (car, person))
    output_file_path = join(data_dir, "pdfs/%s/%s/content.pdf" % (car, person))
    #TODO: Maybe redirect STDERR to something useful so we can put it in the JSON response
    execute = 'wkhtmltopdf -s Letter -B 0 -L 0 -R 0 -T 0 --zoom 1.1 %s %s' % (input_file_path, output_file_path)
    # print(execute)
    sp.Popen(execute, shell=True)

    # wk_retcode = sp.call(execute, shell=True)
    # if wk_retcode != 0:
    #     return response(code='2', message='[render_html] Failed to convert HTML to PDF')
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
    data_dir = DEFAULT_DATA_DIR  # this should eventually be an option
    pdf_path = join(data_dir, "/%s/%s/content.pdf" % (car, person))
    if not exists(pdf_path):
        return response(code='3', message="[print_pdf] Could not find pdf at %s" % pdf_path)
    # Print using lpr
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)
    # Obviously change MRC-Lab-Printer to whatever is actually going to be used
    lpr_retcode = sp.call("lpr -P MRC-Lab-Printer %s" % pdf_path)
    if lpr_retcode != 0:
        return response(code='4', message='[print_pdf] lpr failed with error code %d' % lpr_retcode)
    # Return 0 for success, <some_code> for failed to print, a different one for failed to find/read content.pdf
    return response(code='0')


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
            1 - Error / File I/O error
            2 - Error / wkhtmltopdf failure
            3 - Error / No content.pdf
            4 - Error / Failed to print
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
