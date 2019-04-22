from setuptools import setup
from codecs import open

# Retrieve dependencies
with open('requirements.txt', 'r') as f:
    reqs = f.readlines()

# Retrieve readme
with open('README.md', 'r') as f:
    long_desc = f.read()

setup(
    name='dpu',
    description='Data Processing Unit for eVOLVER.',
    long_description=long_desc,
    author='Fynch Biosciencese',
    author_email='brandon@fynchbio.com',
    install_requires=reqs,
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
        'Topic :: Utilities',
    ),
)
