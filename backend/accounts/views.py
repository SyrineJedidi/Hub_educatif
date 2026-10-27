from pathlib import Path
from smtplib import SMTPException
from bson import ObjectId
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, DatabaseError
from django.db.models import Q, F
from django.http import FileResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_mongodb_backend import transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound, AuthenticationFailed, APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, AdminGuard, nonce
from .permissions import Administrator
from .serializers import (
    RegistrationSerializer, LoginSerializer, EmailSerializer, LinkSerializer,
    ResetSerializer, ChangePasswordSerializer, ProfileSerializer, AvatarSerializer,
    AdminUpdateSerializer, user_data,
)
from .captcha import ACTIONS, captcha_enabled, create_challenge, verify_captcha
from .services import limit, send_link, send_verification, VERIFY_MAX_AGE, VERIFY_SALT


def validated(cls, request, **context):
    serializer = cls(data=request.data, context=context)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def find_user(uid):
    if not ObjectId.is_valid(uid):
        raise NotFound('Compte introuvable.')
    try:
        return User.objects.get(pk=ObjectId(uid))
    except User.DoesNotExist:
        raise NotFound('Compte introuvable.')


@method_decorator(csrf_protect, name='dispatch')
class SecureView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class PublicView(SecureView):
    permission_classes = [AllowAny]


class CSRFView(PublicView):
    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class RegisterView(PublicView):
    def post(self, request):
        limit(request, 'register', maximum=10, seconds=3600)
        data = validated(RegistrationSerializer, request)
        verify_captcha(request, 'register')
        data.pop('confirmation')
        try:
            user = User.objects.create_user(**data)
        except IntegrityError:
            raise ValidationError({'email': ['Cette adresse email est déjà utilisée.']})
        if not settings.EMAIL_VERIFICATION_REQUIRED:
            User.objects.filter(pk=user.pk).update(email_verified=True)
            return Response({'message': 'Compte créé. Vous pouvez vous connecter.', 'verification': False}, status=201)
        try:
            send_verification(user)
        except (OSError, SMTPException):
            # The account exists: the person can ask for a new link from the login page.
            pass
        return Response({'message': f'Compte créé. Un email de confirmation a été envoyé à {user.email} : ouvrez le lien qu’il contient pour activer votre compte.',
                         'verification': True}, status=201)


class EmailRequestView(PublicView):
    kind = 'reset'

    def post(self, request):
        limit(request, 'email-ip', maximum=10, seconds=3600)
        email = validated(EmailSerializer, request)['email']
        verify_captcha(request, self.kind)
        limit(request, 'email-account', maximum=3, seconds=3600, identity=f'{self.kind}:{email}')
        user = self.recipient(email)
        if user:
            try:
                send_link(user, self.kind)
            except (OSError, SMTPException):
                # Keep the same response and allow a later retry. Never log the link.
                pass
        return Response({'message': 'Si un compte correspond à cette adresse, un email vous sera envoyé. Vous pourrez réessayer plus tard si nécessaire.'})


    def recipient(self, email):
        return User.objects.filter(email=email, is_active=True).first()


class ResetRequestView(EmailRequestView):
    kind = 'reset'


class ResendVerificationView(EmailRequestView):
    kind = 'verify'

    def recipient(self, email):
        return User.objects.filter(email=email, is_active=True, email_verified=False).first()


class VerifyEmailView(PublicView):
    def post(self, request):
        limit(request, 'verify-email', maximum=20, seconds=3600)
        data = validated(LinkSerializer, request)
        try:
            payload = signing.loads(data['token'], salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
        except signing.SignatureExpired:
            raise ValidationError({'token': ['Ce lien a expiré. Demandez un nouvel email de confirmation depuis la page de connexion.']})
        except signing.BadSignature:
            raise ValidationError({'token': ['Lien de confirmation invalide.']})
        uid = payload.get('uid', '')
        user = User.objects.filter(pk=uid if ObjectId.is_valid(uid) else None, email=payload.get('email'), is_active=True).first()
        if not user:
            raise ValidationError({'token': ['Lien de confirmation invalide.']})
        User.objects.filter(pk=user.pk).update(email_verified=True)
        return Response({'message': 'Adresse confirmée. Vous pouvez vous connecter.'})


class AuthConfigView(PublicView):
    """Public settings of the account forms."""
    def get(self, request):
        return Response({'captcha': {'enabled': captcha_enabled(), 'provider': 'altcha'},
                         'email_verification': settings.EMAIL_VERIFICATION_REQUIRED})


class CaptchaChallengeView(PublicView):
    """A new signed ALTCHA challenge for one account form."""
    def get(self, request):
        action = request.query_params.get('action', '')
        if action not in ACTIONS: raise ValidationError({'action': ['Formulaire inconnu.']})
        limit(request, 'captcha-challenge', maximum=120, seconds=600)
        return Response(create_challenge(action))  # Never cached: the API middleware sends no-store.


class EmailNotVerified(APIException):
    status_code = 403
    default_code = 'email_not_verified'
    default_detail = 'Confirmez d’abord votre adresse email : ouvrez le lien reçu après l’inscription, ou demandez un nouvel email.'


class LoginView(PublicView):
    def post(self, request):
        limit(request, 'login-ip', maximum=20)
        data = validated(LoginSerializer, request)
        verify_captcha(request, 'login')
        limit(request, 'login-account', maximum=10, identity=data['email'])
        user = authenticate(request, username=data['email'], password=data['password'])
        if not user:
            raise AuthenticationFailed('Email ou mot de passe incorrect.')
        # Checked after the password, so the answer never reveals whether an address has an account.
        if settings.EMAIL_VERIFICATION_REQUIRED and not user.email_verified:
            raise EmailNotVerified()
        login(request, user)
        return Response({'user': user_data(user), 'csrfToken': get_token(request)})


class LogoutView(SecureView):
    def post(self, request):
        logout(request)
        return Response({'message': 'Vous êtes déconnecté.'})


class MeView(SecureView):
    def get(self, request):
        return Response({'user': user_data(request.user)})


class ResetConfirmView(PublicView):
    def post(self, request):
        limit(request, 'reset-confirm', maximum=20)
        data = validated(ResetSerializer, request)
        try:
            payload = signing.loads(data['token'], salt='reset-password', max_age=settings.PASSWORD_RESET_TIMEOUT)
            user = find_user(payload['uid'])
        except (signing.BadSignature, KeyError, ValueError, NotFound):
            raise ValidationError({'token': ['Lien invalide ou expiré.']})
        if not user.is_active or not default_token_generator.check_token(user, payload['value']):
            raise ValidationError({'token': ['Lien invalide, expiré ou déjà utilisé.']})
        validated(ResetSerializer, request, user=user)
        # Compare and swap prevents concurrent consumption of the same link.
        changed = User.objects.filter(pk=user.pk, password=user.password, is_active=True).update(password=make_password(data['password']))
        if not changed:
            raise ValidationError({'token': ['Lien déjà utilisé.']})
        logout(request)
        return Response({'message': 'Mot de passe réinitialisé. Reconnectez-vous.'})


class ProfileView(SecureView):
    def get(self, request):
        return Response({'user': user_data(request.user)})

    def patch(self, request):
        data = validated(ProfileSerializer, request)
        User.objects.filter(pk=request.user.pk, is_active=True).update(**data)
        request.user.refresh_from_db()
        return Response({'user': user_data(request.user)})


class AvatarView(SecureView):
    def get(self, request):
        if not request.user.avatar:
            raise NotFound('Aucun avatar.')
        response = FileResponse(request.user.avatar.open('rb'), content_type='image/jpeg')
        response['Cache-Control'] = 'private, no-store'
        return response

    def post(self, request):
        data = validated(AvatarSerializer, request)
        old = request.user.avatar.name
        request.user.avatar = data['avatar']
        request.user.save(update_fields=['avatar'])
        if old:
            request.user.avatar.storage.delete(old)
        return Response({'user': user_data(request.user)})

    def delete(self, request):
        request.user.avatar.delete(save=False)
        request.user.save(update_fields=['avatar'])
        return Response({'user': user_data(request.user)})


class ChangePasswordView(SecureView):
    def post(self, request):
        limit(request, 'change-password', maximum=10)
        data = validated(ChangePasswordSerializer, request, user=request.user)
        if not request.user.check_password(data['old_password']):
            raise ValidationError({'old_password': ['Ancien mot de passe incorrect.']})
        changed = User.objects.filter(pk=request.user.pk, password=request.user.password).update(password=make_password(data['password']))
        if not changed:
            raise ValidationError({'old_password': ['Votre mot de passe a changé. Reconnectez-vous.']})
        logout(request)
        return Response({'message': 'Mot de passe modifié. Reconnectez-vous.'})


class UsersView(SecureView):
    permission_classes = [Administrator]

    def get(self, request):
        users = User.objects.all().order_by('date_joined', 'id')
        query = request.query_params.get('q', '')[:100]
        if query:
            users = users.filter(Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        role = request.query_params.get('role')
        if role in User.Role.values:
            users = users.filter(role=role)
        active = request.query_params.get('active')
        if active in ('true', 'false'):
            users = users.filter(is_active=active == 'true')
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise ValidationError({'page': ['Numéro de page invalide.']})
        return Response({'count': users.count(), 'page': page, 'page_size': 20, 'results': [user_data(u) for u in users[(page - 1) * 20:page * 20]]})


class UserDetailView(SecureView):
    permission_classes = [Administrator]

    def get(self, request, uid):
        return Response({'user': user_data(find_user(uid))})

    def patch(self, request, uid):
        data = validated(AdminUpdateSerializer, request)
        AdminGuard.objects.get_or_create(key='accounts')
        # Every admin update writes the same guard document. MongoDB detects
        # concurrent writers and aborts one transaction, preventing write skew.
        for attempt in range(3):
            try:
                with transaction.atomic():
                    AdminGuard.objects.filter(key='accounts').update(revision=F('revision') + 1)
                    actor = User.objects.get(pk=request.user.pk)
                    if not actor.is_active or actor.role != 'ADMIN':
                        from rest_framework.exceptions import PermissionDenied
                        raise PermissionDenied('Vos droits ont changé. Reconnectez-vous.')
                    user = find_user(uid)
                    if data.get('role') == 'ADMIN' and user.role != 'ADMIN':
                        raise ValidationError({'role': ['Le compte administrateur est unique. Ce rôle ne peut pas être attribué à un autre compte.']})
                    removing = data.get('role', user.role) != 'ADMIN' or not data.get('is_active', user.is_active)
                    if user.role == 'ADMIN' and user.is_active and removing and User.objects.filter(role='ADMIN', is_active=True).count() <= 1:
                        raise ValidationError({'detail': 'Le dernier administrateur actif doit être conservé.'})
                    if data.get('role', user.role) != user.role:
                        from classrooms.models import LearningGroup, Enrollment
                        from django.utils import timezone
                        if LearningGroup.objects.filter(teacher=user, archived=False).exists() or Enrollment.objects.filter(student=user).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=timezone.now())).exists():
                            raise ValidationError({'role': ['Réaffectez ou archivez les groupes enseignés et terminez les périodes d’inscription en cours ou futures avant de changer ce rôle. L’historique sera conservé.']})
                        from courses.models import Course
                        if Course.objects.filter(teacher=user).exclude(status='ARCHIVED').exists():
                            raise ValidationError({'role': ['Archivez les cours de cet enseignant ou confiez-les à un autre enseignant avant de changer son rôle.']})
                    user.session_nonce = nonce()
                    for key, value in data.items():
                        setattr(user, key, value)
                    user.save()
                return Response({'user': user_data(user)})
            except DatabaseError:
                if attempt == 2:
                    error = APIException('Modification concurrente ou base indisponible. Réessayez.')
                    error.status_code = status.HTTP_409_CONFLICT
                    raise error
