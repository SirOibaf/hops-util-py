"""
Utility functions to retrieve information about available services and setting up security for the Hops platform.

These utils facilitates development by hiding complexity for programs interacting with Hops services.
"""

import os
import signal
from ctypes import cdll
import itertools
import socket

def _find_in_path(path, file):
    """Find a file in a given path string."""
    for p in path.split(os.pathsep):
        candidate = os.path.join(p, file)
        if (os.path.exists(os.path.join(p, file))):
            return candidate
    return False

def find_tensorboard():
    pypath = os.getenv("PYSPARK_PYTHON")
    pydir = os.path.dirname(pypath)
    search_path = os.pathsep.join([pydir, os.environ['PATH'], os.environ['PYTHONPATH']])
    tb_path = _find_in_path(search_path, 'tensorboard')
    if not tb_path:
        raise Exception("Unable to find 'tensorboard' in: {}".format(search_path))
    return tb_path

def on_executor_exit(signame):
    """
    Return a function to be run in a child process which will trigger
    SIGNAME to be sent when the parent process dies
    """
    signum = getattr(signal, signame)
    def set_parent_exit_signal():
        # http://linux.die.net/man/2/prctl

        PR_SET_PDEATHSIG = 1
        result = cdll['libc.so.6'].prctl(PR_SET_PDEATHSIG, signum)
        if result != 0:
            raise Exception('prctl failed with error code %s' % result)
    return set_parent_exit_signal

def num_executors(spark):
    """ Get the number of executors configured for Jupyter
    Returns:
      Number of configured executors for Jupyter
    """
    sc = spark.sparkContext
    return int(sc._conf.get("spark.executor.instances"))

def num_param_servers(spark):
    """ Get the number of parameter servers configured for Jupyter
    Returns:
      Number of configured parameter servers for Jupyter
    """
    sc = spark.sparkContext
    return int(sc._conf.get("spark.tensorflow.num.ps"))

def csv_to_args(path):
    print("TODO")

def grid_params(dict):
    """ Generate all possible combinations (cartesian product) of the hyperparameter values
    Returns:
      A new dictionary with a grid of all the possible hyperparameter combinations
    """
    keys = dict.keys()
    val_arr = []
    for key in keys:
        val_arr.append(dict[key])

    permutations = list(itertools.product(*val_arr))

    args_dict = {}
    slice_index = 0
    for key in keys:
        args_arr = []
        for val in list(zip(*permutations))[slice_index]:
            args_arr.append(val)
        slice_index += 1
        args_dict[key] = args_arr
    return args_dict

def get_ip_address():
    """Simple utility to get host IP address"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]



