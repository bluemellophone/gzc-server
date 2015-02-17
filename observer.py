#!/usr/bin/env python

from __future__ import print_function

import sys
import time
import ibeis
import analyze
import traceback

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import multiprocessing

from os import walk, mkdir
from os.path import join, split, splitext, isfile, exists, realpath

from utool import IMG_EXTENSIONS

# TODO: how long should this wait be?
# how long should the watchdog wait before it assumes a new file is fully written?
FILE_CREATION_WAIT = 5

ibeis._preload()


ibs = ibeis.opendb('PZ_MTEST')

# build the query request objects for zebras and giraffes
daid_list_zebra = ibs.get_valid_aids(is_exemplar=True, species=ibeis.constants.Species.ZEB_PLAIN)
daid_list_giraffe = ibs.get_valid_aids(is_exemplar=True, species=ibeis.constants.Species.GIRAFFE)

qreq_zebra = ibs.new_query_request([], daid_list_zebra)
qreq_giraffe = ibs.new_query_request([], daid_list_giraffe)

qreq = {'zebra': qreq_zebra, 'giraffe': qreq_giraffe}


class NewImageHandler(PatternMatchingEventHandler):
    # we only want to check for new image files
    patterns = ['*%s' % ext for ext in IMG_EXTENSIONS]

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
        print('file: %s, event: %s' % (full_path, event.event_type))
        print('giving the OS %d seconds to finish writing the file %s' % (FILE_CREATION_WAIT, full_path))
        # need to sleep to give the OS time to finish writing the file
        # note that new files will still be detected!!!
        time.sleep(FILE_CREATION_WAIT)
        self.queue.put(full_path)

#    def on_modified(self, event):
#        self.process(event)

    def on_created(self, event):
        self.process(event)


def process_image(fname):
    print('received request: %s' % (fname))
#    time.sleep(10) # fake processing the request
    try:
        analyze.analyze(ibs, qreq, fname)
        print('request completed: %s' % (fname))
        return fname
    except Exception:
        return sys.exc_info()


def recover_state(queue, data_dir, results_dir):
    # first get all files in the data directory
    input_files = []
    for root, dirnames, filenames in walk(path_to_watch):
        for filename in filenames:
            # only check for actual animal images
            _, animal = split(root)
            if animal == 'giraffe' or animal == 'zebra':
                input_files.append(join(root, filename))

    # remember to remove leading backslash so that os.path.join works correctly
    input_files_cleaned = [text.replace(data_dir, '')[1:] for text in input_files]

    # for all the input files, check if the corresponding json file exists
    num_recovered = 0
    for filepath_clean, filepath_full in zip(input_files_cleaned, input_files):
        path, ext = splitext(filepath_clean)

        # check if the json file has been created
        file_to_check_json = join(results_dir, '%s_0_data.json' % (path))

        # we need to check if the match file exists, but need to check all extensions
        files_to_check_match = [join(results_dir, '%s_0_match%s' % (path, _ext)) for _ext in IMG_EXTENSIONS]
        files_to_check_match_existence = [isfile(fname) for fname in files_to_check_match]

        # if the either the json file does't exist or no match file is found, re-analyze this file
        if not isfile(file_to_check_json) or True not in files_to_check_match_existence:
            print('the file %s has to be analyzed' % (realpath(filepath_full)))
            queue.put(realpath(filepath_full))
            num_recovered += 1

    return num_recovered


if __name__ == '__main__':
    results_dir = 'data/analysis'
    path_to_watch = 'data/images'

    # need to check that the directory we are watching actually exists
    if not exists('data'):
        mkdir('data')
    images_dir = join('data', 'images')
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
        print('the observer failed to start!')
        exit(1)

    # check if there are input images without results
    print('attempting to recover state...')
    num_recovered = recover_state(queue, path_to_watch, results_dir)
    print('found %d file(s) that are missing results to add to the queue' % (num_recovered))
    print('observer is now monitoring %s for new files' % (path_to_watch))

    # process new images as the observer puts them in the queue
    try:
        while True:
            time.sleep(1)
            # print('queue size: %d' % (queue.qsize()))
            if not queue.empty():
                result = process_image(queue.get())
                if isinstance(result, tuple):
                    type_, ex, tb = result
                    print('\n\n***** EXCEPTION *****\n\n')
                    print('type_ = %r' % (type_))
                    print('ex = %r' % (ex))
                    traceback.print_tb(tb)
                    #raise type_, ex, tb
                else:
                    print('observer is still monitoring %s for new files (observer.isAlive() = %s, queue.empty() = %s)' % (path_to_watch, observer.isAlive(), queue.empty()))
    except KeyboardInterrupt:
        print('observer shutting down!')
        observer.stop()

    observer.join()
