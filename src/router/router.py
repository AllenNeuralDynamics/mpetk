#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys

import aibsmw
import argparse
import mpeconfig


def main():
    parser = argparse.ArgumentParser(description="router pub-sub hub for aibsmw.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     )
    parser.add_argument('-v', '--version', action='version', version=aibsmw.__version__)
    parser.add_argument('-p', '--port', type=int, help='port to bind on (you probably do not need this.')
    args = parser.parse_args(sys.argv[1:])

    mpeconfig.source_configuration('aibsmw', send_start_log=False)
    logging.info('Starting {}'.format(aibsmw))

    if 'port' in args:
        router = aibsmw.Router(port=args.port)
    else:
        router = aibsmw.Router()
    router.start()


if __name__ == "__main__":
    main()
