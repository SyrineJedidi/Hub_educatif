import json
import secrets
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User

class Command(BaseCommand):
    help = 'Créer des comptes navigateur isolés sans écraser les données ; réutiliser l’administrateur unique.'
    def handle(self,*args,**options):
        database=settings.DATABASES['default']['NAME']
        if database not in {'test_nexora_browser_isolated','test_nexora_roles_browser_isolated'}:
            raise CommandError('Utilisez une configuration de test navigateur isolée.')
        root=settings.BASE_DIR.parent/'.local'
        root.mkdir(exist_ok=True)
        credential_file=root/f'{database}-admin.json'
        admins=User.objects.filter(role='ADMIN')
        if admins.count()>1:
            raise CommandError('Cette ancienne base possède plusieurs administrateurs. Utilisez --settings=config.roles_e2e_settings ; aucune donnée existante modifiée.')
        admin=admins.first()
        if admin:
            if not credential_file.exists():
                raise CommandError('Administrateur existant sans identifiants de fixture connus. Aucune modification de son compte.')
            saved=json.loads(credential_file.read_text(encoding='utf-8'))
            password=saved['password']
            if saved['email']!=admin.email or not admin.is_active or not admin.check_password(password):
                raise CommandError('Les identifiants de fixture ne correspondent plus à l’administrateur. Aucune modification effectuée.')
        else:
            password=secrets.token_urlsafe(24)
            admin=User.objects.create_superuser(f'admin-{secrets.token_hex(6)}@example.test',password,first_name='Admin',last_name='Navigateur')
            credential_file.write_text(json.dumps({'email':admin.email,'password':password}),encoding='utf-8')
        run=secrets.token_hex(6)
        data={'run':run,'password':password,'admin':admin.email}
        for key,role in [('teacher','STUDENT'),('outsider','TEACHER'),('other_student','STUDENT')]:
            email=f'{key}-{run}@example.test'
            User.objects.create_user(email,password,role=role,first_name=key.title(),last_name=run)
            data[key]=email
        data['student']=f'student-{run}@example.test'
        (root/'browser.json').write_text(json.dumps(data),encoding='utf-8')
        self.stdout.write('Fixtures créées ; administrateur unique réutilisable ; identifiants aléatoires dans .local (ignoré par Git).')
