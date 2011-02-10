# This file is a part of MediaCore-AWS, Copyright 2011 Simple Station Inc.

from mediacore.forms import ListFieldSet, TextField
from mediacore.forms.admin.storage import StorageForm
from mediacore.lib.i18n import N_
from mediacore.lib.util import merge_dicts

class AmazonS3StorageForm(StorageForm):

    fields = StorageForm.fields + [
        ListFieldSet('aws',
            suppress_label=True,
            legend=N_('Amazon Details:', domain='mediacore_aws'),
            children=[
                TextField('aws_access_key', label_text=N_('AWS Access Key', domain='mediacore_aws')),
                TextField('aws_secret_key', label_text=N_('AWS Secret Key', domain='mediacore_aws')),
                TextField('s3_bucket_name', label_text=N_('S3 Bucket Name', domain='mediacore_aws')),
                TextField('s3_bucket_dir', label_text=N_('Subdirectory on S3 to upload to', domain='mediacore_aws')),
                TextField('cf_download_domain', label_text=N_('Cloudfront Download Domain', domain='mediacore_aws'), help_text=N_('Optional', domain='mediacore_aws')),
                TextField('cf_streaming_domain', label_text=N_('Cloudfront Streaming Domain', domain='mediacore_aws'), help_text=N_('Optional', domain='mediacore_aws')),
            ]
        ),
    ] + StorageForm.buttons

    def display(self, value, **kwargs):
        """Display the form with default values from the engine param."""
        engine = kwargs['engine']
        data = engine._data
        defaults = {'aws': {
            'aws_access_key': data.get('aws_access_key', ''),
            'aws_secret_key': data.get('aws_secret_key', ''),
            's3_bucket_name': data.get('s3_bucket_name', ''),
            's3_bucket_dir': data.get('s3_bucket_dir', ''),
            'cf_download_domain': data.get('cf_download_domain', ''),
            'cf_streaming_domain': data.get('cf_streaming_domain', ''),
        }}
        value = merge_dicts({}, defaults, value)
        return StorageForm.display(self, value, **kwargs)

    def save_engine_params(self, engine, **kwargs):
        """Map validated field values to engine data.

        Since form widgets may be nested or named differently than the keys
        in the :attr:`mediacore.lib.storage.StorageEngine._data` dict, it is
        necessary to manually map field values to the data dictionary.

        :type engine: :class:`mediacore.lib.storage.StorageEngine` subclass
        :param engine: An instance of the storage engine implementation.
        :param \*\*kwargs: Validated and filtered form values.
        :raises formencode.Invalid: If some post-validation error is detected
            in the user input. This will trigger the same error handling
            behaviour as with the @validate decorator.

        """
        StorageForm.save_engine_params(self, engine, **kwargs)
        aws = kwargs['aws']
        data = engine._data
        data['aws_access_key'] = aws['aws_access_key']
        data['aws_secret_key'] = aws['aws_secret_key']
        data['s3_bucket_name'] = aws['s3_bucket_name']
        data['s3_bucket_dir'] = aws['s3_bucket_dir']
        data['cf_download_domain'] = aws['cf_download_domain']
        data['cf_streaming_domain'] = aws['cf_streaming_domain']
