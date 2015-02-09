from __future__ import absolute_import, division, print_function
from PIL import Image
import numpy as np
import cStringIO as StringIO
import re
from os.path import join, exists
from os import mkdir

ORIENTATIONS = {   # used in apply_orientation
    2: (Image.FLIP_LEFT_RIGHT,),
    3: (Image.ROTATE_180,),
    4: (Image.FLIP_TOP_BOTTOM,),
    5: (Image.FLIP_LEFT_RIGHT, Image.ROTATE_90),
    6: (Image.ROTATE_270,),
    7: (Image.FLIP_LEFT_RIGHT, Image.ROTATE_270),
    8: (Image.ROTATE_90,)
}


def open_oriented_image(im_path):
    im = Image.open(im_path)
    if hasattr(im, '_getexif'):
        exif = im._getexif()
        if exif is not None and 274 in exif:
            orientation = exif[274]
            im = apply_orientation(im, orientation)
    img = np.asarray(im).astype(np.float32) / 255.
    if img.ndim == 2:
        img = img[:, :, np.newaxis]
        img = np.tile(img, (1, 1, 3))
    elif img.shape[2] == 4:
        img = img[:, :, :3]
    return img


def apply_orientation(im, orientation):
    '''
    This script handles the skimage exif problem.
    '''
    if orientation in ORIENTATIONS:
        for method in ORIENTATIONS[orientation]:
            im = im.transpose(method)
    return im


def embed_image_html(image, filter_width=True):
    '''Creates an image embedded in HTML base64 format.'''
    image_pil = Image.fromarray((255 * image).astype('uint8'))
    width, height = image_pil.size
    if filter_width:
        _height = 350
        _width = int((float(_height) / height) * width)
    else:
        _width = 700
        _height = int((float(_width) / width) * height)
    image_pil = image_pil.resize((_width, _height))
    string_buf = StringIO.StringIO()
    image_pil.save(string_buf, format='jpeg')
    data = string_buf.getvalue().encode('base64').replace('\n', '')
    return 'data:image/jpeg;base64,' + data


def process_person(car, person):
    car = car.lower()
    person = person.lower()
    try:
        car_number, car_color = re.findall(r"[^\W\d_]+|\d+", car)
        if car_color.isdigit():
            # Flip - color entered first
            car_number, car_color = car_color, car_number
        car_str = car_number + car_color
    except:
        car_number, car_color = '&#8734;', car
        car_str = car
    print("CAR: %s [ %s - %s ]" % (car_str, car_color, car_number, ))
    print("PARSON: %s" % (person, ))
    return car_str, car_number, car_color, person


def ensure_structure(data, kind, car_number, car_color, person=None):
    data       = data.lower()
    kind       = kind.lower()
    car_number = car_number.lower()
    car_color  = car_color.lower()
    person     = person.lower()
    # Create data dir
    if not exists(data):
        mkdir(data)
    # Create kind dir
    kind_dir = join(data, kind)
    if not exists(kind_dir):
        mkdir(kind_dir)
    # Create car dir
    car_dir = join(kind_dir, car_number + car_color)
    if not exists(car_dir):
        mkdir(car_dir)
    # If no person, return car dir
    if person is None:
        return car_dir
    # Create person dir
    person_dir = join(car_dir, person)
    if not exists(person_dir):
        mkdir(person_dir)
    # Return peron dir
    return person_dir
