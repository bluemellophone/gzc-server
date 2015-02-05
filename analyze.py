#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import cv2
import simplejson as json
import optparse

# IBEIS
import ibeis
import utool  # NOQA
import utool as ut

from os.path import join, exists, realpath, split, basename, splitext  # NOQA
from os import mkdir, listdir

from shutil import copy


DEFAULT_DATA_DIR = 'data'


def analyze(ibs, path_to_file):
    # decompose the path to get the animal type, person letter, and car information
    animal_path, fname = split(path_to_file)
    person_path, animal = split(animal_path)
    car_path, person = split(person_path)
    _, car = split(car_path)
    if animal == 'zebra': 
        # for we are only concerned with plains zebras
        species = ibeis.constants.Species.ZEB_PLAIN
    elif animal == 'giraffe':
        species = ibeis.constants.Species.GIRAFFE

    # create the results directory for the given car/person/animal
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

#    imdir = join(DEFAULT_DATA_DIR, 'images', car, person, animal)
#
#    # pass the new image to IBEIS
#    print('Analyzing images in %s...' % imdir)
#    img_names = listdir(imdir)
#    gpaths = [realpath(join(imdir, imname)) for imname in img_names]
    gid_list = ibs.add_images([path_to_file])
    aids_list = ibs.detect_random_forest(gid_list, species=species)
    qaid_list = utool.flatten(aids_list)

    daid_list = ibs.get_valid_aids(is_exemplar=True)
    # qreq should be a property of the - a persistent query request
    qreq_ = ibs.new_query_request(qaid_list, daid_list)
    qreq_.set_external_qaids(qaid_list)
    qres_list = ibs.query_chips(qreq_=qreq_, verbose=False)
    #qres_list = ibs.query_chips(aid_list, daid_list, qreq_=None, verbose=False)

    fname_base, fname_ext = splitext(fname)
    for qx, qres in enumerate(qres_list):
        aid = qres.get_top_aids(num=1)
        fpath = qres.dump_top_match(ibs, fpath_strict=join(animal_dir, '%s_%d_correspondences.jpg' % (fname_base, qx)), vert=False)
       
        gid_list = ibs.get_annot_gids(aid) 
        img = ibs.get_images(gid_list)[0]
        name = ibs.get_annot_names(aid)[0]

        # write the image of the query result along with the original
        cv2.imwrite(join(animal_dir, '%s_%d_match.png' % (fname_base, qx)), img)
        copy(path_to_file, join(animal_dir, '%s_%d_animal.%s' % (fname_base, qx, fname_ext)))
        
        # get intesting information about the query animal 
        information = {'result_name': name, 'original_filename': path_to_file}
        with open(join(animal_dir, '%s_%d_data.json' % (fname_base, qx)), 'w') as ofile:
            json.dump(information, ofile)


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
    analyze(ibs, 'data/images/1RED/A/zebra/image1.jpg')
    analyze(ibs, 'data/images/1RED/A/giraffe/image1.jpg')

