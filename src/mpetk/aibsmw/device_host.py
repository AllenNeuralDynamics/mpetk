#!/usr/bin/env python
# -*- coding: utf-8 -*-
import aibsmw
import logging
import mpeconfig

def rdm_handler(message_id, message, timestamp):
    print(message)


def main(args=None):
    mpeconfig.source_configuration('aibsmw')
    logging.info('Starting {}'.format(aibsmw))

    io = aibsmw.ZMQHandler(aibsmw.messages)
    io.register_for_message('generic_heartbeat', rdm_handler)


    io.start()


if __name__ == "__main__":
    main()
