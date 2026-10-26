from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import AutoReconnect
root=Path(__file__).resolve().parent.parent
client=MongoClient('mongodb://127.0.0.1:27019/?directConnection=true',serverSelectionTimeoutMS=1500)
config=client.admin.command('replSetGetConfig')['config']
options=client.admin.command('getCmdLineOpts')['parsed']
actual=Path(options['storage']['dbPath']).resolve()
expected=(root/'.local/mongo').resolve()
if config['_id']!='nexora' or actual!=expected:
    raise SystemExit('Instance différente : arrêt refusé.')
try:
    client.admin.command('shutdown')
except AutoReconnect:
    print('MongoDB du projet arrêté proprement.')
