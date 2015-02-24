#!/usr/bin/env python

from __future__ import print_function

import sys
import time
import ibeis
import analyze  # NOQA
import traceback

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import multiprocessing

from os import walk, mkdir
from os.path import join, split, splitext, isfile, exists, realpath

import utool as ut
from ibeis import constants as const


# PARAMETERS FOR ANALYZE.PY AND OBSERVER.PY
#
# DEFAULT_DATA_DIR:    The root directory where the analysis, images, gps, and pdfs directories are.
# FILE_CREATION_WAIT:  How long the observer should wait after the last file in
#                      a batch is created, before the entire batch is sent for processing.  This
#                      tries to avoid sending half-written image files to IBEIS.
# MIN_TASKS:           The minimum number of images in the task list before the task list
#                      is sent for processing.
# TASK_TIMEOUT:        If the MIN_TASKS requirement is not satisfied, this is how long
#                      the observer will wait before sending the whole task list regardless.
# IBEIS_USE_TWO_DBS:   Whether IBEIS should use the same database for both
#                      species, or a separate database for each species.
# SERVER_IP_ADDRESS:   If set here, applies to the analyze module too.
# SERVER_PORT:         If set here, applies to the analyze module too.
# FRACTION_FOR_REVIEW: If N and M are the number of input images and output
#                      images respectively, then this directory needs to satisfy M >=
#                      FRACTION_FOR_REVIEW * N to be considered for review.
# MINIMUM_FOR_REVIEW:  The minimum number of files required in a directory before it may be sent for review.

# parameters used by the observer
DEFAULT_DATA_DIR = 'data'
FILE_CREATION_WAIT = 5  # seconds
MIN_TASKS = 8
TASK_TIMEOUT = 5  # seconds
IBEIS_USE_TWO_DBS = False

# parameters that will be passed to the analyze module
analyze_params = {'DEFAULT_DATA_DIR': DEFAULT_DATA_DIR,
                  'SERVER_IP_ADDRESS': '127.0.0.1',
                  'SERVER_PORT': 5000,
                  'FRACTION_FOR_REVIEW': 0.8,
                  'MINIMUM_FOR_REVIEW': 8}

ibeis._preload()

if IBEIS_USE_TWO_DBS:
    IBEIS_DB1 = 'PZ_MUGU_ALL'   # the specialist plains zebra database
    IBEIS_DB2 = 'GIRM_MUGU_20'  # the specialist masai giraffe database
    ibspz = ibeis.opendb(IBEIS_DB1)
    ibsgir = ibeis.opendb(IBEIS_DB2)
    ibsmap = {'zebra': ibspz, 'giraffe': ibsgir}
else:
    IBEIS_DB = 'MUGU_MASTER'    # the merged database containing both plains zebras and masai giraffes
    ibs_single = ibeis.opendb(IBEIS_DB)
    ibsmap = {'zebra': ibs_single, 'giraffe': ibs_single}


# TODO: update the species name for GIRAFFE_MASAI when the DB is ready
# species_dict = {'zebra': const.Species.ZEB_PLAIN, 'giraffe': const.Species.GIRAFFE_MASAI}
species_dict = {'zebra': const.Species.ZEB_PLAIN, 'giraffe': const.Species.GIRAFFE}

daid_list_zebra = ibsmap['zebra'].get_valid_aids(is_exemplar=True, species=species_dict['zebra'], nojunk=True)
daid_list_giraffe = ibsmap['giraffe'].get_valid_aids(is_exemplar=True, species=species_dict['giraffe'], nojunk=True)

# build the query request objects for zebras and giraffes
qreq_zebra = ibsmap['zebra'].new_query_request([], daid_list_zebra)
qreq_giraffe = ibsmap['giraffe'].new_query_request([], daid_list_giraffe)

qreq_dict = {'zebra': qreq_zebra, 'giraffe': qreq_giraffe}


# all checks must be executed for True and any check that fails must return False
def is_valid_user_photo(path_to_file):
    # check existence first
    if not isfile(path_to_file):
        return False
    animal_path, fname = split(path_to_file)
    person_path, animal = split(animal_path)
    car_path, person = split(person_path)
    _, car = split(car_path)

    car = car.lower()
    person = person.lower()
    animal = animal.lower()

    # check that the file is in a directory named "zebra" or "giraffe"
    if not (person.isalpha() and car.isalnum() and (animal == 'zebra' or animal == 'giraffe')):
        return False

    # check for valid image files
    if not fname.endswith(tuple(ut.IMG_EXTENSIONS)):
        return False

    return True


class NewImageHandler(PatternMatchingEventHandler):
    # we only want to check for new image files
    patterns = ['*%s' % ext for ext in ut.IMG_EXTENSIONS]

    def __init__(self, queue):
        self.queue = queue
        super(NewImageHandler, self).__init__()

    def process(self, event):
        """
        event.event_type
            'modified' | 'created' | 'moved' | 'deleted'
        event.is_directory
            True | False
        event.src_path
            path/to/observed/file
        """
        full_path = realpath(event.src_path)
        # avoid spamming with non-photo files like first.jpg, etc.
        if is_valid_user_photo(full_path):
            print('[observer] %s: %s' % (full_path, event.event_type))
            self.queue.put(full_path)

#    def on_modified(self, event):
#        self.process(event)

    def on_created(self, event):
        self.process(event)


def process_images(fname_list):
    print('[observer] received %d requests' % (len(fname_list)))
    # time.sleep(3)  # fake processing the request
    try:
        analyze.analyze(ibsmap, qreq_dict, species_dict, fname_list, analyze_params)
        print('[observer] completed %d requests' % (len(fname_list)))
        return fname_list
    except Exception:
        return sys.exc_info()


def recover_state(queue, data_dir, results_dir):
    # first get all files in the data directory
    input_files = []
    for root, dirnames, filenames in walk(path_to_watch):
        for filename in filenames:
            # only check for actual animal images
            path_to_file = join(root, filename)
            if is_valid_user_photo(path_to_file):
                input_files.append(path_to_file)

    # remember to remove leading backslash so that os.path.join works correctly
    input_files_cleaned = [text.replace(data_dir, '')[1:] for text in input_files]

    # for all the input files, check if the corresponding json file exists
    num_recovered = 0
    for filepath_clean, filepath_full in zip(input_files_cleaned, input_files):
        path, ext = splitext(filepath_clean)

        # check if the json file has been created
        file_to_check_json = join(results_dir, '%s_0_data.json' % (path))

        # we need to check if the match file exists, but need to check all extensions
        files_to_check_match = [join(results_dir, '%s_0_match%s' % (path, _ext)) for _ext in ut.IMG_EXTENSIONS]
        files_to_check_match_existence = [isfile(fname) for fname in files_to_check_match]

        # if the either the json file does't exist or no match file is found, re-analyze this file
        if not isfile(file_to_check_json) or True not in files_to_check_match_existence:
            print('[observer] the file %s has to be analyzed' % (realpath(filepath_full)))
            queue.put(realpath(filepath_full))
            num_recovered += 1

    return num_recovered


if __name__ == '__main__':
    data_dir = DEFAULT_DATA_DIR
    results_dir = join(data_dir, 'analysis')
    path_to_watch = join(data_dir, 'images')

    # need to check that the directory we are watching actually exists
    if not exists(data_dir):
        mkdir(data_dir)
    images_dir = join(data_dir, 'images')
    if not exists(images_dir):
        mkdir(images_dir)

    queue = multiprocessing.Queue()

    # create the file observer that will watch for new files
    observer = Observer()
    observer.schedule(NewImageHandler(queue), path=path_to_watch, recursive=True)
    observer.start()

    if observer.isAlive():
        print('\n\n***** OBSERVER IS LIVE *****\n\n')
    else:
        print('[observer] the observer failed to start!')
        exit(1)

    # check if there are input images without results
    print('[observer] attempting to recover state...')
    num_recovered = recover_state(queue, path_to_watch, results_dir)
    print('[observer] found %d file(s) that are missing results to add to the queue' % (num_recovered))
    print('[observer] observer is now monitoring %s for new files' % (path_to_watch))

    task_list = []
    time_out = TASK_TIMEOUT
    # process new images as the observer puts them in the queue
    try:
        while True:
            time.sleep(1)
            if task_list:
                print('[observer] timeout = %d with %d tasks waiting (need %d to process)' % (time_out, len(task_list), MIN_TASKS))
                time_out -= 1

            while not queue.empty():
                fname = queue.get()
                if fname not in task_list:
                    print('[observer] unpacking task: %s' % (fname))
                    task_list.append(fname)
                else:
                    print('[observer] removed duplicate file: %s' % (fname))

            if len(task_list) >= MIN_TASKS or time_out < 0:
                print('[observer] process triggered! reasons:\n[observer]  enough tasks? %s\n[observer]  timeout? %s' % (len(task_list) > MIN_TASKS, time_out < 0))
                print('[observer] waiting for %d seconds before dispatching...' % (FILE_CREATION_WAIT))
                time.sleep(FILE_CREATION_WAIT)
                result_list = process_images(task_list)
                task_list = []
                time_out = TASK_TIMEOUT

                if isinstance(result_list, tuple):
                    type_, ex, tb = result_list
                    print('\n\n***** EXCEPTION *****\n\n')
                    print('[observer] type_ = %r' % (type_))
                    print('[observer] ex = %r' % (ex))
                    traceback.print_tb(tb)

                print('[observer] still monitoring %s for new files (observer.isAlive() = %s, queue.empty() = %s, len(task_list) = %d)' % (path_to_watch, observer.isAlive(), queue.empty(), len(task_list)))

    except KeyboardInterrupt:
        print('[observer] shutting down!')
        observer.stop()
        observer.join()
