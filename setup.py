# -*- coding:utf-8 -*-
from setuptools import setup, find_packages
import os
import re

with open(os.path.join("DrissionPage", "__init__.py"), "r", encoding="utf-8") as f:
    version_match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE)
    if version_match:
        __version__ = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string.")

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name="DrissionPage",
    version=__version__,
    author="g1879",
    author_email="g1879@qq.com",
    description="Python based web automation tool. It can control the browser and send and receive data packets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # license="BSD",
    keywords="DrissionPage",
    url="https://DrissionPage.cn",
    include_package_data=True,
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        'lxml',
        'requests',
        'cssselect',
        'DownloadKit>=2.0.7',
        'websocket-client',
        'click',
        'tldextract>=3.4.4',
        'psutil'
    ],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        # "License :: OSI Approved :: BSD License",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'dp = DrissionPage._functions.cli:main',
        ],
    },
)
