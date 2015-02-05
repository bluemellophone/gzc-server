#!/usr/bin/env python

import time
import ibeis
import analyze

from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler

from multiprocessing import Pool

pool = None
ibs = None

class MyHandler(PatternMatchingEventHandler):
    # we only want to check for new image files
    patterns = ["*.jpg", "*.JPG", '*.png', '*.PNG']

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
        pool.apply_async(process_image, [event.src_path], callback=done_processing)
        print event.src_path, event.event_type

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)


def process_image(fname):
    print 'received request: %s' % (fname)
    #time.sleep(5) # fake processing the request
    analyze.analyze(ibs, fname)
    return fname


def done_processing(fname):
    print 'request completed: %s' % (fname)


def recover_state(data_dir, results_dir):
    pass

 
if __name__ == '__main__':
    results_dir = 'data/analysis/images'
    path_to_watch = 'data/images'

    ibs = ibeis.opendb('testdb1')

    # need to check if any files were written while the observer was offline
    recover_state(path_to_watch, results_dir)

    # create the file observer that will watch for new files
    observer = Observer()
    observer.schedule(MyHandler(), path=path_to_watch, recursive=True)
    observer.start()

    pool = Pool(processes=1)

    try:
        while True:
            time.sleep(1)
            print 'listening...'
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

