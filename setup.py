
import os
import setuptools

def readme():
    path = os.path.dirname(__file__)
    with open(os.path.join(path, 'README.md')) as f:
        return f.read()

name = 'flask-quickstart'
description = 'Flask Quickstart'
version = '0.4.0'
author = 'Fictive Kin LLC'
email = 'hello@fictivekin.com'
classifiers = [
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Topic :: Software Development',
]

if __name__ == "__main__":
    setuptools.setup(
        name=name,
        version=version,
        description=description,
        long_description=readme(),
        classifiers=classifiers,
        url='https://github.com/fictivekin/flask-quickstart',
        author=author,
        author_email=email,
        maintainer=author,
        maintainer_email=email,
        license='MIT',
        python_requires=">=3.8",
        packages=setuptools.find_packages(),
        install_requires=[
            'boto3',
            'botocore',
            'certifi',
            'dynaconf',
            'flask',
            'pytz',
            'werkzeug',
        ],
        extras_requires={
            'sentry': ['sentry-sdk[flask]'],
            'csp': ['flask-csp'],
            'cors': ['flask-cors'],
            'full': [
                'flask-csp',
                'flask-cors',
                'sentry-sdk[flask]',
            ],
        },
        dependency_links=[
            'https://github.com/fictivekin/flask-csp.git#egg=flask-csp',
        ],
    )
