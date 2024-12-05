from daisy import config
import amqplib.client_0_8 as amqp
conn = amqp.Connection(host=config.amqp_host, userid=config.amqp_username,
                       password=config.amqp_password)
for q in ('failed_retrace_amd64', 'failed_retrace_armhf',
          'failed_retrace_i386', 'retrace_amd64', 'retrace_armhf',
          'retrace_i386'):
    try:
        # Exceptions invalidate the channel, apparently.
        channel = conn.channel()
        channel.queue_purge(q)
    except:
        # Queue not found.
        pass
