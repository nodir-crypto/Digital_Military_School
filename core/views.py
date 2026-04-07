from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Avg, Count, Q
from django.core.paginator import Paginator
from django.db import transaction
from django.contrib import messages
import json

# Modellar va Formalarni import qilish
from .models import (
    Subject, Lesson, Quiz, Choice, Question,
    DepartmentResource, GlobalLibrary, QuizAttempt, Department
)
from .forms import LessonForm, ProfileEditForm, DepartmentResourceForm, GlobalLibraryForm

User = get_user_model()


# ================================================================
# 1. DARSLARNI BOSHQARISH (CRUD & BUILDER)
# ================================================================

@login_required
def delete_quiz(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    if hasattr(lesson, 'quiz'):
        lesson.quiz.delete()
        messages.success(request, "Test muvaffaqiyatli o'chirildi.")
    else:
        messages.error(request, "Ushbu darsda o'chirish uchun test topilmadi.")
    return redirect('instructor_dashboard')


@login_required
def quiz_builder(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    quiz = getattr(lesson, 'quiz', None)

    existing_questions = []
    if quiz:
        for q in quiz.questions.all().prefetch_related('choices'):
            existing_questions.append({
                'id': q.id,
                'text': q.text,
                'difficulty': q.difficulty,
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
                    quiz.title = quiz_title
                    quiz.duration = duration
                    quiz.save()
                    quiz.questions.all().delete()

                total_q = int(request.POST.get('total_questions', 0))
                for i in range(1, total_q + 1):
                    q_text = request.POST.get(f'q_text_{i}')
                    if not q_text: continue

                    question = Question.objects.create(
                        quiz=quiz,
                        text=q_text,
                        difficulty=request.POST.get(f'difficulty_{i}', 'MEDIUM'),
                        explanation=request.POST.get(f'explanation_{i}', '')
                    )

                    correct_letter = request.POST.get(f'q_{i}_correct')
                    for letter in ['a', 'b', 'c', 'd']:
                        c_text = request.POST.get(f'q_{i}_choice_{letter}')
                        if c_text:
                            Choice.objects.create(
                                question=question,
                                text=c_text,
                                is_correct=(letter == correct_letter)
                            )
                messages.success(request, "Test muvaffaqiyatli saqlandi!")
                return redirect('instructor_dashboard')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")

    context = {
        'lesson': lesson,
        'quiz': quiz,
        'existing_questions_json': json.dumps(existing_questions)
    }
    return render(request, 'core/quiz_builder.html', context)


# ================================================================
# 2. DINAMIK FILTRLASH (Siz so'ragan asosiy o'zgarish)
# ================================================================

@login_required
def get_departments_by_subject(request):
    """
    O'qituvchi dars yuklayotganda fanni tanlasa, faqat o'sha
    fanga ruxsat berilgan kafedralar ro'yxatini qaytaradi.
    """
    subject_id = request.GET.get('subject_id')
    if subject_id:
        # Fan modelidagi 'available_in_departments' orqali kafedralarni olamiz
        subject = get_object_or_404(Subject, id=subject_id)
        departments = subject.available_in_departments.all()

        data = [{'id': d.id, 'name': d.name} for d in departments]
        return JsonResponse({'departments': data})
    return JsonResponse({'departments': []})


@login_required
def home(request):
    user = request.user
    search_query = request.GET.get('search', '').strip()

    if user.role == 'KURSANT':
        # Kursant faqat o'z kafedrasiga ruxsat berilgan fanlarni ko'radi
        subject_list = Subject.objects.filter(available_in_departments=user.department).distinct().order_by('-id')

        if search_query:
            subject_list = subject_list.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            ).distinct()

        paginator = Paginator(subject_list, 6)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'subjects': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'search_query': search_query,
        }

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'core/partials/subject_list_partial.html', context)

        # Analitika va Dashboard ma'lumotlari
        user_attempts = QuizAttempt.objects.filter(user=user).order_by('-completed_at')
        avg_score = user_attempts.aggregate(Avg('score'))['score__avg'] or 0

        top_3 = User.objects.filter(department=user.department, role='KURSANT').annotate(
            student_avg_score=Avg('quizattempt__score'),
            student_total_tests=Count('quizattempt')
        ).filter(student_total_tests__gt=0).order_by('-student_avg_score')[:3]

        lessons = Lesson.objects.filter(target_departments=user.department).distinct()

        context.update({
            'lessons': lessons,
            'avg_score': round(avg_score, 1),
            'total_tests': user_attempts.count(),
            'recent_attempts': user_attempts[:5],
            'top_3': top_3,
        })
        return render(request, 'core/home.html', context)

    return redirect('instructor_dashboard')


# ================================================================
# 3. ANALITIKA VA REYTING
# ================================================================

@login_required
def student_analytics(request):
    all_attempts = QuizAttempt.objects.filter(user=request.user).order_by('completed_at')
    stats = all_attempts.aggregate(avg_score=Avg('score'), best_score=Max('score'), total=Count('id'))

    subject_stats = QuizAttempt.objects.filter(user=request.user).values('quiz__title').annotate(avg_score=Avg('score'))

    timeline_data = {
        'labels': [a.completed_at.strftime('%d/%m') for a in all_attempts[:15]],
        'scores': [float(a.score) for a in all_attempts[:15]],
    }
    subject_data = {
        'labels': [s['quiz__title'] for s in subject_stats],
        'scores': [float(s['avg_score']) for s in subject_stats],
    }

    context = {
        'avg_score': stats['avg_score'] or 0,
        'best_score': stats['best_score'] or 0,
        'total_attempts': stats['total'],
        'timeline_data_json': json.dumps(timeline_data),
        'subject_data_json': json.dumps(subject_data),
    }
    return render(request, 'core/analytics.html', context)


def ranking_view(request):
    rankings = User.objects.filter(role='KURSANT').annotate(
        avg_score=Avg('quizattempt__score'),
        total_tests=Count('quizattempt')
    ).filter(total_tests__gt=0).order_by('-avg_score')
    return render(request, 'core/ranking.html', {'top_3': rankings[:3], 'others': rankings[3:]})


# ================================================================
# 4. TEST TOPSHIRISH MANTIQI
# ================================================================

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all().order_by('id')
    total = questions.count()

    step_key, ans_key = f'quiz_{quiz_id}_step', f'quiz_{quiz_id}_answers'
    step = request.session.get(step_key, 0)

    if step >= total:
        user_answers = request.session.get(ans_key, {})
        correct = sum(1 for q in questions if
                      Choice.objects.filter(id=user_answers.get(str(q.id)), question=q, is_correct=True).exists())
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
    attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('-completed_at')
    attempt = attempts.first()
    history = list(attempts[:5])
    history.reverse()
    return render(request, 'quiz/result.html', {
        'quiz': quiz, 'score': attempt.score, 'is_passed': attempt.is_passed,
        'history': history, 'best_score': attempts.order_by('-score').first().score, 'attempt': attempt
    })


# ================================================================
# 5. DARSLAR RO'YXATI VA DASHBOARD
# ================================================================

@login_required
def subject_lessons(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.user.role == 'KURSANT':
        lesson_list = subject.lessons.filter(target_departments=request.user.department).distinct()
    else:
        lesson_list = subject.lessons.all()

    paginator = Paginator(lesson_list.order_by('-created_at'), 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/subject_lessons.html', {'subject': subject, 'lessons': page_obj, 'page_obj': page_obj})


@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return render(request, 'core/lesson_detail.html', {'lesson': lesson, 'quiz': getattr(lesson, 'quiz', None)})


@login_required
def instructor_dashboard(request):
    if request.user.role not in ['INSTRUCTOR', 'COMMANDER']: return redirect('home')

    teacher_subjects = Subject.objects.filter(instructors=request.user)
    selected_subject = request.GET.get('subject_filter')
    lessons = Lesson.objects.filter(author=request.user).order_by('-created_at')

    if selected_subject:
        lessons = lessons.filter(subject_id=selected_subject)

    return render(request, 'core/instructor_dashboard.html', {
        'lessons': lessons, 'teacher_subjects': teacher_subjects, 'selected_subject_id': selected_subject
    })


@login_required
def add_lesson(request):
    if request.user.role not in ['INSTRUCTOR', 'COMMANDER']: raise PermissionDenied
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
        if form.is_valid():
            form.save()
            return redirect('instructor_dashboard')
    else:
        form = LessonForm(instance=lesson, user=request.user)
    return render(request, 'core/add_lesson.html', {'form': form, 'edit_mode': True})


@login_required
def delete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    if request.user.is_superuser or request.user.role == 'COMMANDER' or lesson.author == request.user:
        if request.method == 'POST':
            lesson.delete()
            return redirect('instructor_dashboard')
        return render(request, 'core/confirm_delete.html', {'lesson': lesson})
    raise PermissionDenied


# ================================================================
# 6. PROFIL VA KUTUBXONA
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
        if form.is_valid():
            form.save()
            return redirect('profile')
    return render(request, 'core/profile_edit.html', {'form': ProfileEditForm(instance=request.user)})


@login_required
def resource_hub(request):
    dept_res = DepartmentResource.objects.filter(department=request.user.department) if request.user.department else []
    return render(request, 'resources/hub.html', {
        'dept_resources': dept_res, 'global_books': GlobalLibrary.objects.all(), 'active_tab': 'resources'
    })


@login_required
def upload_resource(request):
    if request.user.role not in ['INSTRUCTOR', 'COMMANDER']: return redirect('resource_hub')
    if request.method == 'POST':
        res_type = request.POST.get('res_type')
        data = {
            'title': request.POST.get('title'),
            'file': request.FILES.get('file'),
            'image': request.FILES.get('image'),
            'file_type': request.POST.get('file_type'),
            'uploaded_by': request.user
        }
        try:
            if res_type == 'dept':
                DepartmentResource.objects.create(department=request.user.department, **data)
            else:
                GlobalLibrary.objects.create(description=request.POST.get('description', ''), **data)
            messages.success(request, "Resurs muvaffaqiyatli saqlandi!")
        except Exception as e:
            messages.error(request, f"Xatolik: {e}")
        return redirect('resource_hub')
    return render(request, 'resources/upload.html')


# ================================================================
# 7. --- GLOBAL RESOURCE EDIT/DELETE ---
# ================================================================


@login_required
def edit_global_resource(request, pk):
    # Faqat o'zi yuklagan resursni olish
    resource = get_object_or_404(GlobalLibrary, pk=pk, uploaded_by=request.user)

    if request.method == 'POST':
        form = GlobalLibraryForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, "Umumiy resurs muvaffaqiyatli yangilandi!")
            return redirect('resource_hub')
    else:
        form = GlobalLibraryForm(instance=resource)

    return render(request, 'core/edit_resource.html', {'form': form, 'title': 'Umumiy resursni tahrirlash'})


@login_required
def delete_global_resource(request, pk):
    resource = get_object_or_404(GlobalLibrary, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        resource.delete()
        messages.success(request, "Resurs o'chirib tashlandi.")
    return redirect('resource_hub')



# ====================================================================
# 8. --- DEPARTMENT RESOURCE EDIT/DELETE ---
# ====================================================================

@login_required
def edit_dept_resource(request, pk):
    resource = get_object_or_404(DepartmentResource, pk=pk, uploaded_by=request.user)

    if request.method == 'POST':
        form = DepartmentResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, "Kafedra resursi yangilandi!")
            return redirect('resource_hub')
    else:
        form = DepartmentResourceForm(instance=resource)

    return render(request, 'core/edit_resource.html', {'form': form, 'title': 'Kafedra resursini tahrirlash'})


@login_required
def delete_dept_resource(request, pk):
    resource = get_object_or_404(DepartmentResource, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        resource.delete()
        messages.success(request, "Kafedra resursi o'chirildi.")
    return redirect('resource_hub')