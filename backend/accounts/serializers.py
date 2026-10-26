from io import BytesIO
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import User


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: ['Ce champ ne peut pas être modifié.'] for key in unknown})
        return super().to_internal_value(data)


class EmailSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class PasswordSerializer(StrictSerializer):
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    confirmation = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['confirmation']:
            raise serializers.ValidationError({'confirmation': ['Les mots de passe ne correspondent pas.']})
        user = self.context.get('user') or User(email=attrs.get('email', ''), first_name=attrs.get('first_name', ''), last_name=attrs.get('last_name', ''))
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs


class RegistrationSerializer(PasswordSerializer, EmailSerializer):
    role = serializers.ChoiceField(choices=[(User.Role.STUDENT, 'Étudiant'), (User.Role.TEACHER, 'Enseignant')])
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)


class LoginSerializer(EmailSerializer):
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class LinkSerializer(StrictSerializer):
    token = serializers.CharField(max_length=1024)


class ResetSerializer(PasswordSerializer):
    token = serializers.CharField(max_length=1024)


class ChangePasswordSerializer(PasswordSerializer):
    old_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class ProfileSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)


class AvatarSerializer(StrictSerializer):
    avatar = serializers.FileField()

    def validate_avatar(self, upload):
        if upload.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('La taille maximale est de 2 Mo.')
        try:
            with Image.open(upload) as img:
                if img.format not in ('PNG', 'JPEG', 'WEBP') or img.width * img.height > 16_000_000:
                    raise ValueError()
                img.verify()
            upload.seek(0)
            with Image.open(upload) as img:
                img.thumbnail((512, 512))
                output = BytesIO()
                img.convert('RGB').save(output, format='JPEG', quality=85)
            return ContentFile(output.getvalue(), name=f'{uuid4().hex}.jpg')
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise serializers.ValidationError('Choisissez une image PNG, JPEG ou WebP valide (16 mégapixels maximum).')


class AdminUpdateSerializer(StrictSerializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)


def user_data(user):
    return {
        'id': str(user.pk), 'email': user.email, 'first_name': user.first_name,
        'last_name': user.last_name, 'role': user.role, 'is_active': user.is_active,
        'email_verified': user.email_verified, 'date_joined': user.date_joined,
        'last_login': user.last_login,
        'avatar': '/api/profile/avatar/' if user.avatar else None,
    }
