#!/usr/bin/env python

from __future__ import print_function

import time
import ibeis
import analyze

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import multiprocessing
import multiprocessing.pool

from os import walk, mkdir
from os.path import join, split, splitext, isfile, exists, realpath

from utool import IMG_EXTENSIONS


# ibs needs to be global so it may be shared among processes
ibs = ibeis.opendb('testdb1')
daid_list = ibs.get_valid_aids(is_exemplar=True)
qreq = ibs.new_query_request([], daid_list)


# need to write our own non-daemonic Pool so that pyrf may create its own processes
# http://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
class NoDaemonProcess(multiprocessing.Process):
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)


# this is our custom, non-daemonic Pool
class NonDaemonicPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


class NewImageHandler(PatternMatchingEventHandler):
    # we only want to check for new image files
    patterns = ['*%s' % ext for ext in IMG_EXTENSIONS]

    def process(self, event):
        """
        event.event_type
            'modified' | 'created' | 'moved' | 'deleted'
        event.is_directory
            True | False
        event.src_path
            path/to/observed/file
        """
        # need to sleep to give the OS time to finish writing the file
        time.sleep(1)
        pool.apply_async(process_image, args=[event.src_path], callback=done_processing)
        print('file: %s, event: %s' % (event.src_path, event.event_type))

#    def on_modified(self, event):
#        self.process(event)

    def on_created(self, event):
        self.process(event)


def process_image(fname):
    print('received request: %s' % (fname))
#    time.sleep(3) # fake processing the request
    analyze.analyze(ibs, qreq, fname)
    return fname


def done_processing(fname):
    print('request completed: %s' % (fname))


def recover_state(pool, data_dir, results_dir):
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
            pool.apply_async(process_image, args=[realpath(filepath_full)], callback=done_processing)


if __name__ == '__main__':
    results_dir = 'data/analysis'
    path_to_watch = 'data/images'

    # need to check that the directory we are watching actually exists
    if not exists('data'):
        mkdir('data')
    images_dir = join('data', 'images')
    if not exists(images_dir):
        mkdir(images_dir)

    # instantiate an asynchronous process to analyze images
    pool = NonDaemonicPool(processes=1)

    # need to check if any files were written while the observer was offline
    recover_state(pool, path_to_watch, results_dir)

    # create the file observer that will watch for new files
    observer = Observer()
    observer.schedule(NewImageHandler(), path=path_to_watch, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
            print('listening...')
    except KeyboardInterrupt:
        print('observer shutting down!')
        observer.stop()

    observer.join()
