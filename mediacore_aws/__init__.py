# This file is a part of MediaCore-AWS, Copyright 2011 Simple Station Inc.

import mimetypes
import os
from tempfile import TemporaryFile
from PIL import Image
from boto.s3.key import Key
from pylons import config, tmpl_context

from mediacore.lib.thumbnails import (create_default_thumbs_for,
    create_thumbs_for, delete_thumbs, has_default_thumbs, normalize_thumb_item,
    resize_thumb, thumb_path, thumb_paths, thumb_url, _ext_filter)
from mediacore.model.meta import DBSession
from mediacore.plugin.events import observes

# Import the Amazon Storage engine so that it is registered and usable.
from mediacore_aws.lib.storage import AmazonS3Storage


# Helper functions for the retrieving the currently configured S3 engine.
# This assumes that there will only be on S3 engine enabled at a time.

def get_s3_storage():
    """Helper for retrieving the current S3 Storage engine.

    We use this to get a boto connection to the configured bucket."""
    c = tmpl_context._current_obj()
    if getattr(c, '_s3_engine', ''):
        if c._s3_engine == 'None':
            return None
        return c._s3_engine
    engine = DBSession.query(AmazonS3Storage)\
        .filter(AmazonS3Storage.enabled == True)\
        .first()
    c._s3_engine = engine or 'None'
    return engine

def get_s3_bucket_url():
    """Get the currently configured S3 bucket URL and cache it."""
    c = tmpl_context._current_obj()
    if getattr(c, '_s3_bucket_url', ''):
        if c._s3_bucket_url == 'None':
            return None
        return c._s3_bucket_url
    storage = get_s3_storage()
    if storage:
        c._s3_bucket_url = url = storage.bucket_url
        return url
    else:
        c._s3_bucket_url = 'None'
        return None

def s3_thumb_exists(path):
    """Return True if a thumb exists for this item.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    """
    # if this is called we've already verified a s3 is enabled
    storage = get_s3_storage()
    bucket = storage.connect_to_bucket()
    return bool(bucket.get_key(path))


@observes(thumb_path, appendleft=True)
def s3_thumb_path(item, size, exists=False, ext='jpg'):
    """Get the thumbnail path for the given item and size.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    :param size: Size key to display, see ``thumb_sizes`` in
        :mod:`mediacore.config.app_config`
    :type size: str
    :param exists: If enabled, checks to see if the file actually exists.
        If it doesn't exist, ``None`` is returned.
    :type exists: bool
    :param ext: The extension to use, defaults to jpg.
    :type ext: str
    :returns: The absolute system path or ``None``.
    :rtype: str

    """
    if not item:
        return None

    # fallback to normal thumb handling if no S3 engine is enabled.
    bucket_url = get_s3_bucket_url()
    if not bucket_url:
        return None

    image_dir, item_id = normalize_thumb_item(item)
    image = '%s/%s%s.%s' % (image_dir, item_id, size, ext)
    image_path = image # use the relative path

    if exists and not s3_thumb_exists(image_path):
        return None
    return image_path

@observes(thumb_url, appendleft=True)
def s3_thumb_url(item, size, qualified=False, exists=False):
    """Get the thumbnail url for the given item and size.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    :param size: Size key to display, see ``thumb_sizes`` in
        :mod:`mediacore.config.app_config`
    :type size: str
    :param qualified: If ``True`` return the full URL including the domain.
    :type qualified: bool
    :param exists: If enabled, checks to see if the file actually exists.
        If it doesn't exist, ``None`` is returned.
    :type exists: bool
    :returns: The relative or absolute URL.
    :rtype: str

    """
    if not item:
        return None

    # fallback to normal thumb handling if no S3 engine is enabled.
    bucket_url = get_s3_bucket_url()
    if not bucket_url:
        return None

    image_dir, item_id = normalize_thumb_item(item)
    image = '%s/%s%s.jpg' % (image_dir, item_id, size)
    image_path = image # use the relative path

    if exists and not s3_thumb_exists(image):
        return None
    return bucket_url + image

@observes(create_thumbs_for, appendleft=True)
def s3_create_thumbs_for(item, image_file, image_filename):
    """Creates thumbnails in all sizes for a given Media or Podcast object.

    Side effects: Closes the open file handle passed in as image_file.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    :param image_file: An open file handle for the original image file.
    :type image_file: file
    :param image_filename: The original filename of the thumbnail image.
    :type image_filename: unicode
    """
    # fallback to normal thumb handling if no S3 engine is enabled.
    storage = get_s3_storage()
    if not storage:
        return None
    bucket = storage.connect_to_bucket()

    image_dir, item_id = normalize_thumb_item(item)
    img = Image.open(image_file)

    # TODO: Allow other formats?
    for key, xy in config['thumb_sizes'][item._thumb_dir].iteritems():
        path = thumb_path(item, key)
        thumb_img = resize_thumb(img, xy)
        if thumb_img.mode != "RGB":
            thumb_img = thumb_img.convert("RGB")

        tmpfile = TemporaryFile()
        thumb_img.save(tmpfile, 'JPEG')

        key = Key(bucket)
        key.key = path
        key.set_contents_from_file(tmpfile, {'Content-Type': 'image/jpeg'})
        key.set_acl('public-read')

    # Backup the original image, ensuring there's no odd chars in the ext.
    # Thumbs from DailyMotion include an extra query string that needs to be
    # stripped off here.
    ext = os.path.splitext(image_filename)[1].lower()
    ext_match = _ext_filter.match(ext)
    if ext_match:
        backup_type = ext_match.group(1)
        backup_path = thumb_path(item, 'orig', ext=backup_type)
        image_file.seek(0)

        key = Key(bucket)
        key.key = backup_path
        key.set_contents_from_file(image_file,
            {'Content-Type': mimetypes.guess_type(backup_path)[0]})
        key.set_acl('public-read')

        image_file.close()
    return True

@observes(create_default_thumbs_for, appendleft=True)
def s3_create_default_thumbs_for(item):
    """Create copies of the default thumbs for the given item.

    This copies the default files (all named with an id of 'new') to
    use the given item's id. This means there could be lots of duplicate
    copies of the default thumbs, but at least we can always use the
    same url when rendering.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    """
    # fallback to normal thumb handling if no S3 engine is enabled.
    storage = get_s3_storage()
    if not storage:
        return None
    bucket = storage.connect_to_bucket()

    image_dir, item_id = normalize_thumb_item(item)

    for key in config['thumb_sizes'][image_dir].iterkeys():
        src_file = os.path.join(config['cache.dir'], 'images', thumb_path((image_dir, 'new'), key))
        dst_file = thumb_path(item, key)
        key = Key(bucket)
        key.key = dst_file

        key.set_metadata('is_default_thumb', '1')
        key.set_contents_from_filename(src_file, {'Content-Type': 'image/jpeg'})
        key.set_acl('public-read')
    return True

@observes(delete_thumbs, appendleft=True)
def s3_delete_thumbs(item):
    """Delete the thumbnails associated with the given item.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    """
    # fallback to normal thumb handling if no S3 engine is enabled.
    storage = get_s3_storage()
    if not storage:
        return None
    bucket = storage.connect_to_bucket()

    for path in thumb_paths(item, exists=True).itervalues():
        bucket.delete_key(path)
        if bucket.get_key(path):
            raise RuntimeError('Delete failed')
    return True

@observes(has_default_thumbs, appendleft=True)
def s3_has_default_thumbs(item):
    """Return True if the thumbs for the given item are the defaults.

    :param item: A 2-tuple with a subdir name and an ID. If given a
        ORM mapped class with _thumb_dir and id attributes, the info
        can be extracted automatically.
    :type item: ``tuple`` or mapped class instance
    """
    # fallback to normal thumb handling if no S3 engine is enabled.
    storage = get_s3_storage()
    if not storage:
        return None
    bucket = storage.connect_to_bucket()
    image_dir, item_id = normalize_thumb_item(item)
    key = bucket.get_key(thumb_path(item, 's'))
    return key and key.get_metadata('is_default_thumb') == '1'
