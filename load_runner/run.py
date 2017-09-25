from load_runner import object_model

import sys
import getopt


def main(argv):
    tests = []
    bypass = False
    res_file, output_file = None, None
    try:
        opts, _ = getopt.getopt(argv, "hlt:r:o:", ["help", "list", "tests=",
                                                   "results=", "output="])
    except getopt.GetoptError:
        print
        tests = []
        bypass = True

    if not bypass:
        for opt, arg in opts:
            if opt == '-h':
                print 'python -m load_runner.run [-l] [-t "test1 test2 testN"]'
                sys.exit()
            elif opt in ("-t", "--tests"):
                tests = arg.split(" ")
            elif opt in ('-l', '--list'):
                list_tests()
                sys.exit(0)
            elif opt in ('-r', '--results'):
                res_file = arg
            elif opt in ('-o', '--output'):
                output_file = arg

    if res_file:
        process_results(res_file, output_file)
    else:
        run_tests(tests, output_file)


def list_tests():
    print "Going to list tests"
    load_runner = object_model.LoadRunner()
    load_runner.load_description('test.yml')
    load_runner.list_tests()


def process_results(res_file, output_file):
    print "Going to process results"
    load_runner = object_model.LoadRunner()
    load_runner.load_description('test.yml')
    load_runner.process_results(res_file, output_file)


def run_tests(tests, output_file):
    print 'Going to run tests: ', tests
    load_runner = object_model.LoadRunner()
    load_runner.load_description('test.yml')
    load_runner.run_tests(tests, output_file=output_file)


if __name__ == "__main__":
    main(sys.argv[1:])
