#!/usr/bin/python
#
# manually add an item to the retracing queue
# ./rabbit-readd-to-queue.py armhf 52448fc6-087f-11e4-a42f-fa163e78b027

import amqplib.client_0_8 as amqp
import sys

from daisy import config
from datetime import datetime


if config.amqp_username and config.amqp_password:
    connection = amqp.Connection(host=config.amqp_host,
                                 userid=config.amqp_username,
                                 password=config.amqp_password)
else:
    connection = amqp.Connection(host=config.amqp_host)

channel = connection.channel()

arch = sys.argv[1]
message = sys.argv[2] # uuid:storage_provider

try:
    queue = 'retrace_%s' % arch
    channel.queue_declare(queue=queue, durable=True, auto_delete=False)
    # We'll use this timestamp to measure how long it takes to process a
    # retrace, from receiving the core file to writing the data back to
    # Cassandra.
    body = amqp.Message(message, timestamp=datetime.utcnow())
    # Persistent
    body.properties['delivery_mode'] = 2
    channel.basic_publish(body, exchange='', routing_key=queue)
finally:
    channel.close()
