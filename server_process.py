#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import cv2
import simplejson as json
import optparse

# IBEIS
import ibeis
import utool  # NOQA
import utool as ut

from os.path import join, exists, realpath  # NOQA
from os import mkdir, listdir


DEFAULT_DATA_DIR = 'data'


def analyze(ibs, car, person, species):
    if species == ibeis.constants.Species.ZEB_PLAIN or species == ibeis.constants.Species.ZEB_GREVY:
        animal = 'zebra'
    elif species == ibeis.constants.Species.GIRAFFE:
        animal = 'giraffe'

    data_dir = DEFAULT_DATA_DIR
    if not exists(data_dir):
        mkdir(data_dir)
    analysis_dir = join(DEFAULT_DATA_DIR, 'analysis')
    if not exists(analysis_dir):
        mkdir(analysis_dir)
    image_dir = join(analysis_dir, 'images')
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
    gid_list = ibs.add_images(gpaths)
    aids_list = ibs.detect_random_forest(gid_list, species=species)
    qaid_list = utool.flatten(aids_list)

    daid_list = ibs.get_valid_aids(is_exemplar=True)
    # qreq should be a property of the - a persistent query request
    qreq_ = ibs.new_query_request(qaid_list, daid_list)
    qreq_.set_external_qaids(qaid_list)
    qres_list = ibs.query_chips(qreq_=qreq_, verbose=False)
    #qres_list = ibs.query_chips(aid_list, daid_list, qreq_=None, verbose=False)

    for qx, qres in enumerate(qres_list):
        aid = qres.get_top_aids(num=1)
        fpath = qres.dump_top_match(ibs, fpath=join(animal_dir, '%d.jpg' % qx), vert=False)
       
        gid_list = ibs.get_annot_gids(aid) 
        img = ibs.get_images(gid_list)[0]
        name = ibs.get_annot_names(aid)
        cv2.imwrite(join(animal_dir, '%s_%d.png' % (name, qx)), img)
        
        information = {'name': name}
        with open(join(animal_dir, 'image_%d_data.json' % qx), 'w') as ofile:
          json.dump(information, ofile)


def process(ibs, car, person_letter):
    # what about grevy's or plains?
    analyze(ibs, car, person_letter, ibeis.constants.Species.ZEB_PLAIN)
    #analyze(ibs, car, person_letter, ibeis.constants.Species.ZEB_GREVY)
    #analyze(ibs, car, person_letter, ibeis.constants.Species.GIRAFFE)


if __name__ == '__main__':
    '''
    Parse command line options and start the server.
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '--db',
        help='specify an IBEIS database',
        type='str', default='testdb1')

    opts, args = parser.parse_args()

    car = '1RED'
    person_letter = 'A'
    ibs = ibeis.opendb(db=opts.db)
    process(ibs, car, person_letter)

