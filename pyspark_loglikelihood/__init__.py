from __future__ import absolute_import
import logging

# console handler with debug verbosity
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# message formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# create logger
LOG = logging.getLogger('PySpark LogLikelihood')
LOG.setLevel(logging.DEBUG)

# attach handler to the logger
LOG.addHandler(ch)


# Import declaration
__all__ = ['LOG']

# Package version
__version__ = "1.0"
