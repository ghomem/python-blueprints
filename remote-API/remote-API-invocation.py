import os
import time
import requests
import argparse
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import HTTPError
from urllib3.exceptions import MaxRetryError

# adjust to the status code that you want to receive (200, 404, 500,..)
BASE_URL = "https://httpstat.us/500?"

# use this variant to test timeouts, sleep time specified in miliseconds
# BASE_URL = "https://httpstat.us/200?sleep=8000"

# how many times a failed request is retried
NUMBER_OF_RETRIES = 3

# limit for both the connect timeout and read timeout
CLIENT_TIMEOUT = 3

# number bv which the dynamic wait interval 2**{previous retries} is multiplied
BACKOFF_FACTOR = 1

# list of status codes to retry
FORCE_RETRY_STATUS_CODE_LIST = [500, 502, 503, 504]


def main():

    # the command line arguments allow for overriding the defaults

    parser = argparse.ArgumentParser(description='Test remote API invocation')

    parser.add_argument( '-u',  '--url',            help='URL used for testing',      type=str, default=BASE_URL)
    parser.add_argument( '-nr', '--nr-retries',     help='Number of retries',         type=int, default=NUMBER_OF_RETRIES)
    parser.add_argument( '-ct', '--client-timeout', help='Client timeout in seconds', type=int, default=CLIENT_TIMEOUT)
    parser.add_argument( '-bf', '--backoff-factor', help='Backoff factor',            type=int, default=BACKOFF_FACTOR)

    # get the arguments as a dictionary
    args = parser.parse_args()

    print(f"Starting with {args.nr_retries} retries, {args.client_timeout}s of client timeout, and backoff factor {args.backoff_factor}\n")

    start_time = time.time()

    # this is the maximum time consumed in the retry + wait process
    # as the number NUMBER_OF_RETRIES increases this time converges
    # to the wall clock time because the total time becomes dominated by the wait
    # whereas the time for the call itself becomes negligible (unless the requests
    # are hanging until a timeout which is a different situation)
    #
    # the formula for calculating this is the partial sum of a geometric series of ratio 2
    max_backoff_time = args.backoff_factor * (1 - (2 ** (args.nr_retries-1)) ) / (1 - 2)

    print("Worst case time spent on backoff delays: ", max_backoff_time)

    # the maximum execution time adds to the maximum backoff time (wait between retries)
    # the worst-case scenario for time consumed performing the calls (the case where all of them timeout
    # on read after borderline timeout on the establishment of the tcp connection)
    #
    # the 2 * args.client_timeout  factor models a very slow establishment of the connection,
    # just infinitesimaly under args.client_timeout, followed by a very slow read that actually
    # times out at args.client_timeout
    max_execution_time = max_backoff_time + (args.nr_retries + 1) * (2 * args.client_timeout)

    print("Worst case execution time: ", max_execution_time)

    # generate a session for persisting the configuration of retry
    requester = requests.session()

    retries = Retry(total=args.nr_retries, backoff_factor=args.backoff_factor, status_forcelist=FORCE_RETRY_STATUS_CODE_LIST)

    requester.mount("https://", HTTPAdapter(max_retries=retries))
    requester.mount("http://",  HTTPAdapter(max_retries=retries))

    print("\nRequest to endpoint " + str(args.url))

    try:
        response = requester.get(url=args.url, timeout=args.client_timeout)
        print("Request done")
        # print(response.text)

    except (HTTPError, MaxRetryError) as err:
        # we are here because we retried as much as is configured and it still did not work
        # the following code should gracefully handle that situation
        print("There was a problem in the request to service: " + str(err))

    except Exception as err:
        print("Unexpected error: " + str(err))

    execution_time = str(f"""{time.time() - start_time:.1f}""")
    print(f"\nExecution time {execution_time}s")


main()
