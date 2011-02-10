# This file is a part of MediaCore-AWS, Copyright 2011 Simple Station Inc.

from setuptools import setup, find_packages

setup(
    name = 'MediaCore-AWS',
    version = '0.1',
    packages = find_packages(),
    author = 'Simple Station Inc.',
    author_email = 'info@simplestation.com',
    description = 'Amazon Web Services integration for MediaCore.',
    install_requires = [
        'MediaCore >= 0.9.0b3',
        'boto >= 2.0b3',
    ],
    entry_points = {
        'mediacore.plugin': ['aws = mediacore_aws'],
    },
    message_extractors = {'mediacore_aws': [
        ('**.py', 'python', None),
        ('templates/**.html', 'genshi', {'template_class': 'genshi.template.markup:MarkupTemplate'}),
        ('public/**', 'ignore', None),
        ('tests/**', 'ignore', None),
    ]},
)
