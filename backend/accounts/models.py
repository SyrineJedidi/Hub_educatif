import secrets
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


def nonce():
    return secrets.token_urlsafe(24)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.update(role='ADMIN', is_staff=True, is_superuser=True, is_active=True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Étudiant'
        TEACHER = 'TEACHER', 'Enseignant'
        ADMIN = 'ADMIN', 'Administrateur'

    session_nonce = models.CharField(max_length=64, default=nonce)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        constraints = [models.UniqueConstraint(fields=['role'], condition=models.Q(role='ADMIN'), name='unique_admin_account')]

    def _get_session_auth_hash(self, secret=None):
        from django.utils.crypto import salted_hmac
        return salted_hmac('django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash', self.password + self.session_nonce, secret=secret, algorithm='sha256').hexdigest()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.is_staff = self.role == self.Role.ADMIN
        self.is_superuser = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)


class AdminGuard(models.Model):
    key = models.CharField(max_length=20, unique=True, default='accounts')
    revision = models.PositiveIntegerField(default=0)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    hits = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
