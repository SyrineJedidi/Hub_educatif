import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from accounts.models import User
from accounts.services import reset_token
from classrooms.models import LearningGroup, Enrollment
from attendance.models import LearningSession, AttendanceSheet

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   EMAIL_VERIFICATION_REQUIRED=True, CAPTCHA_ENABLED=False)
class ModuleTests(TransactionTestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@example.test', self.password, first_name='Admin', last_name='Nexora')
        self.teacher = User.objects.create_user('teacher@example.test', self.password, role='TEACHER', first_name='Prof',last_name='Un')
        self.other_teacher = User.objects.create_user('other@example.test', self.password, role='TEACHER', first_name='Prof',last_name='Deux')
        self.student = User.objects.create_user('student@example.test', self.password, first_name='Élève',last_name='Un')
        self.other_student = User.objects.create_user('student2@example.test', self.password, first_name='Élève',last_name='Deux')
        self.group = LearningGroup.objects.create(name='Informatique',code='INFO',level='L1',academic_year='2026–2027',teacher=self.teacher)
        self.other_group = LearningGroup.objects.create(name='Autre groupe',code='OTHER',level='L1',academic_year='2026–2027',teacher=self.other_teacher)
        self.now = timezone.now().replace(microsecond=0)
        self.enrollment = Enrollment.objects.create(student=self.student,group=self.group,starts_at=self.now-timedelta(days=10))
        Enrollment.objects.create(student=self.other_student,group=self.group,starts_at=self.now-timedelta(days=10))
        self.session = LearningSession.objects.create(group=self.group,title='Algorithmique',starts_at=self.now-timedelta(hours=2),ends_at=self.now-timedelta(hours=1),creator=self.teacher)
        User.objects.update(email_verified=True)  # Fixture accounts are already confirmed.
        self.client = self.as_user(self.admin)
    def confirm_email(self,email,client):
        # Opens the link of the confirmation email, like the person would.
        message=[m for m in mail.outbox if email in m.to][-1]
        token=re.search(r'verifier-email\?token=(\S+)',message.body).group(1)
        self.assertEqual(self.post('auth/email/verify/',dict(token=token),client).status_code,200)
    def as_user(self,user):
        client=APIClient();client.force_login(user);return client
    def post(self,path,data=None,client=None):
        return (client or self.client).post('/api/'+path,data or {},format='json')
    def patch(self,path,data,client=None):
        return (client or self.client).patch('/api/'+path,data,format='json')
    def enrollment_payload(self,**kw):
        return dict(student_id=str(self.student.pk),group_id=str(self.group.pk),starts_at=(self.now+timedelta(days=1)).isoformat(),**kw)
    def session_payload(self,**kw):
        data=dict(group_id=str(self.group.pk),title='Nouvelle séance',starts_at=(self.now+timedelta(days=1)).isoformat(),ends_at=(self.now+timedelta(days=1,hours=1)).isoformat())
        data.update(kw);return data
    def open_sheet(self):
        response=self.post(f'sessions/{self.session.pk}/sheet/',client=self.as_user(self.teacher))
        self.assertEqual(response.status_code,200,response.data);return response.data
    def save_sheet(self,sheet,statuses=None,**kw):
        statuses=statuses or ['PRESENT']*len(sheet['entries'])
        entries=[dict(student_id=e['student_id'],status=s,comment='') for e,s in zip(sheet['entries'],statuses)]
        data=dict(version=sheet['version'],entries=entries,validate_sheet=True);data.update(kw)
        return self.as_user(self.teacher).put(f'/api/sessions/{self.session.pk}/sheet/',data,format='json')

    def test_registration_normalization_and_session(self):
        c=APIClient();data=dict(email=' NEW@EXAMPLE.TEST ',role='STUDENT',first_name='Nouveau',last_name='Compte',password=self.password,confirmation=self.password)
        response=self.post('auth/register/',data,c);self.assertEqual(response.status_code,201,response.data)
        user=User.objects.get(email='new@example.test');self.assertEqual(user.role,'STUDENT');self.assertFalse(user.email_verified);self.assertNotEqual(user.password,self.password)
        self.assertEqual(self.post('auth/login/',dict(email=user.email,password=self.password),c).status_code,403)
        self.confirm_email(user.email,c)
        self.assertEqual(self.post('auth/login/',dict(email=user.email,password=self.password),c).status_code,200)
        self.assertEqual(c.get('/api/auth/me/').data['user']['id'],str(user.pk))
        self.assertTrue(c.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        self.assertEqual(self.post('auth/logout/',client=c).status_code,200)
        self.assertEqual(c.get('/api/auth/me/').status_code,401)
    def test_registration_invalid_duplicate_and_privilege(self):
        base=dict(email='fresh@example.test',role='STUDENT',first_name='Prénom',last_name='Nom',password=self.password,confirmation=self.password)
        for override in [dict(role='ADMIN'),dict(email='STUDENT@EXAMPLE.TEST'),dict(email='incorrect'),dict(confirmation='different'),dict(password='123',confirmation='123')]:
            response=self.post('auth/register/',dict(base,**override),APIClient());self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(User.objects.filter(email='fresh@example.test').count(),0)
    def test_csrf_on_login_register_logout(self):
        c=APIClient(enforce_csrf_checks=True)
        for path in ['auth/login/','auth/register/','auth/logout/','auth/password/reset/']:
            self.assertEqual(self.post(path,client=c).status_code,403)
        token=c.get('/api/csrf/').data['csrfToken']
        r=c.post('/api/auth/login/',dict(email=self.student.email,password=self.password),format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(c.post('/api/auth/logout/',{},format='json',HTTP_X_CSRFTOKEN=r.data['csrfToken']).status_code,200)
    def test_inactive_and_bad_credentials_generic(self):
        c=APIClient();self.student.is_active=False;self.student.save()
        responses=[self.post('auth/login/',dict(email=email,password='bad'),c) for email in ['unknown@example.test',self.student.email]]
        self.assertEqual(responses[0].data,responses[1].data);self.assertEqual(responses[0].status_code,401)
    def test_login_rate_limit(self):
        c=APIClient()
        for i in range(10):self.post('auth/login/',dict(email='x@example.test',password='bad'),c)
        self.assertEqual(self.post('auth/login/',dict(email='x@example.test',password='bad'),c).status_code,429)
    def test_reset_neutral_email_and_single_use(self):
        old=self.as_user(self.student);c=APIClient();first=self.post('auth/password/reset/',dict(email=self.student.email),c);second=self.post('auth/password/reset/',dict(email='missing@example.test'),c)
        self.assertEqual(first.data,second.data);self.assertNotIn('token',str(first.data));self.assertEqual(len(mail.outbox),1)
        token=re.search(r'token=(\S+)',mail.outbox[0].body).group(1)
        new_password=secrets.token_urlsafe(24)
        payload=dict(token=token,password=new_password,confirmation=new_password)
        self.assertEqual(self.post('auth/password/confirm/',payload,c).status_code,200)
        self.assertEqual(old.get('/api/auth/me/').status_code,401)
        self.assertEqual(self.post('auth/password/confirm/',payload,c).status_code,400)
    def test_reset_expired_and_invalid(self):
        token=reset_token(self.student)
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertEqual(self.post('auth/password/confirm/',dict(token=token,password=self.password,confirmation=self.password),APIClient()).status_code,400)
        self.assertEqual(self.post('auth/password/confirm/',dict(token='tampered',password=self.password,confirmation=self.password),APIClient()).status_code,400)
    def test_password_change_invalidates_all_sessions(self):
        c=self.as_user(self.student);other=self.as_user(self.student);new=secrets.token_urlsafe(24)
        payload=dict(old_password='bad',password=new,confirmation=new)
        self.assertEqual(self.post('auth/password/change/',payload,c).status_code,400)
        payload['old_password']=self.password
        self.assertEqual(self.post('auth/password/change/',payload,c).status_code,200)
        self.assertEqual(other.get('/api/auth/me/').status_code,401)
    def test_profile_readonly_and_admin_permissions(self):
        c=self.as_user(self.student)
        self.assertEqual(self.patch('profile/',dict(first_name='Alice',last_name='Nom'),c).status_code,200)
        self.assertEqual(self.patch('profile/',dict(role='ADMIN'),c).status_code,400)
        self.assertEqual(c.get('/api/admin/users/').status_code,403)
        self.assertEqual(self.patch(f'admin/users/{self.teacher.pk}/',dict(role='ADMIN'),c).status_code,403)
    def test_avatar_real_content_and_safe_storage(self):
        c=self.as_user(self.student)
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            fake=SimpleUploadedFile('image.svg',b'<svg onload="alert(1)"/>',content_type='image/png')
            self.assertEqual(c.post('/api/profile/avatar/',{'avatar':fake},format='multipart').status_code,400)
            image=BytesIO();Image.new('RGB',(20,20)).save(image,format='PNG')
            upload=SimpleUploadedFile('../../avatar.png',image.getvalue(),content_type='image/png')
            self.assertEqual(c.post('/api/profile/avatar/',{'avatar':upload},format='multipart').status_code,200)
            self.student.refresh_from_db();self.assertRegex(self.student.avatar.name,r'^avatars/[a-f0-9]{32}\.jpg$')
            response=c.get('/api/profile/avatar/');self.assertEqual(response.status_code,200);response.close()
            self.assertEqual(APIClient().get('/api/profile/avatar/').status_code,401)
    def test_last_admin_and_deactivation(self):
        self.assertEqual(self.patch(f'admin/users/{self.admin.pk}/',dict(is_active=False)).status_code,400)
        self.assertEqual(self.patch(f'admin/users/{self.admin.pk}/',dict(role='STUDENT')).status_code,400)
        c=self.as_user(self.student)
        self.assertEqual(self.patch(f'admin/users/{self.student.pk}/',dict(is_active=False)).status_code,200)
        self.assertEqual(c.get('/api/auth/me/').status_code,401)
        self.assertEqual(self.patch(f'admin/users/{self.student.pk}/',dict(is_active=True)).status_code,200)
        self.assertEqual(c.get('/api/auth/me/').status_code,401)
    def test_role_dependencies(self):
        for user in [self.teacher,self.student]:
            self.assertEqual(self.patch(f'admin/users/{user.pk}/',dict(role='ADMIN')).status_code,400)
        fresh=User.objects.create_user('fresh@example.test',self.password)
        self.assertEqual(self.patch(f'admin/users/{fresh.pk}/',dict(role='TEACHER')).status_code,200)
    def test_group_isolation_and_student_privacy(self):
        teacher=self.as_user(self.other_teacher);student=self.as_user(self.student)
        self.assertEqual(teacher.get(f'/api/groups/{self.group.pk}/').status_code,403)
        self.assertEqual(teacher.get(f'/api/enrollments/?group={self.group.pk}').status_code,403)
        result=student.get(f'/api/enrollments/?group={self.group.pk}').data
        self.assertEqual(len(result['results']),1);self.assertEqual(result['results'][0]['student_id'],str(self.student.pk))
        self.assertEqual(student.get(f'/api/sessions/{self.session.pk}/sheet/').status_code,403)
    def test_group_create_archive_and_delete_dependencies(self):
        data=dict(name='Nouveau',code='NEW',level='L2',academic_year='2026',teacher_id=str(self.teacher.pk))
        r=self.post('groups/',data);self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(self.post('groups/',data).status_code,400)
        self.assertEqual(self.post('groups/',dict(data,code='NO'),self.as_user(self.teacher)).status_code,403)
        self.assertEqual(self.client.delete(f'/api/groups/{self.group.pk}/').status_code,400)
        self.assertEqual(self.client.delete('/api/groups/'+r.data['id']+'/').status_code,204)
    def test_enrollment_periods_and_reenrollment(self):
        self.assertEqual(self.post('enrollments/',self.enrollment_payload()).status_code,400)
        end=self.now+timedelta(hours=1)
        self.assertEqual(self.patch(f'enrollments/{self.enrollment.pk}/',dict(ends_at=end.isoformat())).status_code,200)
        self.assertEqual(self.post('enrollments/',self.enrollment_payload()).status_code,201)
        self.assertEqual(Enrollment.objects.filter(student=self.student,group=self.group).count(),2)
        self.assertEqual(self.post('enrollments/',self.enrollment_payload()).status_code,400)
    def test_enrollment_invalid_period_and_archived(self):
        self.assertEqual(self.post('enrollments/',self.enrollment_payload(ends_at=self.now.isoformat())).status_code,400)
        self.group.archived=True;self.group.save()
        self.assertEqual(self.post('enrollments/',self.enrollment_payload()).status_code,400)
        self.assertEqual(self.post('sessions/',self.session_payload()).status_code,400)
    def test_session_dates_overlap_and_ownership(self):
        teacher=self.as_user(self.teacher)
        self.assertEqual(self.post('sessions/',self.session_payload(),teacher).status_code,201)
        self.assertEqual(self.post('sessions/',self.session_payload(),teacher).status_code,400)
        self.assertEqual(self.post('sessions/',self.session_payload(ends_at=self.now.isoformat()),teacher).status_code,400)
        self.assertEqual(self.post('sessions/',self.session_payload(),self.as_user(self.other_teacher)).status_code,403)
        self.assertEqual(self.post('sessions/',self.session_payload(),self.as_user(self.student)).status_code,403)
    def test_student_session_period_access(self):
        c=self.as_user(self.student)
        self.enrollment.starts_at=self.now;self.enrollment.save()
        self.assertEqual(c.get(f'/api/sessions/{self.session.pk}/').status_code,403)
        self.assertEqual(c.get('/api/sessions/').data['count'],0)
    def test_sheet_future_cancelled_and_permissions(self):
        for status,start in [('PLANNED',self.now+timedelta(hours=2)),('CANCELLED',self.now-timedelta(hours=2))]:
            self.session.status=status;self.session.starts_at=start;self.session.save()
            self.assertEqual(self.post(f'sessions/{self.session.pk}/sheet/',client=self.as_user(self.teacher)).status_code,400)
        self.assertEqual(self.post(f'sessions/{self.session.pk}/sheet/',client=self.as_user(self.other_teacher)).status_code,403)
    def test_draft_validation_uniqueness_and_history(self):
        sheet=self.open_sheet();self.assertEqual(len(sheet['entries']),2)
        self.assertEqual(self.save_sheet(sheet,['UNSET','PRESENT']).status_code,400)
        entries=[dict(student_id=sheet['entries'][0]['student_id'],status='PRESENT')]*2
        self.assertEqual(self.save_sheet(sheet,entries=entries).status_code,400)
        draft=self.save_sheet(sheet,['UNSET','PRESENT'],validate_sheet=False);self.assertEqual(draft.status_code,200,draft.data)
        self.assertFalse(draft.data['validated']);self.assertEqual(self.as_user(self.student).get('/api/statistics/').data['count'],0)
        validated=self.save_sheet(draft.data);self.assertEqual(validated.status_code,200,validated.data)
        self.assertTrue(validated.data['validated']);self.assertTrue(validated.data['history'])
    def test_participant_snapshot_and_destructive_session_edit(self):
        sheet=self.open_sheet();self.enrollment.ends_at=self.now-timedelta(days=5);self.enrollment.save()
        self.assertEqual(len(self.open_sheet()['entries']),2)
        payload=self.session_payload(starts_at=(self.now-timedelta(days=1)).isoformat(),ends_at=self.now.isoformat())
        self.assertEqual(self.patch(f'sessions/{self.session.pk}/',payload).status_code,400)
    def test_corrections_reason_and_version_conflict(self):
        sheet=self.open_sheet();validated=self.save_sheet(sheet);self.assertEqual(validated.status_code,200,validated.data)
        self.assertEqual(self.save_sheet(sheet).status_code,409)
        self.assertEqual(self.save_sheet(validated.data,['ABSENT','PRESENT']).status_code,400)
        corrected=self.save_sheet(validated.data,['ABSENT','PRESENT'],reason='Justificatif contrôlé')
        self.assertEqual(corrected.status_code,200,corrected.data)
        self.assertEqual(corrected.data['history'][-1]['reason'],'Justificatif contrôlé')
        self.assertEqual(self.save_sheet(corrected.data,['UNSET','PRESENT'],reason='Correction').status_code,400)
    def test_statistics_convention_privacy_and_cancelled(self):
        sheet=self.open_sheet();response=self.save_sheet(sheet,['LATE','EXCUSED']);self.assertEqual(response.status_code,200,response.data)
        stats=self.client.get('/api/statistics/').data;self.assertEqual(stats['rate'],100);self.assertEqual(stats['totals']['EXCUSED'],1)
        own=self.as_user(self.student).get('/api/statistics/').data
        self.assertEqual(own['count'],1);self.assertEqual(own['results'][0]['student_id'],str(self.student.pk))
        self.session.status='CANCELLED';self.session.save()
        self.assertIsNone(self.client.get('/api/statistics/').data['rate'])
        self.assertTrue(AttendanceSheet.objects.filter(session=self.session).exists())
    def test_statistics_excludes_unfinished(self):
        sheet=self.open_sheet();self.save_sheet(sheet)
        self.session.ends_at=self.now+timedelta(hours=1);self.session.save()
        self.assertEqual(self.client.get('/api/statistics/').data['count'],0)
    def test_export_authorization_and_csv_formula(self):
        self.student.first_name='=HYPERLINK(1)';self.student.save();self.save_sheet(self.open_sheet())
        self.assertEqual(self.as_user(self.student).get('/api/statistics/export/').status_code,403)
        self.assertEqual(self.as_user(self.other_teacher).get(f'/api/statistics/export/?group={self.group.pk}').status_code,403)
        response=self.as_user(self.teacher).get('/api/statistics/export/')
        self.assertEqual(response.status_code,200);self.assertIn("'=HYPERLINK(1)",response.content.decode('utf-8'))
    def test_concurrent_overlapping_sessions(self):
        from accounts.models import AdminGuard
        AdminGuard.objects.get_or_create(key='accounts')
        clients=[self.as_user(self.teacher),self.as_user(self.teacher)]
        payload=self.session_payload()
        def create(c):
            try:return c.post('/api/sessions/',payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(create,clients))
        self.assertEqual(results.count(201),1,results)
        self.assertIn(next(code for code in results if code!=201),[400,409])
    def test_full_scenario(self):
        c=APIClient();new=secrets.token_urlsafe(24)
        self.assertEqual(self.post('auth/register/',dict(email='scenario@example.test',role='STUDENT',first_name='Scénario',last_name='Élève',password=new,confirmation=new),c).status_code,201)
        self.confirm_email('scenario@example.test',c)
        self.assertEqual(self.post('auth/login/',dict(email='scenario@example.test',password=new),c).status_code,200)
        new_user=User.objects.get(email='scenario@example.test')
        future_teacher=User.objects.create_user('future@example.test',self.password)
        self.assertEqual(self.patch(f'admin/users/{future_teacher.pk}/',dict(role='TEACHER')).status_code,200)
        group=self.post('groups/',dict(name='Scénario',code='SCENARIO',level='L1',academic_year='2026',teacher_id=str(future_teacher.pk))).data
        self.assertEqual(self.post('enrollments/',dict(group_id=group['id'],student_id=str(new_user.pk),starts_at=(self.now-timedelta(days=1)).isoformat())).status_code,201)
        future_teacher.refresh_from_db();teacher=self.as_user(future_teacher)
        session=self.post('sessions/',self.session_payload(group_id=group['id'],starts_at=(self.now-timedelta(minutes=20)).isoformat(),ends_at=(self.now-timedelta(minutes=10)).isoformat()),teacher)
        self.assertEqual(session.status_code,201,session.data)
        path=f"sessions/{session.data['id']}/sheet/"
        sheet=self.post(path,client=teacher).data
        r=teacher.put('/api/'+path,dict(version=0,entries=[dict(student_id=str(new_user.pk),status='PRESENT')],validate_sheet=True),format='json')
        self.assertEqual(r.status_code,200,r.data);self.assertEqual(c.get('/api/statistics/').data['count'],1)
        self.assertEqual(self.client.get('/api/statistics/').data['totals']['PRESENT'],1)
        self.assertEqual(c.get('/api/admin/users/').status_code,403)

    def test_two_simultaneous_sheet_edits_cannot_overwrite(self):
        from accounts.models import AdminGuard
        sheet=self.open_sheet()
        clients=[self.as_user(self.teacher), self.as_user(self.teacher)]
        def save(item):
            client,status=item
            payload=dict(version=sheet['version'],validate_sheet=True,entries=[dict(student_id=e['student_id'],status=status) for e in sheet['entries']])
            try:return client.put(f'/api/sessions/{self.session.pk}/sheet/',payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(save,zip(clients,['PRESENT','ABSENT'])))
        self.assertEqual(sorted(results),[200,409])
        saved=AttendanceSheet.objects.get(session=self.session)
        self.assertEqual(saved.version,1)
        self.assertEqual(len({e.status for e in saved.entries}),1)

    def test_concurrent_enrollments_are_unique(self):
        from accounts.models import AdminGuard
        AdminGuard.objects.get_or_create(key='accounts')
        fresh=User.objects.create_user('concurrent@example.test',self.password)
        clients=[self.as_user(self.admin),self.as_user(self.admin)]
        payload=self.enrollment_payload();payload['student_id']=str(fresh.pk)
        def create(client):
            try:return client.post('/api/enrollments/',payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(create,clients))
        self.assertEqual(results.count(201),1,results)
        self.assertEqual(Enrollment.objects.filter(student=fresh,group=self.group).count(),1)

    def test_concurrent_second_admin_creation_is_refused(self):
        from django.db import IntegrityError
        def create(email):
            try:
                User.objects.create_superuser(email,self.password)
                return 'created'
            except IntegrityError:
                return 'refused'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(create,['admin2@example.test','admin3@example.test']))
        self.assertEqual(results,['refused','refused'])
        self.assertEqual(User.objects.filter(role='ADMIN').count(),1)

    def test_historical_student_statistics_survive_period_edits(self):
        self.save_sheet(self.open_sheet())
        self.enrollment.ends_at=self.now-timedelta(days=5)
        self.enrollment.save()
        stats=self.as_user(self.student).get('/api/statistics/').data
        self.assertEqual(stats['count'],1)
        self.assertEqual(stats['rate'],100)

    def test_reset_request_throttle(self):
        c=APIClient()
        for _ in range(3):self.post('auth/password/reset/',{'email':self.student.email},c)
        self.assertEqual(self.post('auth/password/reset/',{'email':self.student.email},c).status_code,429)

    def test_api_validation_and_paginated_filters(self):
        self.assertEqual(self.client.get('/api/admin/users/?role=TEACHER&active=true&q=Prof').data['count'],2)
        self.assertEqual(self.client.get('/api/groups/?q=INFO').data['count'],1)
        for path in ['groups/?page=bad','enrollments/?page=bad','sessions/?page=bad','statistics/?page=bad','sessions/?from=bad']:
            self.assertEqual(self.client.get('/api/'+path).status_code,400,path)
        self.assertEqual(self.client.get('/api/groups/invalid-id/').status_code,404)

    def test_role_change_after_ending_dependencies_preserves_history(self):
        self.enrollment.ends_at=self.now-timedelta(hours=1)
        self.enrollment.save()
        response=self.patch(f'admin/users/{self.student.pk}/',dict(role='TEACHER'))
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_registration_teacher_role_and_permissions(self):
        c=APIClient()
        payload=dict(email='newteacher@example.test',first_name='Nouvel',last_name='Enseignant',role='TEACHER',password=self.password,confirmation=self.password)
        response=self.post('auth/register/',payload,c)
        self.assertEqual(response.status_code,201,response.data)
        teacher=User.objects.get(email=payload['email'])
        self.assertEqual(teacher.role,'TEACHER')
        self.assertFalse(teacher.is_staff);self.assertFalse(teacher.is_superuser)
        self.confirm_email(teacher.email,c)
        response=self.post('auth/login/',dict(email=teacher.email,password=self.password),c)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['user']['role'],'TEACHER')
        self.assertEqual(c.get('/api/admin/users/').status_code,403)
        self.assertEqual(c.get(f'/api/groups/{self.group.pk}/').status_code,403)

    def test_registration_requires_valid_public_role(self):
        payload=dict(email='choose@example.test',first_name='Choix',last_name='Role',password=self.password,confirmation=self.password)
        for role in [None,'','ADMIN','SUPERUSER','teacher']:
            data=dict(payload)
            if role is not None:data['role']=role
            response=self.post('auth/register/',data,APIClient())
            self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(User.objects.filter(email=payload['email']).exists())

    def test_admin_cannot_promote_a_second_admin(self):
        fresh=User.objects.create_user('another@example.test',self.password)
        response=self.patch(f'admin/users/{fresh.pk}/',dict(role='ADMIN'))
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(User.objects.filter(role='ADMIN').count(),1)
        fresh.refresh_from_db();self.assertEqual(fresh.role,'STUDENT')

    def test_single_admin_command_refuses_before_password_prompt(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with patch('accounts.management.commands.create_admin.getpass') as prompt:
            with self.assertRaises(CommandError):
                call_command('create_admin',email='second@example.test',first_name='Second',last_name='Admin')
        prompt.assert_not_called()

    def test_database_refuses_direct_second_admin_promotion(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.filter(pk=self.teacher.pk).update(role='ADMIN')
        self.assertEqual(User.objects.filter(role='ADMIN').count(),1)
