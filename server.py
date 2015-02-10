#!/usr/bin/env python
from __future__ import absolute_import, division, print_function
# HTTP / HTML
import socket
import tornado.wsgi
import tornado.httpserver
import flask
from flask import request, redirect, url_for, make_response  # NOQA
# Web Internal
import serverfuncs as sf
import subprocess as sp
import simplejson as json
import optparse
import logging
# Other
from os.path import join, exists, isdir, realpath
import utool as ut
import operator
import zipfile
import shutil


################################################################################
# SERVER PARAMETERS
################################################################################

# Flags
BROWSER = ut.get_argflag('--browser')

# Defaults
DEFAULT_PORT = 5000
DEFAULT_DATA_DIR = 'data'
# DEFAULT_PRINTER_NAME = 'MRC-Lab-Printer'
DEFAULT_PRINTER_NAME = '_128_213_17_40'

# Application
app = flask.Flask(__name__)
# print('GET:  ', request.args)
# print('POST: ', request.form)
# print('FILES:', request.files)


################################################################################
# SIMPLE ROUTES
################################################################################


@app.route('/')
def index():
    return sf.template(None)


@app.route('/images/form')
def images_form():
    return sf.template('images')


@app.route('/gps/form')
def gps_form():
    return sf.template('gps')


################################################################################
# COMPLEX / GET ROUTES
################################################################################


@app.route('/review/<car>/<person>')
def review(car, person):
    # Process the car and person strings
    car_str, car_number, car_color, person = sf.process_person(car, person)
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
                    # print(file_prefix, conf)
                    # Load metadata
                    metadata_list = []
                    with open(join(analysis_path, file_prefix + '_data.json')) as f:
                        data = json.load(f)
                        for key in sorted(data.keys()):
                            metadata = 'metadata-%s="%s"' % (key.replace("_", "-"), data[key], )
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
    return sf.template('review', car_str=car_str, car_color=car_color,
                       car_number=car_number, person=person, gps_url=gps_url,
                       analysis_list=analysis_list, valid=valid)


@app.route('/print/<car>/<person>')
def print_pdf(car, person):
    # Process the car and person strings
    car_str, car_number, car_color, person = sf.process_person(car, person)
    # Ensure the folder
    person_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'pdfs', car_number, car_color, person)
    # Check if content.pdf has been written for this person
    pdf_path = join(person_dir, 'content.pdf')
    if not exists(pdf_path):
        return sf.response(code='3', message='[print_pdf] Could not find pdf at %s' % pdf_path)
    # Print using lpr
    # Obviously change MRC-Lab-Printer to whatever is actually going to be used
    execute = 'lpr -P %s %s' % (DEFAULT_PRINTER_NAME, pdf_path, )
    sp.Popen(execute, shell=True)
    # Return nice response
    return sf.response(code='0')


################################################################################
# POST ROUTES
################################################################################


@app.route('/images/submit', methods=['POST'])
def images():
    # Process images for car and person
    car_color     = request.form['car_color'].lower()
    car_number    = request.form['car_number'].lower()
    person        = request.form['person_letter'].lower()
    image_archive = request.files['image_archive']

    # If the directory already exists, delete it
    new_dir = realpath(join(DEFAULT_DATA_DIR, 'images', car_number + car_color, person))
    if isdir(new_dir):
        print('%s already exists, deleting' % new_dir)
        shutil.rmtree(new_dir)

    # Ensure the folder
    person_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'images', car_number, car_color, person)

    # Extract the content
    with zipfile.ZipFile(image_archive, 'r') as zfile:
        zfile.extractall(person_dir)
    # Return nice response
    return sf.response()


@app.route('/gps/submit', methods=['POST'])
def gps():
    # Process gps for car
    car_color  = request.form['car_color'].lower()
    car_number = request.form['car_number'].lower()
    gps_data   = request.files['gps_data']
    # Ensure the folder
    car_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'gps', car_number, car_color)
    input_path  = join(car_dir, 'track.gpx')
    output_path = join(car_dir, 'track.json')
    # Save track.gpx into folder
    gps_data.save(input_path)
    # Convert the gpx file to json for javascript to be able to read it
    with open(input_path, 'r') as gpx_file:
        with open(output_path, 'w') as json_file:
            gpx_content = gpx_file.read()
            json_content = sf.convert_gpx_to_json(gpx_content)
            json_file.write(json_content)
    # Return nice response
    return sf.response()


@app.route('/render/<car>/<person>', methods=['POST'])
def render_html(car, person):
    # Process the car and person strings
    car_str, car_number, car_color, person = sf.process_person(car, person)
    # Ensure the folder
    person_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'pdfs', car_number, car_color, person)
    # Dump the html content to content.html file
    input_path  = join(person_dir, 'content.html')
    output_path = join(person_dir, 'content.pdf')
    try:
        with open(input_path, 'w') as html_file:
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
        return sf.response(code='1', msg='[render_html] Could not write HTML' + str(ioe))
    # Render content.html with wkhtmltopdf to content.pdf
    #TODO: Maybe redirect STDERR to something useful so we can put it in the JSON response
    execute = 'wkhtmltopdf -s Letter -B 0 -L 0 -R 0 -T 0 --zoom 1.1 %s %s' % (input_path, output_path)
    # print(execute)
    sp.Popen(execute, shell=True)
    # Return nice response
    return sf.response()


################################################################################
# TORNADO / FLASK INITIALIZATION
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


def start_from_terminal():
    # Parse command line arduments
    parser = optparse.OptionParser()
    parser.add_option(
        '-p', '--port',
        help='which port to serve content on',
        type='int', default=DEFAULT_PORT)
    # Start tornado
    opts, args = parser.parse_args()
    start_tornado(app, opts.port)


if __name__ == '__main__':
    start_from_terminal()
