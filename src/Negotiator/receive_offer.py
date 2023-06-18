import pika
import json
from negotiator import Offer, db


url = 'your_own'
connection = pika.BlockingConnection(pika.URLParameters(url))
# connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
channel = connection.channel()
channel.exchange_declare(exchange='alerts', exchange_type='topic')
channel.exchange_declare(exchange='message', exchange_type='topic')

result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange='alerts', queue=queue_name, routing_key="#.#")  # consume


def callback(ch, method, properties, body):
    # Process the message from Queue 1
    message = body.decode('utf-8')
    data = json.loads(message)

    # if data.get("id"):
    #     in_db = Offer.query.filter_by(id=data.get("id")).first()
    # Store the message in the database
    # in_db = Offer.query.filter_by(user_id=data.get("user_id"), product_id=data.get("product_id"), producer_id=data.get("producer_id")).first()
    if data.get("offer_id"):
        in_db = Offer.query.filter_by(id=data.get("offer_id")).first()
        in_db.status = data.get("status")
        in_db.send_to = data.get("send_to")
        if data.get("price"):
            in_db.price = data.get("price")
    else:
        offer = Offer(user_id=data.get("user_id"), product_id=data.get("product_id"), producer_id=data.get("producer_id"), product_name=data.get("product_name"), price=data.get("price"), send_to=data.get("send_to"), status=data.get("status"))
        db.session.add(offer)
    db.session.commit()

    # Send a new message to Queue 
    if data.get("send_to") == "producer":
        channel.basic_publish(exchange='message', routing_key=str(data.get("send_to"))+"."+str(data.get("producer_id")), body=json.dumps(data))
    else:
        channel.basic_publish(exchange='message', routing_key=str(data.get("send_to"))+"."+str(data.get("user_id")), body=json.dumps(data))
    ch.basic_ack(delivery_tag=method.delivery_tag)


# channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=queue_name, on_message_callback=callback)

# Start consuming messages from Queue 
channel.start_consuming()
