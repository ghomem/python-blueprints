import time
import random
from multiprocessing import Process

DELAY = 30


# this is one example function to be executed in a separate process
# it receives two example parameters p1 and p2
def worker_function(p1, p2):

    # we will pretend we are doing heavy work that takes time by sleeping :-)
    interval = random.randrange(DELAY + 1)

    print(f"Begin: {p2:10} | estimated work time: {interval:2}")
    time.sleep(interval)
    print(f"End  : {p2:10} | estimated work time: {interval:2}")

    status = random.randrange(2)

    # note that we use exit and not return because
    # we return and exit code to the parent process
    exit(status)


def main():

    print('Starting the main program')

    # DO WHATEVER STUFF NEEDS TO BE DONE HERE

    print('Starting background multiprocess work\n')

    # this is the list of functions that we want to execute in parallel
    # the list can be made of different functions or the same function
    # in every position, depending on the real world case
    worker_functions = [ worker_function, worker_function, worker_function, worker_function, worker_function ]

    # this is a list with the arguments that will be passed to each independent worker_function
    # in a real world case it would probably be made of data chunks to process
    worker_args = [ ('Worker1', 'New York'), ('Worker2', 'London'), ('Worker3', 'Sydney'), ('Worker4', 'Lisbon'), ('Worker5', 'Paris'), ]

    procs = []

    worker_ids = {}
    # instantiating the process with its arguments
    for function, arg_list in zip(worker_functions, worker_args):

        proc = Process(target=function, args=arg_list)
        proc.daemon = True
        procs.append(proc)
        proc.start()
        pid = proc.pid

        # store the relationship between the process ID and the worker id
        # we are using the second argument to identify the worker
        worker_ids[pid] = arg_list[1]

    # wait for completion - the join call only returns immediatly if the process is done
    # and waits for completion if the process is running
    # since we call it for all of them we are in the loop until all of them are done
    for proc in procs:
        proc.join()

    print('\nNow we will check the process exit codes of our processes:\n')

    # get the exit codes
    status_OK = True
    for proc in procs:
        pid = proc.pid
        exit_code = proc.exitcode
        if exit_code != 0:
            status_OK = False

        # review each processes exit code
        print(f"{worker_ids[pid]:10} returned: {exit_code}")

    # check if all processes returned 0
    if status_OK is not True:
        # in a real world situation we would want to react to this circumstance
        # with more than a simple message
        print('\nWARNING: At least one process exited with an error')

    # now we can go on with the main program execution and collect results
    # from the parallel execution

    print('')
    print('Now, business as usual. The program continues...')


main()
