#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import cv2
import simplejson as json
import optparse

# IBEIS
import ibeis
import utool  # NOQA
import utool as ut
import numpy as np

from vtool import geometry

from os.path import join, exists, realpath, split, basename, splitext  # NOQA
from os import mkdir, listdir

from shutil import copy


DEFAULT_DATA_DIR = 'data'


# takes an image and returns a copy such that the smaller dimension is resized to new_size
def resize_img_by_smaller_dimension(img_in, new_size):
    img = np.copy(img_in)
    h, w, _ = np.shape(img)

    # resize takes (w, h)
    if h > w:
        img_out = cv2.resize(img, (new_size, int(h / (float(w) / new_size))))
    elif h < w:
        img_out = cv2.resize(img, (int(w / (float(h) / new_size)), new_size))
    else:
        img_out = cv2.resize(img, (new_size, new_size))
    
    return img_out


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

    print('received request for car %s, person %s, to analyze file %s which contains an animal of type %s' % (car, person, path_to_file, animal))

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

    gid_list = ibs.add_images([path_to_file])
    aids_list = ibs.detect_random_forest(gid_list, species=species)
    qaid_list = utool.flatten(aids_list)
    detection_bbox_list = ibs.get_annot_verts(qaid_list)

    # so that we can draw a new bounding box for each detection
    img_orig = cv2.imread(path_to_file)

    daid_list = ibs.get_valid_aids(is_exemplar=True)
    # qreq should be a property of the - a persistent query request
    qreq_ = ibs.new_query_request(qaid_list, daid_list)
    qreq_.set_external_qaids(qaid_list)
    qres_list = ibs.query_chips(qreq_=qreq_, verbose=False)
    #qres_list = ibs.query_chips(aid_list, daid_list, qreq_=None, verbose=False)

    fname_base, fname_ext = splitext(fname)
    for (qx, qres), bbox in zip(enumerate(qres_list), detection_bbox_list):
        aid = qres.get_top_aids(num=1)
        score = qres.aid2_score
        fpath = qres.dump_top_match(ibs, fpath_strict=join(animal_dir, '%s_%d_correspondences.jpg' % (fname_base, qx)), vert=False)
       
        gid_list = ibs.get_annot_gids(aid) 
        img_match = ibs.get_images(gid_list)[0]
        name = ibs.get_annot_names(aid)[0]

        # draw the bounding box on the matching image from the database
        verts = ibs.get_annot_verts(aid)[0]
        img_match = geometry.draw_verts(img_match, verts)
        img_match = resize_img_by_smaller_dimension(img_match, 512)
        cv2.imwrite(join(animal_dir, '%s_%d_match.jpg' % (fname_base, qx)), img_match)

        # draw the bounding box on the detection in the original image 
        img_orig_bbox = geometry.draw_verts(img_orig, bbox)
        img_orig_bbox = resize_img_by_smaller_dimension(img_orig_bbox, 512)
        cv2.imwrite(join(animal_dir, '%s_%d_animal.jpg' % (fname_base, qx)), img_orig_bbox)

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
    analyze(ibs, realpath('data/images/1RED/A/zebra/image1.jpg'))
    analyze(ibs, realpath('data/images/1RED/A/giraffe/image1.jpg'))

