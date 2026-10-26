from pathlib import Path
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from accounts.models import User
from classrooms.models import Enrollment
from .models import Attempt, Answer
from .attempt_services import attempt_percentage
from .result_views import reported_attempt, ReadOnlyResultsView
from .services import managed_quiz


def grade_rows(quiz):
    now = timezone.now()
    current = set(Enrollment.objects.filter(group_id=quiz.learning_group_id, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('student_id', flat=True))
    attempts = list(Attempt.objects.filter(quiz=quiz))
    due = [a.pk for a in attempts if a.status == 'IN_PROGRESS' and a.deadline and now >= a.deadline]
    answers = {}
    for answer in Answer.objects.filter(attempt_id__in=due):
        answers.setdefault(answer.attempt_id, {})[str(answer.question_id)] = answer
    by_student = {}
    for attempt in attempts:
        by_student.setdefault(attempt.student_id, []).append(reported_attempt(attempt, now, answers.get(attempt.pk, {})))
    users = {u.pk: u for u in User.objects.filter(pk__in=current | set(by_student))}
    sections = {'current': [], 'former': []}
    for uid in current | set(by_student):
        user = users.get(uid)
        finished = [a for a in by_student.get(uid, []) if a.status in ('SUBMITTED', 'EXPIRED')]
        graded = [a for a in finished if a.points_earned is not None and a.total_points > 0]
        best = max(graded, key=lambda a: (attempt_percentage(a), a.ended_at or a.started_at, str(a.pk))) if graded else None
        ongoing = any(a.status == 'IN_PROGRESS' for a in by_student.get(uid, []))
        row = {'student_id': str(uid), 'name': f'{user.last_name} {user.first_name}'.strip() if user else 'Compte indisponible',
               'status': best.status if best else 'FINISHED_UNGRADED' if finished else 'IN_PROGRESS' if ongoing else 'NOT_STARTED',
               'completed_attempts': len(finished), 'points': best.points_earned if best else None,
               'total': best.total_points if best else None, 'percentage': attempt_percentage(best) if best else None}
        sections['current' if uid in current else 'former'].append(row)
    for rows in sections.values(): rows.sort(key=lambda row: (row['name'].casefold(), row['student_id']))
    return sections


LABELS = {
    'fr': {'title':'Notes du quiz', 'group':'Groupe', 'teacher':'Enseignant', 'export':'Exporté le',
           'rule':'Règle : meilleur pourcentage parmi les tentatives soumises ou expirées corrigées. Les non-participants ne reçoivent pas une note de zéro.',
           'current':'Inscrits actuels', 'former':'Anciens inscrits — résultats historiques', 'empty':'Aucun étudiant dans cette section.',
           'head':['Nom et prénom','Statut','Terminées','Meilleur score','Total','Pourcentage'],
           'NOT_STARTED':'Non commencé','IN_PROGRESS':'En cours','SUBMITTED':'Soumise','EXPIRED':'Expirée','FINISHED_UNGRADED':'Note indisponible'},
    'en': {'title':'Quiz grades', 'group':'Group', 'teacher':'Teacher', 'export':'Exported on',
           'rule':'Rule: best percentage among graded submitted or expired attempts. Non-participants are not assigned a zero grade.',
           'current':'Current members','former':'Former members — historical results','empty':'No students in this section.',
           'head':['Full name','Status','Completed','Best score','Total','Percentage'],
           'NOT_STARTED':'Not started','IN_PROGRESS':'In progress','SUBMITTED':'Submitted','EXPIRED':'Expired','FINISHED_UNGRADED':'Grade unavailable'},
    'ar': {'title':'درجات الاختبار','group':'المجموعة','teacher':'المدرس','export':'تاريخ التصدير',
           'rule':'القاعدة: أفضل نسبة من المحاولات المصححة المسلمة أو المنتهية. لا تمنح درجة الصفر لمن لم يبدأ.',
           'current':'المسجلون الحاليون','former':'المسجلون السابقون — النتائج التاريخية','empty':'لا يوجد طلاب في هذا القسم.',
           'head':['الاسم الكامل','الحالة','المكتملة','أفضل درجة','المجموع','النسبة'],
           'NOT_STARTED':'لم يبدأ','IN_PROGRESS':'قيد الإنجاز','SUBMITTED':'مسلمة','EXPIRED':'منتهية','FINISHED_UNGRADED':'الدرجة غير متاحة'},
}


def grades_pdf(quiz, sections, language='fr'):
    from fpdf import FPDF
    from fpdf.fonts import FontFace
    labels = LABELS[language]
    class GradePDF(FPDF):
        def footer(self):
            self.set_y(-12); self.set_font('Noto', size=8)
            self.cell(0, 6, f'{self.page_no()} / {{nb}}', align='C')
    pdf = GradePDF()
    fonts = Path(__file__).with_name('fonts')
    for family, filename in [('Noto','NotoSans.ttf'), ('Arabic','NotoSansArabic.ttf')]:
        pdf.add_font(family, fname=str(fonts/filename))
        pdf.add_font(family, style='B', fname=str(fonts/filename))
    pdf.set_fallback_fonts(['Arabic', 'Noto'])
    pdf.set_text_shaping(True)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_margins(12, 14, 12)
    pdf.add_page(); pdf.set_font('Noto', 'B', 16)
    pdf.multi_cell(0, 9, labels['title'], new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Noto', size=11)
    for text in [quiz.title, f"{labels['group']} : {quiz.learning_group.name}",
                 f"{labels['teacher']} : {quiz.teacher.first_name} {quiz.teacher.last_name}",
                 f"{labels['export']} : {timezone.localtime().strftime('%Y-%m-%d %H:%M %Z')} — Africa/Tunis", labels['rule']]:
        pdf.multi_cell(0, 7, text, new_x='LMARGIN', new_y='NEXT')
    for section in ('current','former'):
        if pdf.will_page_break(28): pdf.add_page()
        pdf.ln(5);pdf.set_font('Noto','B',12)
        pdf.multi_cell(0, 8, labels[section], new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Noto',size=9)
        if not sections[section]:
            pdf.multi_cell(0,7,labels['empty'],new_x='LMARGIN',new_y='NEXT');continue
        with pdf.table(col_widths=(59,33,20,26,20,28), line_height=6, padding=2,
                       headings_style=FontFace(emphasis='B', fill_color=(236,238,255)),
                       text_align=('LEFT','CENTER','CENTER','CENTER','CENTER','CENTER')) as table:
            for values in [labels['head']] + [[row['name'], labels[row['status']], str(row['completed_attempts']),
                     str(row['points']) if row['points'] is not None else '—', str(row['total']) if row['total'] is not None else '—',
                     f"{row['percentage']:.2f} %" if row['percentage'] is not None else '—'] for row in sections[section]]:
                record=table.row()
                for value in values: record.cell(value)
    return bytes(pdf.output())


class GradeExportView(ReadOnlyResultsView):
    def get(self, request, uid):
        from rest_framework.fields import ChoiceField
        quiz = managed_quiz(request.user, uid)
        language = ChoiceField(choices=list(LABELS)).run_validation(request.query_params.get('lang', 'fr'))
        response=HttpResponse(grades_pdf(quiz,grade_rows(quiz),language),content_type='application/pdf')
        response['Content-Disposition']=f'attachment; filename="notes-quiz-{quiz.pk}.pdf"'
        response['Cache-Control']='private, no-store'
        response['X-Content-Type-Options']='nosniff'
        return response
