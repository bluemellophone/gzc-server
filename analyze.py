#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import cv2
import simplejson as json
import webbrowser

# IBEIS
from ibeis import constants as const
import ibeis
import utool as ut
import vtool as vt
import numpy as np

from vtool import geometry

from os.path import join, exists, isfile, isdir, realpath, split, basename, splitext  # NOQA
from os import listdir

from shutil import copy  # NOQA
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[analyze]')


# defaults only, use the parameters in observer.py to re-configure
DEFAULT_DATA_DIR = 'data'
DEFAULT_SERVER_IP_ADDRESS = '127.0.0.1'
DEFAULT_SERVER_PORT = 5000
DEFAULT_FRACTION_FOR_REVIEW = 0.8
DEFAULT_MINIMUM_FOR_REVIEW = 8


# takes an image and returns a copy such that the smaller dimension is resized to new_size
def resize_img_by_smaller_dimension(img_in, new_size):
    img = np.copy(img_in)
    h, w, _ = np.shape(img)

    # resize takes (w, h)
    if h > w:
        ratio = float(w) / new_size
        img_out = cv2.resize(img, (new_size, int(h / ratio)))
    elif h < w:
        ratio =  float(h) / new_size
        img_out = cv2.resize(img, (int(w / ratio), new_size))
    else:
        ratio = 1.
        img_out = cv2.resize(img, (new_size, new_size))

    return img_out, ratio


def preprocess_fpath(ibsmap, species_dict, path_to_file, params):
    data_dir = params.get('DEFAULT_DATA_DIR', DEFAULT_DATA_DIR)
    if not exists(path_to_file):
        print("[analyze] The path_to_file %r no longer exists, skipping..." % (path_to_file,))
        return None
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
        species = species_dict['zebra']
    elif animal == 'giraffe':
        species = species_dict['giraffe']
    else:
        print('[analyze] %s is not a valid user photo' % (path_to_file))
        return None  # this is some other image, e.g., the timestamp clock

    print('[analyze] received request for car %s, person %s, to analyze file %s which contains an animal of type %s' % (car, person, path_to_file, animal))
    # ibsmap should always be a dict
    if isinstance(ibsmap, dict):
        ibs = ibsmap[animal]
    else:
        ibs = ibsmap

    # Add contributor to the database for this person
    contrib_row_id = ibs.add_contributors(['IBEIS GZC Participant (%s, %s)' % (car, person, )])[0]  # NOQA
    offset_path = join(data_dir, 'images', car, person, 'offset.json')
    with open(offset_path, 'r') as off:
        data = json.load(off)
        offset = data.get('offset', 0.0)
        print('[analyze] Applying Offset: %0.2f' % (offset, ))

    return car, person, animal, species, offset, contrib_row_id


def analyze(ibsmap, qreq_dict, species_dict, path_to_file_list, params):
    print('[analyze] Beginning Analyze')
    print('[analyze] Received %d file paths' % (len(path_to_file_list)))
    # decompose the filename to get the car/person to whom this image belongs
    info_tup_list = [preprocess_fpath(ibsmap, species_dict, path_to_file, params) for path_to_file in path_to_file_list]
    is_valid_list = [tup_ is not None for tup_ in info_tup_list]

    # get the ungrouped tuples that were not None
    valid_tup_list_ug = ut.filter_items(info_tup_list, is_valid_list)
    valid_path_list_ug = ut.filter_items(path_to_file_list, is_valid_list)

    # group by species
    valid_species_list_ug = ut.get_list_column(valid_tup_list_ug, 3)
    seen_species = {}
    def get_species_tmpid(txt):
        if txt in seen_species:
            return seen_species[txt]
        else:
            seen_species[txt] = len(seen_species)
            return get_species_tmpid(txt)
    species_tmpid_list = np.array([get_species_tmpid(txt) for txt in valid_species_list_ug])
    #ibs.get_species_rowids_from_text(valid_species_list_ug)
    unique_species_rowids, groupxs = vt.group_indices(np.array(species_tmpid_list))

    grouped_valid_tup_list = vt.apply_grouping(np.array(valid_tup_list_ug, dtype=object), groupxs)
    grouped_path_list = vt.apply_grouping(np.array(valid_path_list_ug, dtype=object), groupxs)

    print('[analyze] Created  %d species groups' % (len(grouped_valid_tup_list)))
    print('[analyze] grouped_valid_tup_list = ' + ut.list_str(grouped_valid_tup_list))
    print('[analyze] grouped_path_list      = ' + ut.list_str(grouped_path_list))

    assert len(grouped_valid_tup_list) == len(grouped_path_list), 'lengths must match for zip'
    for groupx, (tup, valid_path_list) in enumerate(zip(grouped_valid_tup_list, grouped_path_list)):
        car_list, person_list, animal_list, species_list, offset_list, contrib_row_id_list = zip(*tup)

        assert ut.list_allsame(species_list)

        animal = animal_list[0]
        species = species_list[0]
        ibs = ibsmap[animal]
        with ut.Indenter('[GROUP-%d-%s]' % (groupx, species)):
            assert ((animal == 'zebra' and species == species_dict['zebra']) or
                    (animal == 'giraffe' and species == species_dict['giraffe'])), 'animal/species mismatch!'
            # Add image to database
            gid_list = ibs.add_images(valid_path_list, auto_localize=False)

            reported_time_list = list(map(vt.parse_exif_unixtime, valid_path_list))
            actual_unixtime_list = [
                reported_unixtime + offset
                for reported_unixtime, offset in
                zip(reported_time_list, offset_list)
            ]
            ibs.set_image_unixtime(gid_list, actual_unixtime_list, duplicate_behavior='filter')
            ibs.set_image_contributor_rowid(gid_list, contrib_row_id_list, duplicate_behavior='filter')

            print('[analyze] starting detection for %d images and species %s...' % (len(valid_path_list), species))
            qaids_list = ibs.detect_random_forest(gid_list, species=species)
            qaid_list, reverse_list = ut.invertible_flatten2(qaids_list)
            print('\n[analyze] detected %d animals of species %s' % (len(qaid_list), species))

            # if there were no detections, don't bother
            if not qaid_list:
                continue

            # because qreq_ is persistent we need only to update the qaid_list
            qreq_ = qreq_dict[animal]  # there is a qreq_ for each species
            qaid_list_unique, unique_inverse = np.unique(qaid_list, return_inverse=True)
            qreq_.set_external_qaids(qaid_list_unique)
            qres_list_unique = ibs.query_chips(qreq_=qreq_, verbose=False)
            qres_list = ut.list_take(qres_list_unique, unique_inverse)

            # so that we can draw a new bounding box for each detection
            detection_bbox_list = ibs.get_annot_verts(qaid_list)
            detection_bboxes_list = ut.unflatten2(detection_bbox_list, reverse_list)
            qreses_list = ut.unflatten2(qres_list, reverse_list)

            with ut.Indenter('[POSTPROCESS]'):
                for _tup in zip(valid_path_list, detection_bboxes_list, qreses_list,
                                car_list, person_list, animal_list, gid_list, qaids_list):
                    postprocess_result(ibs, _tup, params)

            with ut.Indenter('[REVIEW_CHECK]'):
                for car, person in zip(car_list, person_list):
                    check_if_need_review(person, car, params)


def postprocess_result(ibs, _tup, params):
    path_to_file, detection_bbox_list, qres_list, car, person, animal, original_gid, qaids = _tup

    data_dir = params.get('DATA_DIR', DEFAULT_DATA_DIR)

    # create the results directory for the given car/person/animal
    analysis_dir = join(data_dir, 'analysis')
    car_dir = join(analysis_dir, car)
    person_dir = join(car_dir, person)
    animal_dir = join(person_dir, animal)
    ut.ensuredir(data_dir, verbose=True)
    ut.ensuredir(analysis_dir, verbose=True)
    ut.ensuredir(person_dir, verbose=True)
    ut.ensuredir(car_dir, verbose=True)
    ut.ensuredir(animal_dir, verbose=True)

    img_orig = cv2.imread(path_to_file)
    fname = basename(path_to_file)
    fname_base, fname_ext = splitext(fname)
    for (qx, qres), qaid in zip(enumerate(qres_list), qaids):
        if qres is None:
            print('cannot execute query number %d on the database, because qres = %r' % (qx, qres,))
            continue
        assert qres.qaid == qaid
        bbox = ibs.get_annot_verts(qaid)
        print('[analyze] processing detection %d:' % (qx))
        aids = qres.get_top_aids(num=1)

        correspondences_file = join(animal_dir, '%s_%d_correspondences.jpg' % (fname_base, qx))
        print('[analyze] writing correspondences to %s' % (correspondences_file))
        qres.dump_top_match(ibs, fpath_strict=correspondences_file, vert=False, draw_border=False, saveax=True)

        match_gid_list = ibs.get_annot_gids(aids)
        match_aid = aids[0]
        match_gid = match_gid_list[0]
        img_match = ibs.get_images(match_gid_list)[0]

        # draw the bounding box on the matching image from the database
        verts = ibs.get_annot_verts(aids)[0]
        img_match, ratio = resize_img_by_smaller_dimension(img_match, 512)
        verts = [(int(np.round(x / ratio)), int(np.round(y / ratio))) for (x, y) in verts]
        img_match = geometry.draw_verts(img_match, verts)
        bbox_file = join(animal_dir, '%s_%d_match.jpg' % (fname_base, qx))
        status = cv2.imwrite(bbox_file, img_match)
        print('[analyze] writing image match with bounding box to %s (success = %s)' % (bbox_file, status))

        # draw the bounding box on the detection in the original image
        img_orig_bbox, ratio = resize_img_by_smaller_dimension(img_orig, 512)
        bbox = [(int(np.round(x / ratio)), int(np.round(y / ratio))) for (x, y) in bbox]
        img_orig_bbox = geometry.draw_verts(img_orig_bbox, bbox)
        orig_file = join(animal_dir, '%s_%d_original.jpg' % (fname_base, qx))
        status = cv2.imwrite(orig_file, img_orig_bbox)
        print('[analyze] writing original image with bounding box to %s (success = %s)' % (orig_file, status))

        # get interesting information about the query animal
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
            'match_annot_viewpoint':   ibs.get_annot_yaws(match_aid),
        }
        json_file = join(animal_dir, '%s_%d_data.json' % (fname_base, qx))
        print('[analyze] writing information file to %s' % (json_file))
        with open(json_file, 'w') as ofile:
            json.dump(information, ofile)

        # write the detection confidence(s) for this image to the json file
        score = str(qres.aid2_score[match_aid])
        confidence = {'%s_%d' % (fname_base, qx): score}

        confidences_file = join(animal_dir, 'confidences.json')
        # check if this is the first detection for this person
        if not isfile(confidences_file):
            print('[analyze] creating new confidences file: %s' % (confidences_file))
            with open(confidences_file, 'w') as ofile:
                json.dump(confidence, ofile)
        # update the existing json file
        else:
            print('[analyze] updating existing confidences file: %s' % (confidences_file))
            with open(confidences_file, 'r') as ifile:
                data = json.load(ifile)
            data.update(confidence)
            with open(confidences_file, 'w') as ofile:
                json.dump(data, ofile)


def check_if_need_review(person, car, params):
        data_dir = params.get('DATA_DIR', DEFAULT_DATA_DIR)
        server_ip_address = params.get('SERVER_IP_ADDRESS', DEFAULT_SERVER_IP_ADDRESS)
        server_port = params.get('SERVER_PORT', DEFAULT_SERVER_PORT)
        fraction_for_review = params.get('FRACTION_FOR_REVIEW', DEFAULT_FRACTION_FOR_REVIEW)
        minimum_for_review = params.get('MINIMUM_FOR_REVIEW', DEFAULT_MINIMUM_FOR_REVIEW)
        # we need to count how many input files we have received and how many
        # output files have been generated, so that we know if we can send a
        # review request for this directory

        # only count files of image types
        giraffe_input_dir = join(data_dir, 'images', car, person, 'giraffe')
        # perhaps this person never submitted a giraffe
        if isdir(giraffe_input_dir):
            num_input_giraffes = len([f for f in listdir(giraffe_input_dir) if f.endswith(tuple(ut.IMG_EXTENSIONS))])
        else:
            num_input_giraffes = 0

        zebra_input_dir = join(data_dir, 'images', car, person, 'zebra')
        if isdir(zebra_input_dir):
            num_input_zebras = len([f for f in listdir(zebra_input_dir) if f.endswith(tuple(ut.IMG_EXTENSIONS))])
        else:
            num_input_zebras = 0

        # only count files of json type, do not count confidences.json
        giraffe_output_dir = join(data_dir, 'analysis', car, person, 'giraffe')
        # perhaps no giraffes have been generated as output yet
        if isdir(giraffe_output_dir):
            num_output_giraffes = len([f for f in listdir(giraffe_output_dir) if (f.endswith('.json') and f != 'confidences.json')])
        else:
            num_output_giraffes = 0

        zebra_output_dir = join(data_dir, 'analysis', car, person, 'zebra')
        if isdir(zebra_output_dir):
            num_output_zebras = len([f for f in listdir(zebra_output_dir) if (f.endswith('.json') and f != 'confidences.json')])
        else:
            num_output_zebras = 0

        # compute the number of input and output images
        num_input = num_input_giraffes + num_input_zebras
        num_output = num_output_giraffes + num_output_zebras

        # this file will be written once the directory has been sent for review
        review_indicator_file = join(data_dir, 'analysis', car, person, 'review.flag')
        fraction_check = (num_output >= (fraction_for_review * num_input))
        minimum_check = (num_output >= minimum_for_review)
        existence_check = (not isfile(review_indicator_file))
        print('\n[analyze] checking if a review is ready for %s' % (join(data_dir, 'analysis', car, person, 'giraffe')))
        print('[analyze]  minimum files required? %d (minimum = %d) ===> %s' % (num_output, minimum_for_review, minimum_check))
        print('[analyze]  necessary fraction of input files? %.2f * %d = %.2f le? %d ===> %s' % (fraction_for_review, num_input, fraction_for_review * num_input, num_output, fraction_check))
        print('[analyze]  has this directory not been reviewed before? %s' % (existence_check))
        if minimum_check and \
           fraction_check and \
           existence_check:
            review_url = 'http://%s:%s/review/%s/%s' % (server_ip_address, server_port, car, person)
            print('[analyze] *** requesting review at: %s ***' % (review_url))
            webbrowser.open(review_url)

            with open(review_indicator_file, 'w') as ofile:
                ofile.write('this file tells the observer that this directory has already been sent for review and should not be sent again')
        else:
            print('[analyze] not ready for review')


if __name__ == '__main__':
    IBEIS_USE_TWO_DBS = False
    if IBEIS_USE_TWO_DBS:
        IBEIS_DB1 = 'PZ_MUGU_19'
        IBEIS_DB2 = 'GIRM_MUGU_20'
        ibspz = ibeis.opendb(IBEIS_DB1)
        ibsgir = ibeis.opendb(IBEIS_DB2)
        ibsmap = {'zebra': ibspz, 'giraffe': ibsgir}
    else:
        IBEIS_DB = 'MUGU_MASTER'
        ibs_single = ibeis.opendb(IBEIS_DB)
        ibsmap = {'zebra': ibs_single, 'giraffe': ibs_single}

    car = '1GREEN'
    person_letter = 'D'
    analyze_params = {'DEFAULT_DATA_DIR': 'data',
                      'SERVER_IP_ADDRESS': '127.0.0.1',
                      'SERVER_PORT': 5000,
                      'FRACTION_FOR_REVIEW': 0.8,
                      'MINIMUM_FOR_REVIEW': 8}

    species_dict = {'zebra': const.Species.ZEB_PLAIN, 'giraffe': const.Species.GIRAFFE}

    daid_list_zebra   = ibsmap['zebra'].get_valid_aids(is_exemplar=True, species=species_dict['zebra'], nojunk=True)
    daid_list_giraffe = ibsmap['giraffe'].get_valid_aids(is_exemplar=True, species=species_dict['giraffe'], nojunk=True)
    qreq_zebra   = ibsmap['zebra'].new_query_request([], daid_list_zebra)
    qreq_giraffe = ibsmap['giraffe'].new_query_request([], daid_list_giraffe)

    qreq_dict = {'zebra': qreq_zebra, 'giraffe': qreq_giraffe}

    # uncomment filenames to do a full test, requires about 3GB of free RAM
    pz_gpath_list = [
        realpath('data/images/1green/d/zebra/IMG_0030.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0031.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0032.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0033.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0034.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0036.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0037.jpg'),
        realpath('data/images/1green/d/zebra/IMG_0038.jpg'),
    ]
    gir_gpath_list = [
        realpath('data/images/1green/d/giraffe/image1.jpg'),
    ]
    both_list = pz_gpath_list + gir_gpath_list

    #analyze(ibsmap, qreq_dict, species_dict, pz_gpath_list, analyze_params)
    #analyze(ibsmap, qreq_dict, species_dict, gir_gpath_list, analyze_params)

    # Test multiple images of different same species
    analyze(ibsmap, qreq_dict, species_dict, both_list, analyze_params)

    print('\n\n ***** TEST RESULTS ***** \n\n')
    result_list = []
    for fname in both_list:
        print('input image: %s' % (fname))
        ofile = fname.replace('images', 'analysis')
        orig_file = '%s_0_original.jpg' % (splitext(ofile)[0])
        corr_file = '%s_0_correspondences.jpg' % (splitext(ofile)[0])
        data_file = '%s_0_data.json' % (splitext(ofile)[0])

        orig_file_exists = isfile(orig_file)
        corr_file_exists = isfile(corr_file)
        data_file_exists = isfile(data_file)
        print(' original file exists: %s @ %s' % (orig_file_exists, orig_file))
        print(' correspondences file exists: %s @ %s' % (corr_file_exists, corr_file))
        print(' data file exists: %s @ %s' % (data_file_exists, data_file))
        result = orig_file_exists and corr_file_exists and data_file_exists
        result_list.append(result)

    print('\n\n ***** ERRORS ***** \n\n')
    print('the errors may be disregarded for any files below in which the detection in the original image is difficult')
    for fname, result in zip(both_list, result_list):
        if not result:
            print('analyze failed on %s' % (fname))
