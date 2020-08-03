# from fastapi import WebSocket
from starlette.endpoints import WebSocketEndpoint
from json import loads, dumps
from aio_pika import connect_robust, Message, IncomingMessage, ExchangeType
from config import CELERY_BROKER
from otto.getdata import timestr
from db import db
from aiofiles import open
from os.path import join

class Record(WebSocketEndpoint):
    encoding = "json"
    events = []
    async def on_connect(self, websocket, **kwargs):
        self.name = timestr()
        self.connection = await connect_robust(CELERY_BROKER[2:], reconnect_interval=2)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange('record', ExchangeType.FANOUT)
        db.recordings.insert_one({'active': True, 'name': self.name})
        await websocket.accept()

    async def on_receive(self, websocket, data):
        # print('ws data', data)
        await self.exchange.publish(Message(
            body=dumps(data).encode()
        ), routing_key='record')
        self.events.append(data)

    async def on_disconnect(self, websocket, close_code, **kwargs):
        await self.channel.close()
        db.recordings.update_one({'name': self.name}, {'$set' : {'active': False, 'close_code': close_code}})
        async with open(join('output/', f'{self.name}.session'), 'w') as f:
            await f.write(dumps({'events': self.events}))


class Watch(WebSocketEndpoint):
    encoding: "json"

    async def processMessage(self, message: IncomingMessage):
        with message.process():
            # print('message', message.body)
            await self.websocket.send_json(loads(message.body.decode()))

    async def on_connect(self, websocket, **kwargs):
        self.connection = await connect_robust(CELERY_BROKER[2:], reconnect_interval=2)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)
        self.exchange = await self.channel.declare_exchange('record', ExchangeType.FANOUT)
        self.queue = await self.channel.declare_queue(exclusive=True)
        await self.queue.bind(self.exchange)
        await websocket.accept()
        self.websocket = websocket
        await self.queue.consume(self.processMessage)

    async def on_disconnect(self, websocket, close_code, **kwargs):
        await self.channel.close()
