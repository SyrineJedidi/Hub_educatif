from pathlib import Path
import secrets
root=Path(__file__).resolve().parent.parent
path=root/'backend/.env'
if path.exists():
    print('backend/.env existe déjà : aucune modification.')
else:
    path.write_text('DJANGO_SECRET_KEY='+secrets.token_urlsafe(64)+'\nDJANGO_DEBUG=true\nMONGODB_DATABASE=nexora_hub\n',encoding='utf-8')
    print('backend/.env créé avec une clé locale aléatoire.')
