from getpass import getpass
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User
from django.db import IntegrityError

class Command(BaseCommand):
    help = 'Créer le premier administrateur (mot de passe saisi de manière masquée).'
    def add_arguments(self, parser):
        parser.add_argument('--email',required=True)
        parser.add_argument('--first-name',required=True)
        parser.add_argument('--last-name',required=True)
    def handle(self,*args,**options):
        from django.core.validators import validate_email
        if User.objects.filter(role='ADMIN').exists():
            raise CommandError('Le compte administrateur existe déjà ; aucun second compte ne peut être créé.')
        email=options['email'].strip().lower()
        try:validate_email(email)
        except ValidationError as exc:raise CommandError(str(exc))
        if User.objects.filter(email=email).exists():raise CommandError('Ce compte existe déjà ; aucune modification effectuée.')
        password=getpass('Mot de passe : ')
        if password!=getpass('Confirmation : '):raise CommandError('Les mots de passe diffèrent.')
        user=User(email=email,first_name=options['first_name'],last_name=options['last_name'])
        try:validate_password(password,user)
        except ValidationError as exc:raise CommandError(str(exc))
        try:
            User.objects.create_superuser(email,password,first_name=user.first_name,last_name=user.last_name)
        except IntegrityError:
            raise CommandError('Un administrateur ou un compte avec cet email vient d’être créé. Aucun compte supplémentaire créé.')
        self.stdout.write(self.style.SUCCESS('Administrateur créé.'))
