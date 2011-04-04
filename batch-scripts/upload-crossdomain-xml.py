#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-
from mediacore.lib.commands import LoadAppCommand, load_app

_script_name = "Crossdomain.xml upload script"
_script_description = """Helper script for uploading a permissive crossdomain.xml to the configured bucket. This is necessary for file uploads to work with flash."""
DEBUG = False

if __name__ == "__main__":
    cmd = LoadAppCommand(_script_name, _script_description)
    cmd.parser.add_option(
        '--debug',
        action='store_true',
        dest='debug',
        help='Write debug output to STDOUT.',
        default=False
    )
    load_app(cmd)
    DEBUG = cmd.options.debug

# BEGIN SCRIPT & SCRIPT SPECIFIC IMPORTS
import sys
from boto.s3 import Key
from mediacore.model.meta import DBSession
from mediacore_aws.lib.storage import AmazonS3Storage

CONENTS = """
<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM
"http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
	<allow-access-from domain="*" secure="false" />
</cross-domain-policy>
"""

def main(parser, options, args):
	for engine in DBSession.query(AmazonS3Storage):
        bucket = engine.connect_to_bucket()
        key = Key(bucket)
        key.key = 'crossdomain.xml'
        key.set_contents_from_string(CONTENTS, {'Content-Type': 'application/xml'})
        key.set_acl('public-read')

    sys.exit(0)

if __name__ == "__main__":
    main(cmd.parser, cmd.options, cmd.args)
