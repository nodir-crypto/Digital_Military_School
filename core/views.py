import random, json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Avg, Count, Q, F
from django.core.paginator import Paginator
from django.db import transaction
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import get_template
from django.utils import timezone
from xhtml2pdf import pisa

# Modellar va Formalarni import qilish
from .models import (
    Subject, Lesson, Quiz, Choice, Question,
    DepartmentResource, GlobalLibrary, QuizAttempt, Department, PasswordResetOTP,
     OfficialMessage  # Xabarlar modeli bor deb hisoblaymiz
)
from .forms import LessonForm, ProfileEditForm, DepartmentResourceForm, GlobalLibraryForm

User = get_user_model()



def login_success(request):
    """
    Login muvaffaqiyatli bo'lgandan keyin foydalanuvchini
    roliga qarab kerakli sahifaga yo'naltiruvchi controller.
    """
    user = request.user
    if user.role == 'INST_HEAD':
        return redirect('management_dashboard')
    elif user.role == 'DEPT_HEAD':
        return redirect('dept_head_dashboard')
    elif user.role == 'INSTRUCTOR':
        return redirect('instructor_dashboard')
    elif user.role == 'KURSANT':
        return redirect('home')
    else:
        return redirect('home')

# ================================================================
# 0. PROFESSIONAL COMMAND & CONTROL DASHBOARDS (SENIOR LOGIC)
# ================================================================


from .models import  User
import datetime

@login_required
def management_dashboard(request):
    """
    Mavjud logikani saqlagan holda Institut boshlig'i uchun
    statistikani yanada chuqurlashtiramiz.
    """
    user = request.user
    if user.role not in ['DEPT_HEAD', 'INST_HEAD']:
        return redirect('home')

    # INSTITUT BOSHLIG'I LOGIKASI (Mavjud strukturani boyitish)
    if user.role == 'INST_HEAD':
        # Barcha kafedralarni kengaytirilgan statistika bilan olish
        departments = Department.objects.all().annotate(
            total_students=Count('members', filter=Q(members__role='KURSANT'), distinct=True),
            total_teachers=Count('members', filter=Q(members__role='INSTRUCTOR'), distinct=True),
            avg_score=Avg('members__quizattempt__score'),
            head_last_login=Max('members__last_login', filter=Q(members__role='DEPT_HEAD'))
        ).order_by('-avg_score') # Reyting bo'yicha saralash

        # Global statistika (Yangi qo'shilgan)
        overall_stats = {
            'total_users': User.objects.count(),
            'inst_avg': QuizAttempt.objects.aggregate(Avg('score'))['score__avg'] or 0,
            'online_now': User.objects.filter(last_online__gte=timezone.now() - datetime.timedelta(minutes=5)).count()
        }

        return render(request, 'management/inst_head_dashboard.html', {
            'departments': departments,
            'active_tab': 'institute_global',
            'overall_stats': overall_stats
        })

    # KAFEDRA BOSHLIG'I LOGIKASI (Mavjud yo'naltirish saqlab qolindi)
    if user.role == 'DEPT_HEAD':
        if user.department:
            # Diqqat: Bu yerda biz avvalgi redirectni saqlaymiz,
            # lekin bu view endi biz yozgan yangi tahliliy mantiq bilan boyitiladi.
            return redirect('department_detail_view', dept_id=user.department.id)
        else:
            return render(request, 'errors/no_dept.html', {"message": "Sizga kafedra biriktirilmagan"})





from django.db.models import Avg, Count, Max
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from .models import Department, User, Subject, QuizAttempt, OfficialMessage

@login_required
def department_detail_view(request, dept_id):
    """
    Kafedra va Institut boshliqlari uchun umumiy tahlil.
    Mantiq: Eng yuqori ball emas, barcha urinishlarning o'rtacha bali asosida.
    """
    dept = get_object_or_404(Department, id=dept_id)
    user = request.user

    # 1. RUXSATLARNI TEKSHIRISH
    if user.role == 'DEPT_HEAD' and user.department.id != dept_id:
        raise PermissionDenied

    # 2. KURSANLAR RO'YXATI (Barcha urinishlarning o'rtacha bali - Avg)
    students = User.objects.filter(department=dept, role='KURSANT').annotate(
        # Kursantning barcha urinishlari o'rtachasi
        avg_score=Avg('quizattempt__score'),
        total_tests=Count('quizattempt__quiz', distinct=True),
        last_act=Max('quizattempt__completed_at')
    ).order_by('-is_starshina', '-avg_score')

    # 3. QIZIL HUDUD (O'rtacha bali 60 dan pastlar)
    at_risk_students = [s for s in students if s.avg_score is not None and s.avg_score < 60]

    # 4. O'QITUVCHILAR KPI (Ular yaratgan testlarning umumiy o'rtacha natijasi)
    instructors = User.objects.filter(department=dept, role='INSTRUCTOR').annotate(
        lessons_count=Count('created_lessons', distinct=True),
        avg_quiz_score=Avg('created_lessons__quiz__quizattempt__score'),
        total_students_reached=Count('created_lessons__quiz__quizattempt__user', distinct=True)
    ).order_by('-lessons_count')

    # 5. FANLAR TAHLILI (Fandagi barcha testlar o'rtachasi)
    subjects = Subject.objects.filter(available_in_departments=dept).annotate(
        subject_avg=Avg('lessons__quiz__quizattempt__score'),
        participation_rate=Count('lessons__quiz__quizattempt__user', distinct=True)
    ).order_by('-subject_avg')

    # 6. RASMIY BUYRUQLAR
    if user.role == 'INST_HEAD':
        # Institut boshlig'i uchun ushbu kafedra rahbariga yuborilgan xabarlar
        dept_head = User.objects.filter(department=dept, role='DEPT_HEAD').first()
        official_orders = OfficialMessage.objects.filter(
            receiver=dept_head
        ).order_by('-created_at')[:5] if dept_head else []
    else:
        # Kafedra boshlig'i uchun o'zining xabarlari
        official_orders = OfficialMessage.objects.filter(
            receiver=user
        ).order_by('-created_at')[:5]

    # 7. KAFEDRA UMUMIY KPI (Barcha urinishlar o'rtachasi)
    overall_avg_query = QuizAttempt.objects.filter(user__department=dept).aggregate(
        final_avg=Avg('score')
    )['final_avg']

    context = {
        'dept': dept,
        'students': students,
        'at_risk_students': at_risk_students,
        'instructors': instructors,
        'subjects': subjects,
        'official_orders': official_orders,
        'overall_avg': overall_avg_query or 0,
        'is_inst_view': (user.role == 'INST_HEAD')
    }

    return render(request, 'management/dept_head_dashboard.html', context)



@login_required
def subject_performance_detail(request, subject_id, dept_id):
    """
    Muayyan fanga kirganda kursantlarning reytingi va o'zlashtirish natijalari.
    """
    subject = get_object_or_404(Subject, id=subject_id)
    dept = get_object_or_404(Department, id=dept_id)

    # Shu fandan shu kafedra kursantlarining natijalari
    rankings = User.objects.filter(
        department=dept,
        role='KURSANT'
    ).annotate(
        spec_avg=Avg('quizattempt__score', filter=Q(quizattempt__quiz__lesson__subject=subject)),
        tests_done=Count('quizattempt', filter=Q(quizattempt__quiz__lesson__subject=subject))
    ).filter(tests_done__gt=0).order_by('-spec_avg')

    return render(request, 'management/subject_ranking.html', {
        'subject': subject,
        'dept': dept,
        'rankings': rankings
    })


# ================================================================
# COMMUNICATIONS ( MESSAGES)
# ================================================================

@login_required
def send_official_message(request):
    """Boshliqlar o'rtasida professional xabar almashish logikasi"""
    if request.method == "POST":
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content')
        receiver = get_object_or_404(User, id=receiver_id)

        # Xabarni saqlash
        OfficialMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            body=content,
            created_at=timezone.now()
        )

        messages.success(request, f"{receiver.get_full_name()} uchun xizmat xabari yuborildi.")
        return redirect(request.META.get('HTTP_REFERER', 'management_dashboard'))
    return JsonResponse({'status': 'error'}, status=400)


# ================================================================
# 1. DARSLARNI BOSHQARISH (CRUD & BUILDER) - O'ZGARISSIZ
# ================================================================

@login_required
def delete_quiz(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    if request.method == 'POST':
        if hasattr(lesson, 'quiz'):
            lesson.quiz.delete()
            messages.success(request, "Test muvaffaqiyatli o'chirildi.")
        else:
            messages.error(request, "Ushbu darsda o'chirish uchun test topilmadi.")
        return redirect('instructor_dashboard')
    return render(request, 'core/confirm_delete.html', {'obj': getattr(lesson, 'quiz', None), 'type': 'test'})


@login_required
def quiz_builder(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    quiz = getattr(lesson, 'quiz', None)
    existing_questions = []
    if quiz:
        for q in quiz.questions.all().prefetch_related('choices'):
            existing_questions.append({
                'id': q.id, 'text': q.text, 'difficulty': q.difficulty,
                'explanation': q.explanation or '',
                'choices': [{'text': c.text, 'is_correct': c.is_correct} for c in q.choices.all()]
            })

    if request.method == "POST":
        try:
            with transaction.atomic():
                quiz_title = request.POST.get('quiz_title', f"{lesson.title} testi")
                duration = request.POST.get('duration', 15)
                if not quiz:
                    quiz = Quiz.objects.create(lesson=lesson, title=quiz_title, duration=duration)
                else:
                    quiz.title, quiz.duration = quiz_title, duration
                    quiz.save()
                    quiz.questions.all().delete()

                total_q = int(request.POST.get('total_questions', 0))
                for i in range(1, total_q + 1):
                    q_text = request.POST.get(f'q_text_{i}')
                    if not q_text: continue
                    question = Question.objects.create(
                        quiz=quiz, text=q_text,
                        difficulty=request.POST.get(f'difficulty_{i}', 'MEDIUM'),
                        explanation=request.POST.get(f'explanation_{i}', '')
                    )
                    correct_letter = request.POST.get(f'q_{i}_correct')
                    for letter in ['a', 'b', 'c', 'd']:
                        c_text = request.POST.get(f'q_{i}_choice_{letter}')
                        if c_text:
                            Choice.objects.create(question=question, text=c_text, is_correct=(letter == correct_letter))
                messages.success(request, "Test muvaffaqiyatli saqlandi!")
                return redirect('instructor_dashboard')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")

    return render(request, 'core/quiz_builder.html', {
        'lesson': lesson, 'quiz': quiz, 'existing_questions_json': json.dumps(existing_questions)
    })


# ================================================================
# 2. DINAMIK FILTRLASH VA ASOSIY SAHIFA - O'ZGARISSIZ
# ================================================================

@login_required
def get_departments_by_subject(request):
    subject_id = request.GET.get('subject_id')
    if subject_id:
        subject = get_object_or_404(Subject, id=subject_id)
        departments = subject.available_in_departments.all()
        data = [{'id': d.id, 'name': d.name} for d in departments]
        return JsonResponse({'departments': data})
    return JsonResponse({'departments': []})


@login_required
def home(request):
    user = request.user
    if user.role in ['DEPT_HEAD', 'INST_HEAD']:
        return redirect('management_dashboard')

    search_query = request.GET.get('search', '').strip()
    if user.role == 'KURSANT':
        subject_list = Subject.objects.filter(available_in_departments=user.department).distinct().order_by('-id')
        if search_query:
            subject_list = subject_list.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

        paginator = Paginator(subject_list, 6)
        page_obj = paginator.get_page(request.GET.get('page'))

        user_attempts = QuizAttempt.objects.filter(user=user).order_by('-completed_at')
        avg_score = user_attempts.aggregate(Avg('score'))['score__avg'] or 0
        top_3 = User.objects.filter(department=user.department, role='KURSANT').annotate(
            student_avg_score=Avg('quizattempt__score'),
            student_total_tests=Count('quizattempt')
        ).filter(student_total_tests__gt=0).order_by('-student_avg_score')[:3]

        context = {
            'subjects': page_obj, 'page_obj': page_obj, 'search_query': search_query,
            'lessons': Lesson.objects.filter(target_departments=user.department).distinct(),
            'avg_score': round(avg_score, 1), 'total_tests': user_attempts.count(),
            'recent_attempts': user_attempts[:5], 'top_3': top_3,
        }
        return render(request, 'core/home.html', context)
    return redirect('instructor_dashboard')


# ================================================================
# 3. ANALITIKA VA REYTING - O'ZGARISSIZ
# ================================================================

@login_required
def student_analytics(request):
    all_qs = QuizAttempt.objects.filter(user=request.user, completed_at__isnull=False).select_related(
        'quiz__lesson__subject')
    recent_attempts = all_qs.order_by('-completed_at')[:10][::-1]
    timeline_data = {
        'labels': [a.completed_at.strftime('%d/%m') for a in recent_attempts],
        'scores': [float(a.score) for a in recent_attempts],
    }
    subject_stats = all_qs.values('quiz__lesson__subject__name').annotate(avg_score=Avg('score')).order_by('-avg_score')
    subject_data = {
        'labels': [s['quiz__lesson__subject__name'] for s in subject_stats],
        'scores': [round(float(s['avg_score']), 1) for s in subject_stats],
    }
    return render(request, 'core/analytics.html', {
        'avg_score': all_qs.aggregate(Avg('score'))['score__avg'] or 0,
        'timeline_data_json': json.dumps(timeline_data, cls=DjangoJSONEncoder),
        'subject_data_json': json.dumps(subject_data, cls=DjangoJSONEncoder),
    })


def ranking_view(request):
    rankings = User.objects.filter(role='KURSANT').annotate(
        avg_score=Avg('quizattempt__score'),
        total_tests=Count('quizattempt')
    ).filter(total_tests__gt=0).order_by('-avg_score')
    return render(request, 'core/ranking.html', {'top_3': rankings[:3], 'others': rankings[3:]})


# ================================================================
# 4. TEST TOPSHIRISH MANTIQI - O'ZGARISSIZ
# ================================================================

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.user.role == 'KURSANT' and not quiz.lesson.target_departments.filter(
            id=request.user.department.id).exists():
        messages.error(request, "Bu testga ruxsatingiz yo'q.")
        return redirect('home')

    questions = quiz.questions.all().order_by('id')
    total = questions.count()
    step_key, ans_key = f'quiz_{quiz_id}_step', f'quiz_{quiz_id}_answers'
    step = request.session.get(step_key, 0)

    if step >= total:
        user_answers = request.session.get(ans_key, {})
        correct = 0
        for q in questions:
            ans_id = user_answers.get(str(q.id))
            if ans_id and Choice.objects.filter(id=ans_id, question=q, is_correct=True).exists():
                correct += 1
        score = (correct / total * 100) if total > 0 else 0
        QuizAttempt.objects.create(user=request.user, quiz=quiz, score=score)
        request.session[step_key], request.session[ans_key] = 0, {}
        return redirect('quiz_result', quiz_id=quiz.id)

    current_q = questions[step]
    if request.method == 'POST':
        choice_id = request.POST.get('choice')
        if choice_id:
            answers = request.session.get(ans_key, {})
            answers[str(current_q.id)] = choice_id
            request.session[ans_key] = answers
            request.session[step_key] = step + 1
            return redirect('take_quiz', quiz_id=quiz.id)

    return render(request, 'quiz/take_quiz.html', {
        'quiz': quiz, 'question': current_q, 'step': step + 1, 'total': total,
        'progress': int(((step + 1) / total) * 100)
    })


@login_required
def quiz_result(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    all_attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('-completed_at')
    if not all_attempts.exists(): return redirect('home')
    current_attempt = all_attempts.first()
    history = list(all_attempts[:5])
    history.reverse()
    return render(request, 'quiz/result.html', {
        'quiz': quiz, 'attempt': current_attempt, 'score': current_attempt.score,
        'is_passed': current_attempt.is_passed, 'history': history,
        'best_score': all_attempts.aggregate(Max('score'))['score__max'],
    })


# ================================================================
# 5. DARSLAR VA DASHBOARD - O'ZGARISSIZ
# ================================================================

@login_required
def subject_lessons(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    lesson_list = subject.lessons.filter(
        target_departments=request.user.department).distinct() if request.user.role == 'KURSANT' else subject.lessons.all()
    paginator = Paginator(lesson_list.order_by('-created_at'), 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/subject_lessons.html', {'subject': subject, 'lessons': page_obj, 'page_obj': page_obj})


@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return render(request, 'core/lesson_detail.html', {'lesson': lesson, 'quiz': getattr(lesson, 'quiz', None)})


@login_required
def instructor_dashboard(request):
    if request.user.role not in ['INSTRUCTOR','DEPT_HEAD', 'INST_HEAD']: return redirect('home')
    teacher_subjects = Subject.objects.filter(instructors=request.user)
    lessons = Lesson.objects.filter(author=request.user).order_by('-created_at')
    selected_subject = request.GET.get('subject_filter')
    if selected_subject: lessons = lessons.filter(subject_id=selected_subject)
    return render(request, 'core/instructor_dashboard.html', {
        'lessons': lessons, 'teacher_subjects': teacher_subjects, 'selected_subject_id': selected_subject
    })


@login_required
def add_lesson(request):
    if request.user.role not in ['INSTRUCTOR','DEPT_HEAD', 'INST_HEAD']: raise PermissionDenied
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.author = request.user
            lesson.save()
            form.save_m2m()
            return redirect('instructor_dashboard')
    else:
        form = LessonForm(user=request.user)
    return render(request, 'core/add_lesson.html', {'form': form})


@login_required
def edit_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson, user=request.user)
        if form.is_valid(): form.save(); return redirect('instructor_dashboard')
    else:
        form = LessonForm(instance=lesson, user=request.user)
    return render(request, 'core/add_lesson.html', {'form': form, 'edit_mode': True})


@login_required
def delete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    if request.user.is_superuser or lesson.author == request.user:
        if request.method == 'POST': lesson.delete(); return redirect('instructor_dashboard')
        return render(request, 'core/confirm_delete.html', {'lesson': lesson})
    raise PermissionDenied


# ================================================================
# 6. PROFIL VA KUTUBXONA - O'ZGARISSIZ
# ================================================================

@login_required
def profile(request):
    attempts = QuizAttempt.objects.filter(user=request.user)
    avg = attempts.aggregate(Avg('score'))['score__avg'] or 0
    passed = attempts.filter(is_passed=True).values('quiz').distinct().count()
    return render(request, 'core/profile.html', {
        'user': request.user, 'avg_score': round(avg, 1),
        'passed_quizzes': passed, 'total_attempts': attempts.count()
    })


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid(): form.save(); return redirect('profile')
    return render(request, 'core/profile_edit.html', {'form': ProfileEditForm(instance=request.user)})


@login_required
def resource_hub(request):
    dept_res = DepartmentResource.objects.filter(department=request.user.department) if request.user.department else []
    return render(request, 'resources/hub.html', {
        'dept_resources': dept_res, 'global_books': GlobalLibrary.objects.all(), 'active_tab': 'resources'
    })


@login_required
def upload_resource(request):
    if request.user.role not in ['INSTRUCTOR','DEPT_HEAD', 'INST_HEAD']: return redirect('resource_hub')
    if request.method == 'POST':
        res_type = request.POST.get('res_type')
        data = {
            'title': request.POST.get('title'), 'file': request.FILES.get('file'),
            'image': request.FILES.get('image'), 'file_type': request.POST.get('file_type'),
            'uploaded_by': request.user
        }
        if res_type == 'dept':
            DepartmentResource.objects.create(department=request.user.department, **data)
        else:
            GlobalLibrary.objects.create(description=request.POST.get('description', ''), **data)
        messages.success(request, "Muvaffaqiyatli saqlandi!")
        return redirect('resource_hub')
    return render(request, 'resources/upload.html')


@login_required
def edit_global_resource(request, pk):
    resource = get_object_or_404(GlobalLibrary, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        form = GlobalLibraryForm(request.POST, request.FILES, instance=resource)
        if form.is_valid(): form.save(); messages.success(request, "Yangilandi!"); return redirect('resource_hub')
    return render(request, 'core/edit_resource.html', {'form': GlobalLibraryForm(instance=resource)})


@login_required
def delete_global_resource(request, pk):
    resource = get_object_or_404(GlobalLibrary, pk=pk, uploaded_by=request.user)
    if request.method == 'POST': resource.delete(); messages.success(request, "O'chirildi.")
    return redirect('resource_hub')


@login_required
def edit_dept_resource(request, pk):
    resource = get_object_or_404(DepartmentResource, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        form = DepartmentResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid(): form.save(); messages.success(request, "Yangilandi!"); return redirect('resource_hub')
    return render(request, 'core/edit_resource.html', {'form': DepartmentResourceForm(instance=resource)})


@login_required
def delete_dept_resource(request, pk):
    resource = get_object_or_404(DepartmentResource, pk=pk, uploaded_by=request.user)
    if request.method == 'POST': resource.delete()
    return redirect('resource_hub')


# ================================================================
# 7. PASSWORD RESET - O'ZGARISSIZ
# ================================================================

def forget_password_view(request):
    if request.method == "POST":
        username, email = request.POST.get('username'), request.POST.get('email')
        user = User.objects.filter(username=username, email=email).first()
        if user:
            PasswordResetOTP.objects.filter(user=user).delete()
            otp, token = str(random.randint(100000, 999999)), PasswordResetOTP.generate_token()
            PasswordResetOTP.objects.create(user=user, otp_code=otp, token=token)
            message = f"Salom {user.username}!\nTasdiqlash kodingiz: {otp}\nAmal qilish vaqti: 10 daqiqa."
            try:
                send_mail("Parolni tiklash", message, 'noreply@dms.uz', [user.email])
                return redirect('verify_otp', token=token)
            except:
                messages.error(request, "Email yuborishda xatolik.")
        else:
            messages.error(request, "Foydalanuvchi topilmadi.")
    return render(request, 'password/forget_password.html')


def verify_otp_view(request, token):
    otp_obj = get_object_or_404(PasswordResetOTP, token=token)
    if not otp_obj.is_valid(): return redirect('forget_password')
    if request.method == "POST":
        if request.POST.get('otp') == otp_obj.otp_code:
            otp_obj.is_verified = True;
            otp_obj.save()
            request.session[f'can_reset_{token}'] = True
            return redirect('reset_password', token=token)
        messages.error(request, "Kod noto'g'ri!")
    return render(request, 'password/verify_otp.html', {'token': token})


def reset_password_view(request, token):
    otp_obj = get_object_or_404(PasswordResetOTP, token=token, is_verified=True)
    if not request.session.get(f'can_reset_{token}'): return redirect('forget_password')
    if request.method == "POST":
        p1, p2 = request.POST.get('pass1'), request.POST.get('pass2')
        if p1 == p2:
            user = otp_obj.user;
            user.set_password(p1);
            user.save()
            otp_obj.delete();
            del request.session[f'can_reset_{token}']
            messages.success(request, "Parol yangilandi!");
            return redirect('login')
        messages.error(request, "Parollar mos kelmadi!")
    return render(request, 'password/reset_password.html', {'token': token})


def custom_404_handler(request, exception):
    return render(request, '404.html', status=404)


# ================================================================
# 8. Kafedira Boshlig'i
# ================================================================

from django.db.models import Max, Avg, Count, Subquery, OuterRef
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Subject, QuizAttempt, OfficialMessage, User

from django.db.models import Max, Avg, Subquery, OuterRef

from django.db.models import Max, Avg, Count, Subquery, OuterRef
from django.shortcuts import render
from .models import Subject, User, QuizAttempt


from django.db.models import Max, Avg, Subquery, OuterRef

@login_required
def dept_head_dashboard(request):
    """
    Kafedra boshlig'i uchun barcha kursantlarning barcha urinishlari
    o'rtacha bali asosida hisoblangan dashboard.
    """
    if not hasattr(request.user, 'role') or request.user.role != 'DEPT_HEAD':
        return redirect('home')

    my_dept = request.user.department
    if not my_dept:
        return render(request, 'errors/no_dept.html', {"message": "Sizga kafedra biriktirilmagan"})

    # 1. KURSANLAR RO'YXATI
    # Bu yerda Count('quizattempt', distinct=True) kursantlar soni ko'payib ketishini oldini oladi
    students = User.objects.filter(department=my_dept, role='KURSANT').annotate(
        # Kursantning barcha urinishlari o'rtachasi (Siz aytgan hamma urinishlar mantiqi)
        avg_score=Avg('quizattempt__score'),
        # Nechta urinish qilgani
        total_attempts=Count('quizattempt'),
        # Nechta alohida test topshirgani (distinct=True shart!)
        total_tests=Count('quizattempt__quiz', distinct=True),
        last_act=Max('quizattempt__completed_at')
    ).order_by('-is_starshina', '-avg_score')

    # 2. QIZIL HUDUD (Hamma urinishlar o'rtachasi 60 dan past bo'lsa)
    at_risk_students = [s for s in students if s.avg_score is not None and s.avg_score < 60]

    # 3. O'QITUVCHILAR (O'qituvchi yaratgan testlardagi hamma urinishlar o'rtachasi)
    instructors = User.objects.filter(department=my_dept, role='INSTRUCTOR').annotate(
        lessons_count=Count('created_lessons', distinct=True),
        # O'qituvchi tomonidan yaratilgan barcha testlardagi barcha urinishlar o'rtachasi
        avg_quiz_score=Avg('created_lessons__quiz__quizattempt__score')
    ).order_by('-lessons_count')

    # 4. FANLAR (Fandagi barcha test urinishlari o'rtachasi)
    subjects = Subject.objects.filter(available_in_departments=my_dept).annotate(
        # Shu fandagi darslarning testlaridagi hamma urinishlar o'rtachasi
        subject_avg=Avg('lessons__quiz__quizattempt__score'),
        # Fanda qatnashgan jami unikal kursantlar soni
        participation_rate=Count('lessons__quiz__quizattempt__user', distinct=True)
    ).order_by('-subject_avg')

    # 5. RASMIY BUYRUQLAR
    official_orders = OfficialMessage.objects.filter(
        receiver=request.user
    ).order_by('-created_at')[:5]

    # 6. KAFEDRA UMUMIY KPI (Institut boshlig'i ko'radigan ko'rsatkich bilan bir xil)
    # Kafedradagi barcha kursantlarning barcha urinishlari o'rtachasi
    overall_avg_query = QuizAttempt.objects.filter(
        user__department=my_dept,
        user__role='KURSANT'
    ).aggregate(final_avg=Avg('score'))['final_avg']

    context = {
        'dept': my_dept,
        'students': students,
        'at_risk_students': at_risk_students,
        'instructors': instructors,
        'subjects': subjects,
        'official_orders': official_orders,
        'overall_avg': overall_avg_query or 0,
    }
    return render(request, 'management/dept_head_dashboard.html', context)


@login_required
def mark_order_as_read(request, message_id):
    """Institut boshlig'ining buyrug'ini 'Ijro etildi' deb belgilash"""
    message = get_object_or_404(OfficialMessage, id=message_id, receiver=request.user)
    message.is_read = True
    message.save()
    messages.success(request, "Buyruq ijrosi tasdiqlandi.")
    return redirect('dept_head_dashboard')


@login_required
def send_dept_notice(request):
    """Kafedra boshlig'i tomonidan o'qituvchi yoki kursantga xabar yuborish"""
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        receiver = get_object_or_404(User, id=receiver_id)
        OfficialMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            subject=subject,
            body=body
        )
        messages.success(request, "Xabarnoma muvaffaqiyatli yuborildi.")
    return redirect('dept_head_dashboard')




# ================================================================
# 9. PDF SENDING
# ================================================================
def export_dept_stats_pdf(request):
    """Kafedra statistikasi bo'yicha rasmiy PDF hisobot yaratish"""
    if request.user.role != 'DEPT_HEAD':
        return HttpResponse("Ruxsat berilmagan", status=403)

    my_dept = request.user.department
    students = User.objects.filter(department=my_dept, role='KURSANT').annotate(
        avg_score=Avg('quizattempt__score')
    ).order_by('-avg_score')

    context = {
        'dept': my_dept,
        'students': students,
        'date': timezone.now(),
        'head_name': request.user.get_full_name(),
        'overall_avg': QuizAttempt.objects.filter(user__department=my_dept).aggregate(Avg('score'))['score__avg']
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{my_dept.name}_hisobot.pdf"'

    template = get_template('management/pdf_report_template.html')
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    return response






# #######################################################################
from django.http import JsonResponse

# def get_user_details(request, user_id):
#     user_obj = get_object_or_404(User, id=user_id)
#
#     data = {
#         'full_name': user_obj.get_full_name(),
#         'role': user_obj.get_role_display(),
#         'department': user_obj.department.name if user_obj.department else "--",
#         'joined_at': user_obj.date_joined.strftime('%d.%m.%Y'),
#     }
#
#     if user_obj.role == 'KURSANT':
#         # Kursant uchun maxsus statistika
#         attempts = QuizAttempt.objects.filter(user=user_obj)
#         best_scores = attempts.values('quiz').annotate(max_s=Max('score'))
#         avg_kpi = best_scores.aggregate(Avg('max_s'))['max_s__avg'] or 0
#
#         data.update({
#             'stat_label_1': 'O\'rtacha KPI',
#             'stat_value_1': f"{round(avg_kpi, 1)}%",
#             'stat_label_2': 'Topshirilgan testlar',
#             'stat_value_2': best_scores.count(),
#             'stat_label_3': 'Jami urinishlar',
#             'stat_value_3': attempts.count(),
#         })
#
#     elif user_obj.role == 'INSTRUCTOR':
#         # O'qituvchi uchun maxsus statistika
#         lessons = user_obj.created_lessons.count()
#         avg_quality = QuizAttempt.objects.filter(quiz__lesson__author=user_obj) \
#                           .values('user', 'quiz').annotate(max_s=Max('score')) \
#                           .aggregate(Avg('max_s'))['max_s__avg'] or 0
#
#         data.update({
#             'stat_label_1': 'Oqitish Sifati',
#             'stat_value_1': f"{round(avg_quality, 1)}%",
#             'stat_label_2': 'Yaratilgan darslar',
#             'stat_value_2': lessons,
#             'stat_label_3': 'Faol shogirdlar',
#             'stat_value_3': User.objects.filter(department=user_obj.department, role='KURSANT').count(),
#         })
#
#     return JsonResponse(data)

def get_user_details(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    data = {
        'full_name': user_obj.get_full_name(),
        # SHU YERGA AVATAR URL QO'SHILDI:
        'profile_picture_url': user_obj.avatar.url if user_obj.avatar else "",
        'role': user_obj.get_role_display(),
        'department': user_obj.department.name if user_obj.department else "--",
        'joined_at': user_obj.date_joined.strftime('%d.%m.%Y'),
    }

    if user_obj.role == 'KURSANT':
        # Kursant uchun maxsus statistika
        attempts = QuizAttempt.objects.filter(user=user_obj)
        best_scores = attempts.values('quiz').annotate(max_s=Max('score'))
        avg_kpi = best_scores.aggregate(Avg('max_s'))['max_s__avg'] or 0

        data.update({
            'stat_label_1': 'O\'rtacha KPI',
            'stat_value_1': f"{round(avg_kpi, 1)}%",
            'stat_label_2': 'Topshirilgan testlar',
            'stat_value_2': best_scores.count(),
            'stat_label_3': 'Jami urinishlar',
            'stat_value_3': attempts.count(),
        })

    elif user_obj.role == 'INSTRUCTOR':
        # O'qituvchi uchun maxsus statistika
        lessons = user_obj.created_lessons.count()
        avg_quality = QuizAttempt.objects.filter(quiz__lesson__author=user_obj) \
                          .values('user', 'quiz').annotate(max_s=Max('score')) \
                          .aggregate(Avg('max_s'))['max_s__avg'] or 0

        data.update({
            'stat_label_1': 'Oqitish Sifati',
            'stat_value_1': f"{round(avg_quality, 1)}%",
            'stat_label_2': 'Yaratilgan darslar',
            'stat_value_2': lessons,
            'stat_label_3': 'Faol shogirdlar',
            'stat_value_3': User.objects.filter(department=user_obj.department, role='KURSANT').count(),
        })

    return JsonResponse(data)