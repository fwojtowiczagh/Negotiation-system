# import pika 
# import json


# connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
# channel = connection.channel()

# channel.queue_declare(queue='negotiator_to_producer', durable=True)


# def callback(ch, method, properties, body):
#     data = json.loads(body)
    
#     ch.basic_ack(delivery_tag=method.delivery_tag)


# channel.basic_qos(prefetch_count=1)
# channel.basic_consume(queue='negotiator_to_producer', on_message_callback=callback)

# channel.start_consuming()