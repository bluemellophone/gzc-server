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
# IBEIS
import ibeis
import utool  # NOQA
import utool as ut
# Web Internal
import serverfuncs, navbar  # NOQA
# Others
import cv2
import zipfile
from datetime import date
from os.path import join, exists, realpath  # NOQA
from os import mkdir, listdir


BROWSER = ut.get_argflag('--browser')
DEFAULT_PORT = 5000
DEFAULT_DATA_DIR = 'data'
DEFAULT_RESULTS_DIR = 'results'
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
    print("CAR:", car)
    print("PARSON:", person)
    return template('review')


################################################################################


@app.route('/images/submit', methods=['POST'])
def images():
    # Hendrik, I need help here   -Jason
    print("GET:  ", request.args)
    print("POST: ", request.form)
    print("FILES:", request.files)

    person_letter = request.form['person_letter']
    car_number = request.form['car_number']
    car_color = request.form['car_color']
    image_archive = request.files['image_archive']

    data_dir = DEFAULT_DATA_DIR # this should eventually be an option
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

    # what about grevy's or plains?
    analyze(car_number + car_color, person_letter, ibeis.constants.Species.ZEB_PLAIN)
    #analyze(car_number + car_color, person_letter, ibeis.constants.Species.ZEB_GREVY)
    #analyze(car_number + car_color, person_letter, ibeis.constants.Species.GIRAFFE)

    return response()


@app.route('/gps/submit', methods=['POST'])
def gps():
    # Hendrik, I need help here   -Jason
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)

    car_number = request.form['car_number']
    car_color = request.form['car_color']
    gps_data = request.files['gps_data']

    data_dir = DEFAULT_DATA_DIR # this should eventually be an option
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


@app.route('/print', methods=['POST'])
def print_html(car, person):
    # Zach, I need help here   -Jason
    print("GET: ", request.args)
    print("POST:", request.form)
    print("FILES:", request.files)
    # This function needs to call wkhtmltopdf with the HTML content in the POST
    # variable 'html_content'.  The wkhtmltopdf code will take the html file
    # and render it to PDF.  Then, the file needs to be sent to a printer by some
    # Python module, see:
    #     http://stackoverflow.com/questions/12723818/print-to-standard-printer-from-python
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

    # Reconstruct data state
    # TODO: RECONSTRUCT THE STATE OF THE DATA FROM THE FILES

    # Blocking
    _start_tornado()
    # if blocking:
    #     _start_tornado()
    # else:
    #     import threading
    #     threading.Thread(target=_start_tornado).start()


def analyze(car, person, species):
    if species == ibeis.constants.Species.ZEB_PLAIN or species == ibeis.constants.Species.ZEB_GREVY:
        animal = 'zebra'
    elif species == ibeis.constants.Species.GIRAFFE:
        animal = 'giraffe' 

    results_dir = DEFAULT_RESULTS_DIR
    if not exists(results_dir):
        mkdir(results_dir)
    image_dir = join(results_dir, 'images')
    if not exists(image_dir):
        mkdir(image_dir)
    car_dir = join(image_dir, car)
    if not exists(car_dir):
        mkdir(car_dir)
    person_dir = join(car_dir, person)
    if not exists(person_dir):
        mkdir(person_dir) 
    animal_dir = join(person_dir, animal)
    if not exists(animal_dir):
        mkdir(animal_dir)

    imdir = join(DEFAULT_DATA_DIR, 'images', car, person, animal)

    print('Analyzing images in %s...' % imdir)
    img_names = listdir(imdir)
    gpaths = [realpath(join(imdir, imname)) for imname in img_names]
    gid_list = app.ibs.add_images(gpaths)
    aids_list = app.ibs.detect_random_forest(gid_list, species=species)
    qaid_list = utool.flatten(aids_list)

    daid_list = app.ibs.get_valid_aids(is_exemplar=True)
    # qreq should be a property of the app - a persistent query request
    qreq_ = app.ibs.new_query_request(qaid_list, daid_list)
    qreq_.set_external_qaids(qaid_list)
    qres_list = app.ibs.query_chips(qreq_=qreq_, verbose=False)
    #qres_list = app.ibs.query_chips(aid_list, daid_list, qreq_=None, verbose=False)
    
    for qx, qres in enumerate(qres_list):
        aid = qres.get_top_aids(num=1)
        fpath = qres.dump_top_match(app.ibs, fpath=join(animal_dir, '%d.jpg' % qx))
       
        gid_list = app.ibs.get_annot_gids(aid) 
        img = app.ibs.get_images(gid_list)[0]
        name = app.ibs.get_annot_names(aid) 
        cv2.imwrite(join(animal_dir, '%s_%d.png' % (name, qx)), img)


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
        type='str', default='testdb1')

    opts, args = parser.parse_args()

    # ibs is the name of an instance of the controller, ibeis is the name of the module
    app.ibs = ibeis.opendb(db=opts.db)
     
    start_tornado(app, opts.port)


if __name__ == '__main__':
    start_from_terminal()
