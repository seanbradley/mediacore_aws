# This file is a part of MediaCore-AWS, Copyright 2011 Simple Station Inc.

import hmac
import os
import simplejson

from base64 import b64encode
from boto.exception import S3ResponseError
from boto.s3.connection import S3Connection
from datetime import datetime, timedelta
from shutil import copyfileobj
from urlparse import urlunsplit

from pylons import config

from mediacore.lib.compat import sha1
from mediacore.lib.i18n import N_
from mediacore.lib.filetypes import guess_container_format, guess_media_type
from mediacore.lib.storage import safe_file_name, FileStorageEngine, StorageError
from mediacore.lib.storage.localfiles import LocalFileStorage
from mediacore.lib.uri import StorageURI
from mediacore.lib.util import delete_files, url_for

from mediacore_aws.forms.admin.storage import AmazonS3StorageForm

class AmazonS3Storage(FileStorageEngine):

    engine_type = u'AmazonS3Storage'
    """A uniquely identifying unicode string for the StorageEngine."""

    default_name = N_(u'Amazon S3', domain='amazon_aws')

    _default_data = {
        'aws_access_key': '',
        'aws_secret_key': '',
        's3_bucket_name': '',
        's3_bucket_dir': '',
        'cf_download_domain': '',
        'cf_streaming_domain': '',
    }

    settings_form_class = AmazonS3StorageForm

    try_before = [LocalFileStorage]

    def prepare_for_upload(self, media_file, content_type, filename, filesize):
        if content_type != 'multipart/form-data':
            raise StorageError("Cannot direct upload without using multipart "
                               "form data and we haven't implemented a file "
                               "upload pass through.")

        media_file.storage = self
        media_file.unique_id = self._get_path(safe_file_name(media_file, filename))

        access_key = self._data['aws_access_key'].encode('utf-8')
        secret_key = self._data['aws_secret_key'].encode('utf-8')
        bucket_name = self._data['s3_bucket_name'].encode('utf-8')

        acl = 'public-read'
        mimetype = media_file.mimetype
        success_action_status = 201 # Return XML instead of redirecting
        expiration = (datetime.utcnow() + timedelta(hours=4))\
            .strftime('%Y-%m-%dT%H:%m:%S.000Z')

        policy_obj = {
            'expiration': expiration,
            'conditions': [
                {'bucket': bucket_name},

                # Prevent tampering with our POST data below
                {'key': media_file.unique_id},
                {'acl': acl},
                {'success_action_status': str(success_action_status)},
                {'Content-Type': mimetype},

                # Allow (and require) the extra Filename var added by Flash
                ['starts-with', '$Filename', ''],

                # Enforce the filesize we've been given, leaving some extra
                # room for the rest of the form data
                ['content-length-range', filesize, filesize + 1048576],
            ]
        }

        policy = b64encode(simplejson.dumps(policy_obj)).encode('utf-8')
        signature = b64encode(hmac.new(secret_key, policy, sha1).digest())

        post_data = {
            'AWSAccessKeyId': access_key,
            'key': media_file.unique_id,
            'acl': acl,
            'success_action_status': success_action_status,
            'Policy': policy,
            'Signature': signature,
            'Content-Type': mimetype,
        }

        return {
            'upload_url': 'https://%s.s3.amazonaws.com/' % bucket_name,
            'extra_post_data': post_data,
            'file_post_var_name': 'file',
        }

    def delete(self, media_file):
        """Delete the stored file represented by the given unique ID.

        :type media_file: :class:`~mediacore.model.media.MediaFile`
        :param media_file: The associated media file object.
        :rtype: boolean
        :returns: True if successful, False if an error occurred.

        """
        access_key = self._data['aws_access_key'].encode('utf-8')
        secret_key = self._data['aws_secret_key'].encode('utf-8')
        bucket_name = self._data['s3_bucket_name'].encode('utf-8')
        file_path = self._get_path(media_file.unique_id)

        try:
            conn = S3Connection(access_key, secret_key)
        except S3ResponseError, e:
            raise StorageError("There was an error connecting to Amazon S3."
                               "Please make sure that you have entered"
                               "the correct credentials in your settings.")
        try:
            bucket = conn.get_bucket(bucket_name)
        except S3ResponseError, e:
            raise StorageError("Error - Unable to connect to S3 bucket")

        # TODO: Find out if there is a way that avoids an extra API call
        # as Boto doesn't appear to return a value from a delete_key()
        if bucket.get_key(file_path):
            bucket.delete_key(file_path)
            if bucket.get_key(file_path):
                raise StorageError("Error - Failed to delete media from S3")
            else:
                return True
        else:
            raise StorageError("Error - Media not found on S3")

    def get_uris(self, media_file):
        """Return a list of URIs from which the stored file can be accessed.

        :type media_file: :class:`~mediacore.model.media.MediaFile`
        :param media_file: The associated media file object.
        :rtype: list
        :returns: All :class:`StorageURI` tuples for this file.

        """
        uris = []

        s3_bucket_name = self._data['s3_bucket_name']
        s3_bucket_dir = self._data['s3_bucket_dir']
        s3_bucket_url = 'https://%s.s3.amazonaws.com/' % s3_bucket_name
        cf_download_domain = self._data['cf_download_domain']
        cf_streaming_domain = self._data['cf_streaming_domain']
        file_path = self._get_path(media_file.unique_id)

        if cf_download_domain:
            cf_download_url = 'http://%s' % cf_download_domain
            uris.append(StorageURI(media_file, 'http', file_path, cf_download_url))
        else:
            uris.append(StorageURI(media_file, 'http', file_path, s3_bucket_url))

        if cf_streaming_domain:
            cf_streaming_url = 'http://%s/cfx/st' % cf_streaming_domain
            uris.append(StorageURI(media_file, 'rtmp', file_path, cf_streaming_url))

        return uris

    def _get_path(self, unique_id):
        """Return the local file path for the given unique ID.

        This method is exclusive to this engine.
        """
        basepath = self._data['s3_bucket_dir']
        if basepath:
            return os.path.join(basepath, unique_id)
        return unique_id

FileStorageEngine.register(AmazonS3Storage)

