import time
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure
client = MongoClient('mongodb://127.0.0.1:27019/?directConnection=true', serverSelectionTimeoutMS=1000)
for attempt in range(30):
    try:
        client.admin.command('ping')
        break
    except ConnectionFailure:
        time.sleep(.5)
try:
    config = client.admin.command('replSetGetConfig')['config']
    if config['_id'] != 'nexora' or config['members'][0]['host'] != '127.0.0.1:27019':
        raise SystemExit('Port 27019 occupé par une autre instance : aucune modification effectuée.')
except OperationFailure as error:
    if error.code != 94:
        raise
    client.admin.command('replSetInitiate', {'_id':'nexora','members':[{'_id':0,'host':'127.0.0.1:27019'}]})
for attempt in range(60):
    if client.admin.command('hello').get('isWritablePrimary'):
        print('MongoDB nexora prêt sur 127.0.0.1:27019')
        break
    time.sleep(.5)
else:
    raise SystemExit('Le replica set ne possède pas encore de primaire.')
