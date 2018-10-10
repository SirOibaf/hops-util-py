"""
Utility functions to retrieve information about available services and setting up security for the Hops platform.

These utils facilitates development by hiding complexity for programs interacting with Hops services.
"""

from hops import hdfs as hopshdfs

from hops import differential_evolution as diff_evo
from hops import grid_search as gs
from hops import launcher as launcher
from hops.distribute import allreduce as tf_allreduce
from hops.distribute import parameter_server as ps

from hops import tensorboard

from hops import util

from datetime import datetime
import atexit
import json
import pydoop.hdfs
import os
import subprocess

elastic_id = 1
app_id = None
experiment_json = None
running = False
driver_tensorboard_hdfs_path = None
run_id = 0

def get_logdir(app_id):
    """

    Args:
        app_id:

    Returns:

    """
    global run_id
    return hopshdfs.get_experiments_dir() + '/' + app_id + '/begin/run.' +  str(run_id)

def begin(name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """
    Start an experiment

    Args:
        :name:
        :local_logdir:
        :versioned_resources:
        :description:

    Returns:

    """
    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.stop() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        global run_id
        global driver_tensorboard_hdfs_path

        running = True

        sc = util._find_spark().sparkContext
        app_id = str(sc.applicationId)

        run_id = run_id + 1

        versioned_path = util.version_resources(versioned_resources, get_logdir(app_id))

        experiment_json = None

        experiment_json = util.populate_experiment(sc, name, 'experiment', 'begin', get_logdir(app_id), None, versioned_path, description)

        util.version_resources(versioned_resources, get_logdir(app_id))

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        hdfs_exec_logdir, hdfs_appid_logdir = hopshdfs.create_directories(app_id, run_id, None, 'begin')

        pydoop.hdfs.dump('', os.environ['EXEC_LOGFILE'], user=hopshdfs.project_user())

        hopshdfs.init_logger()

        driver_tensorboard_hdfs_path,_ = tensorboard.register(hdfs_exec_logdir, hdfs_appid_logdir, 0, local_logdir=local_logdir)
    except:
        exception_handler()
        raise

    return

def end(metric=None):
    """

    Args:
        metric:

    Returns:

    """
    global running
    global experiment_json
    global elastic_id
    global driver_tensorboard_hdfs_path
    global app_id
    if not running:
        raise RuntimeError("An experiment is not running. Did you forget to call experiment.end()?")
    try:
        if metric:
            experiment_json = util.finalize_experiment(experiment_json, None, str(metric))
            util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
        else:
            experiment_json = util.finalize_experiment(experiment_json, None, None)
            util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
    except:
        exception_handler()
        raise
    finally:
        elastic_id +=1
        running = False
        handle = hopshdfs.get()

        if tensorboard.tb_pid != 0:
            subprocess.Popen(["kill", str(tensorboard.tb_pid)])

        if tensorboard.local_logdir_bool:
            local_tb = tensorboard.local_logdir_path
            util.store_local_tensorboard(local_tb, tensorboard.events_logdir)

        if not tensorboard.endpoint == None and not tensorboard.endpoint == '' \
                and handle.exists(tensorboard.endpoint):
            handle.delete(tensorboard.endpoint)
        hopshdfs.kill_logger()


def launch(map_fun, args_dict=None, name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """ Run the wrapper function with each hyperparameter combination as specified by the dictionary

    Args:
      :spark_session: SparkSession object
      :map_fun: The TensorFlow function to run
      :args_dict: (optional) A dictionary containing hyperparameter values to insert as arguments for each TensorFlow job
      :name: (optional) name of the job
    """

    num_ps = util.num_param_servers()
    assert num_ps == 0, "number of parameter servers should be 0"

    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.end() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        running = True

        sc = util._find_spark().sparkContext
        app_id = str(sc.applicationId)

        launcher.run_id = launcher.run_id + 1

        versioned_path = util.version_resources(versioned_resources, launcher.get_logdir(app_id))

        experiment_json = None
        if args_dict:
            experiment_json = util.populate_experiment(sc, name, 'experiment', 'launcher', launcher.get_logdir(app_id), json.dumps(args_dict), versioned_path, description)
        else:
            experiment_json = util.populate_experiment(sc, name, 'experiment', 'launcher', launcher.get_logdir(app_id), None, versioned_path, description)

        util.version_resources(versioned_resources, launcher.get_logdir(app_id))

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        retval, tensorboard_logdir = launcher.launch(sc, map_fun, args_dict, local_logdir)

        if retval:
            experiment_json = util.finalize_experiment(experiment_json, None, retval)
            util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
            return tensorboard_logdir

        experiment_json = util.finalize_experiment(experiment_json, None, None)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

    except:
        exception_handler()
        raise
    finally:
        #cleanup spark jobs
        elastic_id +=1
        running = False
        sc.setJobGroup("", "")
    return tensorboard_logdir


def evolutionary_search(objective_function, search_dict, direction = 'max', generations=10, population=10, mutation=0.5, crossover=0.7, cleanup_generations=False, name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """
    Run the wrapper function with each hyperparameter combination as specified by the dictionary

    Args:
        objective_function:
        search_dict:
        direction:
        generations:
        population:
        mutation:
        crossover:
        cleanup_generations:
        name:
        local_logdir:
        versioned_resources:
        description:

    Returns:

    """

    num_ps = util.num_param_servers()
    assert num_ps == 0, "number of parameter servers should be 0"

    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.end() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        running = True
        spark = util._find_spark()
        sc = spark.sparkContext
        app_id = str(sc.applicationId)

        diff_evo.run_id = diff_evo.run_id + 1

        versioned_path = util.version_resources(versioned_resources, diff_evo.get_logdir(app_id))

        experiment_json = None
        experiment_json = util.populate_experiment(sc, name, 'experiment', 'evolutionary_search', diff_evo.get_logdir(app_id), json.dumps(search_dict), versioned_path, description)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        tensorboard_logdir, best_param, best_metric = diff_evo._search(spark, objective_function, search_dict, direction=direction, generations=generations, popsize=population, mutation=mutation, crossover=crossover, cleanup_generations=cleanup_generations, local_logdir=local_logdir, name=name)

        experiment_json = util.finalize_experiment(experiment_json, best_param, best_metric)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        best_param_dict = util.convert_to_dict(best_param)

    except:
        exception_handler()
        raise
    finally:
        #cleanup spark jobs
        elastic_id +=1
        running = False
        sc.setJobGroup("", "")

    return tensorboard_logdir, best_param_dict

def grid_search(map_fun, args_dict, direction='max', name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """
    Run the wrapper function with each hyperparameter combination as specified by the dictionary

    Args:
        map_fun:
        args_dict:
        direction:
        name:
        local_logdir:
        versioned_resources:
        description:

    Returns:

    """

    num_ps = util.num_param_servers()
    assert num_ps == 0, "number of parameter servers should be 0"

    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.end() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        running = True

        sc = util._find_spark().sparkContext
        app_id = str(sc.applicationId)

        gs.run_id = gs.run_id + 1

        versioned_path = util.version_resources(versioned_resources, gs.get_logdir(app_id))

        experiment_json = util.populate_experiment(sc, name, 'experiment', 'grid_search', gs.get_logdir(app_id), json.dumps(args_dict), versioned_path, description)

        util.version_resources(versioned_resources, gs.get_logdir(app_id))

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        grid_params = util.grid_params(args_dict)

        tensorboard_logdir, param, metric = gs._grid_launch(sc, map_fun, grid_params, direction=direction, local_logdir=local_logdir, name=name)

        experiment_json = util.finalize_experiment(experiment_json, param, metric)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
    except:
        exception_handler()
        raise
    finally:
        #cleanup spark jobs
        elastic_id +=1
        running = False
        sc.setJobGroup("", "")

    return tensorboard_logdir

def allreduce(map_fun, name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """
    Run the TensorFlow allreduce

    Args:
        map_fun:
        name:
        local_logdir:
        versioned_resources:
        description:

    Returns:

    """

    num_ps = util.num_param_servers()
    num_executors = util.num_executors()

    assert num_ps == 0, "number of parameter servers should be 0"
    assert num_executors > 1, "number of workers (executors) should be greater than 1"

    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.end() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        running = True

        sc = util._find_spark().sparkContext
        app_id = str(sc.applicationId)

        tf_allreduce.run_id = tf_allreduce.run_id + 1

        versioned_path = util.version_resources(versioned_resources, tf_allreduce.get_logdir(app_id))

        experiment_json = util.populate_experiment(sc, name, 'experiment', 'allreduce', tf_allreduce.get_logdir(app_id), None, versioned_path, description)

        util.version_resources(versioned_resources, tf_allreduce.get_logdir(app_id))

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        retval, logdir = tf_allreduce._launch(sc, map_fun, local_logdir=local_logdir, name=name)

        experiment_json = util.finalize_experiment(experiment_json, None, retval)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
    except:
        exception_handler()
        raise
    finally:
        #cleanup spark jobs
        elastic_id +=1
        running = False
        sc.setJobGroup("", "")

    return logdir

def parameter_server(map_fun, name='no-name', local_logdir=False, versioned_resources=None, description=None):
    """

    Args:
        map_fun:
        name:
        local_logdir:
        versioned_resources:
        description:

    Returns:

    """
    num_ps = util.num_param_servers()
    num_executors = util.num_executors()

    assert num_ps > 0, "number of parameter servers should be greater than 0"
    assert num_ps < num_executors, "number of parameter servers cannot be greater than number of executors (i.e. num_executors == num_ps + num_workers)"

    global running
    if running:
        raise RuntimeError("An experiment is currently running. Please call experiment.end() to stop it.")

    try:
        global app_id
        global experiment_json
        global elastic_id
        running = True

        sc = util._find_spark().sparkContext
        app_id = str(sc.applicationId)

        ps.run_id = ps.run_id + 1

        versioned_path = util.version_resources(versioned_resources, ps.get_logdir(app_id))

        experiment_json = util.populate_experiment(sc, name, 'experiment', 'parameter_server', ps.get_logdir(app_id), None, versioned_path, description)

        util.version_resources(versioned_resources, ps.get_logdir(app_id))

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

        retval, logdir = ps._launch(sc, map_fun, local_logdir=local_logdir, name=name)

        experiment_json = util.finalize_experiment(experiment_json, None, retval)

        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)
    except:
        exception_handler()
        raise
    finally:
        #cleanup spark jobs
        elastic_id +=1
        running = False
        sc.setJobGroup("", "")

    return logdir

def exception_handler():
    """

    Returns:

    """
    global running
    global experiment_json
    if running and experiment_json != None:
        experiment_json = json.loads(experiment_json)
        experiment_json['status'] = "FAILED"
        experiment_json['finished'] = datetime.now().isoformat()
        experiment_json = json.dumps(experiment_json)
        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

def exit_handler():
    """

    Returns:

    """
    global running
    global experiment_json
    if running and experiment_json != None:
        experiment_json = json.loads(experiment_json)
        experiment_json['status'] = "KILLED"
        experiment_json['finished'] = datetime.now().isoformat()
        experiment_json = json.dumps(experiment_json)
        util.put_elastic(hopshdfs.project_name(), app_id, elastic_id, experiment_json)

atexit.register(exit_handler)
