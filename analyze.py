#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import cv2
import simplejson as json
import optparse
import webbrowser

# IBEIS
import ibeis
import utool  # NOQA
import utool as ut  # NOQA
import numpy as np

from vtool import geometry
from utool import IMG_EXTENSIONS

from os.path import join, exists, isfile, realpath, split, basename, splitext  # NOQA
from os import mkdir, listdir

from shutil import copy  # NOQA


DEFAULT_DATA_DIR = 'data'
SERVER_IP_ADDRESS = '127.0.0.1'
SERVER_PORT = 5000

FRACTION_FOR_REVIEW = 0.8  # fraction of the input images for whichgenerated results are required
MINIMUM_FOR_REVIEW = 5  # minimum number of results required


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


def analyze(ibs, qreq_, path_to_file):
    # decompose the path to get the animal type, person letter, and car information
    animal_path, fname = split(path_to_file)
    person_path, animal = split(animal_path)
    car_path, person = split(person_path)
    _, car = split(car_path)

    car = car.lower()
    person = person.lower()
    animal = animal.lower()

    if animal == 'zebra':
        # for we are only concerned with plains zebras
        species = ibeis.constants.Species.ZEB_PLAIN
    elif animal == 'giraffe':
        species = ibeis.constants.Species.GIRAFFE
    else:
        return  # this is some other image, e.g., the timestamp clock

    print('received request for car %s, person %s, to analyze file %s which contains an animal of type %s' % (car, person, path_to_file, animal))

    # create the results directory for the given car/person/animal
    data_dir = DEFAULT_DATA_DIR
    if not exists(data_dir):
        mkdir(data_dir)
        print('creating directory %s' % (data_dir))
    analysis_dir = join(DEFAULT_DATA_DIR, 'analysis')
    if not exists(analysis_dir):
        mkdir(analysis_dir)
        print('creating directory %s' % (analysis_dir))
    car_dir = join(analysis_dir, car)
    if not exists(car_dir):
        mkdir(car_dir)
        print('creating directory %s' % (car_dir))
    person_dir = join(car_dir, person)
    if not exists(person_dir):
        mkdir(person_dir)
        print('creating directory %s' % (person_dir))
    animal_dir = join(person_dir, animal)
    if not exists(animal_dir):
        mkdir(animal_dir)
        print('creating directory %s' % (animal_dir))

    gid_list = ibs.add_images([path_to_file])
    original_gid = gid_list[0]
    print('starting detection for image %s and species %s' % (path_to_file, species))
    aids_list = ibs.detect_random_forest(gid_list, species=species)
    qaid_list = utool.flatten(aids_list)

    # so that we can draw a new bounding box for each detection
    img_orig = cv2.imread(path_to_file)
    detection_bbox_list = ibs.get_annot_verts(qaid_list)

    # daid_list = ibs.get_valid_aids(is_exemplar=True)
    # qreq should be a property of the - a persistent query request
    #qreq_ = ibs.new_query_request(qaid_list, daid_list)
    qreq_.set_external_qaids(qaid_list)
    qres_list = ibs.query_chips(qreq_=qreq_, verbose=False)
    #qres_list = ibs.query_chips(aid_list, daid_list, qreq_=None, verbose=False)

    fname_base, fname_ext = splitext(fname)
    for (qx, qres), bbox in zip(enumerate(qres_list), detection_bbox_list):
        aid = qres.get_top_aids(num=1)
        qres.dump_top_match(ibs, fpath_strict=join(animal_dir, '%s_%d_correspondences.jpg' % (fname_base, qx)), vert=False, draw_border=False, saveax=True)

        gid_list = ibs.get_annot_gids(aid)
        match_aid = aid[0]
        match_gid = gid_list[0]
        img_match = ibs.get_images(gid_list)[0]

        # draw the bounding box on the matching image from the database
        verts = ibs.get_annot_verts(aid)[0]
        img_match = geometry.draw_verts(img_match, verts)
        img_match = resize_img_by_smaller_dimension(img_match, 512)
        cv2.imwrite(join(animal_dir, '%s_%d_match.jpg' % (fname_base, qx)), img_match)

        # draw the bounding box on the detection in the original image
        img_orig_bbox = geometry.draw_verts(img_orig, bbox)
        img_orig_bbox = resize_img_by_smaller_dimension(img_orig_bbox, 512)
        cv2.imwrite(join(animal_dir, '%s_%d_original.jpg' % (fname_base, qx)), img_orig_bbox)

        # get intesting information about the query animal
        information = {
            'original_image_path':     ibs.get_image_paths(original_gid),
            'original_image_gname':    ibs.get_image_gnames(original_gid),
            'original_image_unixtime': ibs.get_image_unixtime(original_gid),
            'original_image_lat':      ibs.get_image_lat(original_gid),
            'original_image_lon':      ibs.get_image_lon(original_gid),
            'match_image_path':        ibs.get_image_paths(match_gid),
            'match_image_gname':       ibs.get_image_gnames(match_gid),
            'match_image_unixtime':    ibs.get_image_unixtime(match_gid),
            'match_image_lat':         ibs.get_image_lat(match_gid),
            'match_image_lon':         ibs.get_image_lon(match_gid),
            'match_annot_name':        ibs.get_annot_names(match_aid),
            'match_annot_species':     ibs.get_annot_species(match_aid),
            'match_annot_viewpoint':   ibs.get_annot_viewpoints(match_aid),
        }
        with open(join(animal_dir, '%s_%d_data.json' % (fname_base, qx)), 'w') as ofile:
            json.dump(information, ofile)

        # write the detection confidence(s) for this image to the json file
        score = str(qres.aid2_score[match_aid])
        confidence = {'%s_%d' % (fname_base, qx): score}
        print(confidence)
        confidences_file = join(animal_dir, 'confidences.json')
        # check if this is the first detection for this person
        if not isfile(confidences_file):
            with open(confidences_file, 'w') as ofile:
                json.dump(confidence, ofile)
        # update the existing json file
        else:
            with open(confidences_file, 'r') as ifile:
                data = json.load(ifile)
            data.update(confidence)
            with open(confidences_file, 'w') as ofile:
                json.dump(data, ofile)

        # we need to count how many input files we have received and how many output files have been generated, so that we know if we can send a review request for this directory

        # only count files of image types
        num_input_giraffes = len([f for f in listdir(join(DEFAULT_DATA_DIR, 'images', car, person, 'giraffe')) if f.endswith(tuple(IMG_EXTENSIONS))])

        num_input_zebras = len([f for f in listdir(join(DEFAULT_DATA_DIR, 'images', car, person, 'zebra')) if f.endswith(tuple(IMG_EXTENSIONS))])

        # only count files of json type
        num_output_giraffes = len([f for f in listdir(join(DEFAULT_DATA_DIR, 'analysis', car, person, 'giraffe')) if f.endswith('.json')])
        num_output_zebras = len([f for f in listdir(join(DEFAULT_DATA_DIR, 'analysis', car, person, 'zebra')) if f.endswith('.json')])

        # compute the sum (subtract one for confidences.json)
        num_input = num_input_giraffes + num_input_zebras
        num_output = num_output_giraffes + num_output_zebras - 1

        # this file will be written once the directory has been sent for review
        review_indicator_file = join(DEFAULT_DATA_DIR, 'analysis', car, person, 'sentforreview.donotdelete')
        if num_output >= (FRACTION_FOR_REVIEW * num_input) and \
           num_output >= MINIMUM_FOR_REVIEW and \
           not isfile(review_indicator_file):
            review_url = 'http://%s:%s/review/%s/%s' % (SERVER_IP_ADDRESS, SERVER_PORT, car, person)
            webbrowser.open(review_url)

            with open(review_indicator_file, 'w') as ofile:
                ofile.write('this file tells the observer that this directory has already been sent for review and should not be sent again')


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
    daid_list = ibs.get_valid_aids(is_exemplar=True)
    qreq = ibs.new_query_request([], daid_list)

    analyze(ibs, qreq, realpath('data/images/1red/a/zebra/image1.jpg'))
    analyze(ibs, qreq, realpath('data/images/1red/a/giraffe/image1.jpg'))
