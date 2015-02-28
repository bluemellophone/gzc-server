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
from detecttools.directory import Directory
import time
import datetime
from os.path import join, exists, isdir, realpath
import utool as ut
import vtool as vt
import operator
import zipfile
import shutil


################################################################################
# SERVER PARAMETERS
################################################################################

# Flags
BROWSER = ut.get_argflag('--browser')

# Ranges
CAR_COLORS = ['white', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'black']
CAR_NUMBER = map(str, range(1, 26))  # 50
PERSON_LETTERS = ['a', 'b', 'c', 'd', 'e', 'f']  # , 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'aa', 'bb', 'cc', 'dd', 'ee', 'ff', 'gg', 'hh', 'ii', 'jj', 'kk', 'll', 'mm', 'nn', 'oo', 'pp', 'qq', 'rr', 'ss', 'tt', 'uu', 'vv', 'ww', 'xx', 'yy', 'zz']
TIME_HOUR = map(str, range(0, 24))
TIME_MINUTE = map(str, range(0, 60))
TRACK_NUMBERS = map(str, range(1, 6))

# Defaults
DEFAULT_PORT = 5000
DEFAULT_DATA_DIR = 'data'
# DEFAULT_PRINTER_NAME = 'MRC-Lab-Printer'
# DEFAULT_PRINTER_NAME = '_128_213_17_40'
DEFAULT_PRINTER_NAME = 'printer'
# GMT_OFFSET = -5  # Troy
GMT_OFFSET = 3  # Nairobi

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


@app.route('/map/form')
def map_form():
    return sf.template('map_form')


@app.route('/overview')
def overview():
    return sf.template('overview')


@app.route('/cards')
def cards():
    page_list = [ [ [ (1, 'red', 'a'), (24, 'blue', 'f'), (3, 'orange', 'd'), ], [ (18, 'purple', 'c'), (4, 'white', 'd'), (2, 'black', 'b'), ], [ (9, 'green', 'a'), (11, 'yellow', 'e'), (19, 'red', 'c'), ], [ (4, 'orange', 'b'), (3, 'blue', 'f'), (21, 'purple', 'a'), ], ] ]
    i = 1
    page = []
    row = []
    for car_color in CAR_COLORS:
        for car_number in CAR_NUMBER:
            for person_letter in PERSON_LETTERS:
                row.append( (car_number, car_color, person_letter) )
                if i % 3 == 0:
                    page.append(row)
                    row = []
                if i % 12 == 0:
                    page_list.append(page)
                    page = []
                i += 1

    return sf.template('cards', page_list=page_list)


@app.route('/workspace')
def workspace():
    return sf.template('workspace')


################################################################################
# COMPLEX / GET ROUTES
################################################################################


@app.route('/status')
def status():
    cars = {}

    # STEP 1 - GPS
    try:
        gps_path      = join(DEFAULT_DATA_DIR, 'gps')
        direct = Directory(gps_path, recursive=True, include_file_extensions=[])
        for direct_car in direct.directory_list:
            base_car = direct_car.base()
            car_path = join(gps_path, base_car)
            # Establish flags
            flags = {}
            flags['submitted_gpx']  = exists(join(car_path, 'track.gpx'))
            flags['submitted_generated_json'] = exists(join(car_path, 'track.json'))
            cars[base_car] = { 'gps': flags }
            cars[base_car]['persons'] = {}
    except:
        print("No GPS data submitted yet")

    # STEP 2 - IMAGES
    try:
        images_path   = join(DEFAULT_DATA_DIR, 'images')
        direct = Directory(images_path, recursive=True, include_file_extensions=[])
        for direct_car in direct.directory_list:
            base_car = direct_car.base()
            if base_car not in cars:
                cars[base_car] = {}
            cars[base_car]['persons'] = {}
            # Construct dict for person
            for direct_person in direct_car.directory_list:
                base_person = direct_person.base()
                person_path = join(images_path, base_car, base_person)
                # Establish flags, inherit GPS for person if car has GPS flags
                if 'gps' in cars[base_car]:
                    flags = dict(cars[base_car]['gps'])
                else:
                    flags = {}
                flags['submitted_images'] = True
                flags['submitted_first'] = exists(join(person_path, 'first.jpg'))
                flags['submitted_last']  = exists(join(person_path, 'last.jpg'))
                # Giraffe flags
                giraffe_path = join(person_path, 'giraffe')
                if isdir(giraffe_path):
                    flags['submitted_giraffe'] = True
                    temp = Directory(giraffe_path, include_file_extensions='images')
                    flags['submitted_giraffe_number'] = len(temp.files())
                # Zebra flags
                zebra_path = join(person_path, 'zebra')
                if isdir(zebra_path):
                    flags['submitted_zebra'] = True
                    temp = Directory(zebra_path, include_file_extensions='images')
                    flags['submitted_zebra_number'] = len(temp.files())
                # Generated offset
                offset_path = join(person_path, 'offset.json')
                if exists(offset_path):
                    flags['submitted_generated_offset'] = True
                    with open(offset_path, 'r') as off:
                        data = json.load(off)
                        offset = data.get('offset', 0.0)
                    flags['submitted_generated_offset_number'] = offset
                # Assign flags to person
                cars[base_car]['persons'][base_person] = flags
            cars[base_car]['persons_number'] = len(cars[base_car]['persons'].keys())
    except:
        print("No Image data submitted yet")

    # STEP 3 - ANALYSIS
    try:
        analysis_path = join(DEFAULT_DATA_DIR, 'analysis')
        direct = Directory(analysis_path, recursive=True, include_file_extensions=[])
        for direct_car in direct.directory_list:
            base_car = direct_car.base()
            if base_car not in cars:
                cars[base_car] = {}
            # Append to dict for person
            for direct_person in direct_car.directory_list:
                base_person = direct_person.base()
                person_path = join(analysis_path, base_car, base_person)
                # Establish flags
                if base_person in cars[base_car]['persons']:
                    flags = dict(cars[base_car]['persons'][base_person])
                else:
                    flags = {}
                flags['analyzed'] = True
                flags['analyzed_review'] = exists(join(person_path, 'review.flag'))
                # Giraffe flags
                giraffe_path = join(person_path, 'giraffe')
                if isdir(giraffe_path):
                    flags['analyzed_giraffe'] = True
                    flags['analyzed_generated_giraffe_confidences'] = exists(join(giraffe_path, 'confidences.json'))
                    temp = Directory(giraffe_path, include_file_extensions=['jpg', 'json'])
                    flags['analyzed_giraffe_number'] = (len(temp.files()) - 1) / 4.0  # 4 images per detection generated (minus 1 confidences)
                    if not flags['analyzed_generated_giraffe_confidences'] and flags['analyzed_giraffe_number'] == -0.25:
                        flags['analyzed_giraffe_number'] = 0.0

                # Zebra flags
                zebra_path = join(person_path, 'zebra')
                if isdir(zebra_path):
                    flags['analyzed_zebra'] = True
                    flags['analyzed_generated_zebra_confidences'] = exists(join(zebra_path, 'confidences.json'))
                    temp = Directory(zebra_path, include_file_extensions=['jpg', 'json'])
                    flags['analyzed_zebra_number'] = (len(temp.files()) - 1) / 4.0  # 4 images per detection generated (minus 1 confidences)
                    if not flags['analyzed_generated_zebra_confidences'] and flags['analyzed_zebra_number'] == -0.25:
                        flags['analyzed_zebra_number'] = 0.0
                # Assign flags to person
                cars[base_car]['persons'][base_person] = flags
            cars[base_car]['persons_number'] = len(cars[base_car]['persons'].keys())
    except:
        print("No images analyzed yet")

    # STEP 4 - PDFS
    try:
        pdfs_path     = join(DEFAULT_DATA_DIR, 'pdfs')
        direct = Directory(pdfs_path, recursive=True, include_file_extensions=[])
        for direct_car in direct.directory_list:
            base_car = direct_car.base()
            if base_car not in cars:
                cars[base_car] = {}
            # Append to dict for person
            for direct_person in direct_car.directory_list:
                base_person = direct_person.base()
                person_path = join(pdfs_path, base_car, base_person)
                # Establish flags
                if base_person in cars[base_car]['persons']:
                    flags = dict(cars[base_car]['persons'][base_person])
                else:
                    flags = {}
                flags['reviewed'] = True
                flags['reviewed_posted']   = exists(join(person_path, 'content.html'))
                flags['reviewed_rendered'] = exists(join(person_path, 'content.pdf'))
                flags['reviewed_printed']  = exists(join(person_path, 'printed.flag'))
                # Assign flags to person
                cars[base_car]['persons'][base_person] = flags
            cars[base_car]['persons_number'] = len(cars[base_car]['persons'].keys())
    except:
        print("No PDFs rendered yet")

    extra = {}
    extra['cars'] = cars
    extra['cars_number'] = len(cars.keys())
    return sf.response(**extra)


@app.route('/review/<car>/<person>')
def review(car, person):
    # Process the car and person strings
    car_str, car_number, car_color, person = sf.process_person(car, person)
    # Build analysis list
    valid = False
    analysis_dict = {}
    analysis_dict[person] = None
    gps_path = 'data/gps/%s/track.json' % (car_str, )
    # Find friends
    for friend in PERSON_LETTERS:
        friend_path = join('data', 'analysis', car_str, friend)
        if isdir(friend_path):
            analysis_dict[friend] = None

    # Get analysis for person and friends
    for letter in analysis_dict.keys():
        # Load offset from json
        person_dir = join('data', 'images', car_str, letter)
        offset_path = join(person_dir, 'offset.json')
        if exists(offset_path):
            with open(offset_path, 'r') as off:
                data = json.load(off)
                offset = data.get('offset', 0.0)
        else:
            offset = 0.0
        analysis_list = []
        for species in ['zebra', 'giraffe']:
            analysis_path = join('data', 'analysis', car_str, letter, species)
            confidence_path = join(analysis_path, 'confidences.json')
            if exists(confidence_path):
                with open(confidence_path, 'r') as f:
                    data = json.load(f)
                    confidence_list = sorted(data.items(), key=operator.itemgetter(1), reverse=True)
                # Load sorted prefixes
                for (file_prefix, conf) in confidence_list:
                    # print(file_prefix, conf)
                    # Load metadata
                    metadata_list = []
                    with open(join(analysis_path, file_prefix + '_data.json')) as f:
                        data = json.load(f)
                        data['original_image_unixtime'] += offset
                        for key in sorted(data.keys()):
                            metadata = 'metadata-%s=%s' % (key.replace("_", "-"), data[key], )
                            metadata_list.append(metadata)
                    # Load image paths
                    correspondences = url_for('static', filename=join(analysis_path, file_prefix + '_correspondences.jpg'))
                    original        = url_for('static', filename=join(analysis_path, file_prefix + '_original.jpg'))
                    match           = url_for('static', filename=join(analysis_path, file_prefix + '_match.jpg'))
                    metadata        = ' '.join(metadata_list)
                    # Build analysis
                    analysis = (len(analysis_list), conf, correspondences, original, match, metadata)
                    analysis_list.append(analysis)
            else:
                print('ERROR: %s has no analysis' % (analysis_path, ))
        analysis_dict[letter] = analysis_list
    # Set valid flag
    if exists(gps_path) and len(analysis_dict[person]) >= 1:
        valid = True
    # Set valid if override
    if 'override' in request.args:
        valid = True
    return sf.template('review', car_str=car_str, car_color=car_color,
                       car_number=car_number, person=person,
                       analysis_dict=analysis_dict, valid=valid)


@app.route('/print/<car>/<person>')
def print_pdf(car, person):
    # Process the car and person strings
    car_str, car_number, car_color, person = sf.process_person(car, person)
    # Ensure the folder
    person_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'pdfs', car_number, car_color, person)
    # Check if content.pdf has been written for this person
    pdf_path = join(person_dir, 'content.pdf')
    if not exists(pdf_path):
        return sf.response(400, '[print_pdf] Could not find pdf at %s' % pdf_path)
    # Print using lpr
    # Obviously change MRC-Lab-Printer to whatever is actually going to be used
    execute = 'lpr -P %s %s' % (DEFAULT_PRINTER_NAME, pdf_path, )
    sp.Popen(execute, shell=True)
    flag_path = join(person_dir, 'printed.flag')
    if exists(flag_path):
        shutil.rmtree(flag_path)
    with open(flag_path, 'w') as flag:
        flag.write(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
    # Return nice response
    return sf.response()


################################################################################
# POST ROUTES
################################################################################


@app.route('/images/submit', methods=['POST'])
def images():
    # Process images for car and person
    extra = {}
    car_number    = request.form.get('car_number', '').lower()
    car_color     = request.form.get('car_color', '').lower()
    person        = request.form.get('person_letter', '').lower()
    time_hour     = request.form.get('image_first_time_hour', '')
    time_minute   = request.form.get('image_first_time_minute', '')

    # Validate
    if car_number not in CAR_NUMBER:
        return sf.response(102, '[images] Car number invalid')
    if car_color not in CAR_COLORS:
        return sf.response(101, '[images] Car color invalid')
    if person not in PERSON_LETTERS:
        return sf.response(103, '[images] Person letter invalid')
    if time_hour not in TIME_HOUR:
        return sf.response(104, '[images] Time (hour) invalid')
    if time_minute not in TIME_MINUTE:
        return sf.response(105, '[images] Time (minute) invalid')

    # return sf.response(999, '[images] TEST')

    # Get image archive
    image_archive = request.files.get('image_archive', None)
    if image_archive is None:
        return sf.response(106, '[images] No image archive posted')

    # If the directory already exists, delete it
    new_dir = realpath(join(DEFAULT_DATA_DIR, 'images', car_number + car_color, person))
    if isdir(new_dir):
        print('Reprocessing Images for (%s, %s, %s) because %s already exists, deleting old submission' % (car_number, car_color, person, new_dir, ))
        shutil.rmtree(new_dir)
        extra['overwritten'] = True

    # Ensure the folder
    person_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'images', car_number, car_color, person)

    # Extract the content
    try:
        with zipfile.ZipFile(image_archive, 'r') as zfile:
            zfile.extractall(person_dir)
    except Exception as e:
        shutil.rmtree(new_dir)
        return sf.response(100, '[images] Could not write ZIP file: %r' % (e, ), **extra)

    # Error checking for files
    try:
        message = ''
        if not isdir(join(person_dir, 'zebra')):
            message = 'Sub-directory "zebra" does not exist'
            raise ValueError
        if not isdir(join(person_dir, 'giraffe')):
            message = 'Sub-directory "giraffe" does not exist'
            raise ValueError
        if not exists(join(person_dir, 'first.jpg')):
            message = 'Image "first.jpg" does not exist'
            raise ValueError
        if not exists(join(person_dir, 'last.jpg')):
            message = 'Image "last.jpg" does not exist'
            raise ValueError
    except Exception as e:
        shutil.rmtree(new_dir)
        return sf.response(106, '[images] %s: %r' % (message, e, ), **extra)

    # Capture offset from first image to today and reported time
    reported_time = vt.parse_exif_unixtime(join(person_dir, 'first.jpg'))
    actual_time = datetime.datetime.today()
    actual_time = actual_time.replace(hour=int(time_hour), minute=int(time_minute), second=0, microsecond=0)
    actual_time = time.mktime(actual_time.timetuple())
    # mysql_format = '%Y-%m-%d %H:%M:%S'
    # print("Actual Time  : %s" % (actual_time.strftime(mysql_format), ))
    # print("Reported Time: %s" % (reported_time.strftime(mysql_format), ))
    offset = actual_time - reported_time
    print("Time Sync - Reported: %s, Actual %s [ OFFSET: %f ]" % (reported_time, actual_time, offset, ))
    # Write offset to file
    json_file = join(person_dir, 'offset.json')
    with open(json_file, 'w') as ofile:
        json.dump({ 'offset': offset }, ofile)

    # Return nice response
    return sf.response(**extra)


@app.route('/gps/submit', methods=['POST'])
def gps():
    # Process gps for car
    extra = {}
    car_number   = request.form.get('car_number', '').lower()
    car_color    = request.form.get('car_color', '').lower()
    time_hour    = request.form.get('gps_start_time_hour', '')
    time_minute  = request.form.get('gps_start_time_minute', '')
    track_number = request.form.get('track_number', '')

    # Validate
    if car_number not in CAR_NUMBER:
        return sf.response(202, '[gps] Car number invalid')
    if car_color not in CAR_COLORS:
        return sf.response(201, '[gps] Car color invalid')
    if time_hour not in TIME_HOUR:
        return sf.response(204, '[gps] Time (hour) invalid')
    if time_minute not in TIME_MINUTE:
        return sf.response(205, '[gps] Time (minute) invalid')
    if track_number not in TRACK_NUMBERS:
        return sf.response(205, '[gps] Track number invalid')

    # return sf.response(999, '[gps] TEST')

    # Get GPS data from GPX file
    gps_data   = request.files.get('gps_data', None)
    if gps_data is None:
        return sf.response(206, '[gps] No GPX file posted')

    # If the directory already exists, delete it
    new_dir = realpath(join(DEFAULT_DATA_DIR, 'gps', car_number + car_color,))
    if isdir(new_dir):
        print('Reprocessing GPS for (%s, %s) because %s already exists, deleting old submission' % (car_number, car_color, new_dir, ))
        shutil.rmtree(new_dir)
        extra['overwritten'] = True

    # Ensure the folder
    car_dir = sf.ensure_structure(DEFAULT_DATA_DIR, 'gps', car_number, car_color)
    input_path  = join(car_dir, 'track.gpx')
    output_path = join(car_dir, 'track.json')
    track_path  = join(car_dir, '%s.track' % (track_number, ))
    with open(track_path, 'w') as track:
        track.write('')

    # Save track.gpx into folder
    try:
        gps_data.save(input_path)
    except Exception as e:
        shutil.rmtree(new_dir)
        return sf.response(200, '[gps] Could not write GPX file: %r' % (e, ), **extra)

    # Convert the gpx file to json for javascript to be able to read it
    with open(input_path, 'r') as gpx_file:
        with open(output_path, 'w') as json_file:
            gpx_content = gpx_file.read()
            try:
                json_content = sf.convert_gpx_to_json(gpx_content, GMT_OFFSET)
            except Exception as e:
                shutil.rmtree(new_dir)
                return sf.response(207, '[gps] Could not parse GPX file: %r' % (e, ), **extra)
            json_file.write(json_content)

    # Return nice response
    return sf.response(**extra)


@app.route('/map_online/submit', methods=['GET', 'POST'])
def map_online():
    gpx_str = request.form.get('gps_data_str', None)
    car_str  = request.args.get('car_str', None)
    json_str = None
    if gpx_str is not None and len(gpx_str) > 0:
        json_str = sf.convert_gpx_to_json(gpx_str, GMT_OFFSET)
    elif car_str is not None:
        # Build analysis list
        gps_path = 'data/gps/%s/track.json' % (car_str, )
        if exists(gps_path):
            print("FOUND GPS JSON")
            with open(gps_path, 'r') as json_file:
                json_str = json_file.read()
            print(json_str)
    else:
        gpx_data  = request.files.get('gps_data_gpx', None)
        json_data = request.files.get('gps_data_json', None)
        if gpx_data is not None:
            gpx_str = gpx_data.stream.read()
            if len(gpx_str) > 0:
                json_str = sf.convert_gpx_to_json(gpx_str, GMT_OFFSET)
        elif json_data is not None:
            json_str = json_data.stream.read()
    return sf.template('map_online', data=json_str)


@app.route('/map/submit', methods=['GET', 'POST'])
def map():
    gpx_str  = request.form.get('gps_data_str', None)
    offset   = request.args.get('offset', None)
    car_str  = request.args.get('car_str', None)
    json_str = None
    if gpx_str is not None and len(gpx_str) > 0:
        json_str = sf.convert_gpx_to_json(gpx_str, GMT_OFFSET)
    elif car_str is not None:
        # Build analysis list
        gps_path = 'data/gps/%s/track.json' % (car_str, )
        if exists(gps_path):
            with open(gps_path, 'r') as json_file:
                json_str = json_file.read()
    else:
        gpx_data  = request.files.get('gps_data_gpx', None)
        json_data = request.files.get('gps_data_json', None)
        if gpx_data is not None:
            gpx_str = gpx_data.stream.read()
            if len(gpx_str) > 0:
                json_str = sf.convert_gpx_to_json(gpx_str, GMT_OFFSET)
        elif json_data is not None:
            json_str = json_data.stream.read()
    return sf.template('map', data=json_str, offset=offset)


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
            head_content = request.form.get('head_content', '')
            html_content = request.form.get('html_content', '')
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
            content = content.replace('<script src="https://maps.gstatic.com/maps-api-v3/api/js/19/10/main.js"></script>', '')  # Fix for JavaScript Google Maps
            content = content.encode('utf-8')
            html_file.write(content)
    except Exception as e:
        return sf.response(300, '[render_html] Could not write HTML file: %r' % (e, ))
    # Render content.html with wkhtmltopdf to content.pdf
    #TODO: Maybe redirect STDERR to something useful so we can put it in the JSON response
    execute = 'wkhtmltopdf -s Letter -B 0 -L 0 -R 0 -T 0 --javascript-delay 3000 --zoom 1.1 %s %s' % (input_path, output_path)
    # execute = 'wkhtmltopdf -s A4 -B 0 -L 0 -R 0 -T 0 --javascript-delay 3000 --zoom 1.1 %s %s' % (input_path, output_path)
    print(execute)
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
