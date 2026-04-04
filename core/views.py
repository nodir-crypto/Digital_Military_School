from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect

# ###################################

from django.contrib.auth.decorators import login_required
from django.db.models import  Max
from .models import Subject, Lesson, Quiz, Choice, Question
from .forms import LessonForm, ProfileEditForm

import json
from django.db import transaction
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Lesson, Quiz, Question, Choice


@login_required
def delete_quiz(request, lesson_id):
    # Darsni va unga tegishli testni topamiz
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)

    if hasattr(lesson, 'quiz'):
        lesson.quiz.delete()  # Test o'chirilganda unga tegishli savollar (cascade) ham o'chadi
        messages.success(request, "Test muvaffaqiyatli o'chirildi va dars testsiz holatga qaytdi.")
    else:
        messages.error(request, "Ushbu darsda o'chirish uchun test topilmadi.")

    return redirect('instructor_dashboard')

@login_required
def quiz_builder(request, lesson_id):
    # 1. Havfsizlik: Faqat dars muallifi test yarata oladi
    lesson = get_object_or_404(Lesson, id=lesson_id, author=request.user)
    quiz = getattr(lesson, 'quiz', None)

    # 2. Mavjud savollarni JS uchun tayyorlash
    existing_questions = []
    if quiz:
        for q in quiz.questions.all().prefetch_related('choices'):
            existing_questions.append({
                'id': q.id,
                'text': q.text,
                'difficulty': q.difficulty,
                'explanation': q.explanation or '',
                'choices': [
                    {'text': c.text, 'is_correct': c.is_correct} for c in q.choices.all()
                ]
            })

    # 3. POST so'rovi (Saqlash mantiqi)
    if request.method == "POST":
        try:
            with transaction.atomic():
                # Quiz ob'ektini yaratish yoki yangilash
                quiz_title = request.POST.get('quiz_title', f"{lesson.title} testi")
                if not quiz:
                    quiz = Quiz.objects.create(lesson=lesson, title=quiz_title)
                else:
                    quiz.title = quiz_title
                    quiz.duration = request.POST.get('duration', 15)
                    quiz.save()
                    # Tozalash va qayta yozish strategiyasi (Senior uslubi)
                    quiz.questions.all().delete()

                # Savollarni saqlash
                total_q = int(request.POST.get('total_questions', 0))
                for i in range(1, total_q + 1):
                    q_text = request.POST.get(f'q_text_{i}')
                    if not q_text: continue  # O'chirilgan savollar o'tkazib yuboriladi

                    question = Question.objects.create(
                        quiz=quiz,
                        text=q_text,
                        difficulty=request.POST.get(f'difficulty_{i}', 'MEDIUM'),
                        explanation=request.POST.get(f'explanation_{i}', '')
                    )

                    # Variantlarni saqlash
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




# Dinamik User modelini olish
User = get_user_model()

from django.db.models import Avg, Count, Q  # Q ni qo'shish shart
from django.core.paginator import Paginator


@login_required
def home(request):
    user = request.user

    # 0. Qidiruv so'rovini olish
    search_query = request.GET.get('search', '').strip()

    if user.role == 'KURSANT':
        # 1. Asosiy filtr: Kursantning o'z kafedrasiga tegishli fanlar
        subject_list = Subject.objects.filter(department=user.department).order_by('-id')

        # 2. QIDIRUV MANTIQI
        if search_query:
            subject_list = subject_list.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            ).distinct()

        # 3. PAGINATION
        paginator = Paginator(subject_list, 6)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # AJAX uchun tayyorlanadigan minimal context
        context = {
            'subjects': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'search_query': search_query,
        }

        # --- MUHIM: AJAX SO'ROVINI TEKSHIRISH ---
        # Agar so'rov JavaScript (Live Search) orqali kelayotgan bo'lsa,
        # faqat fanlar ro'yxati qismini (partial) qaytaramiz.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'core/partials/subject_list_partial.html', context)
        # ----------------------------------------

        # 4. Analitika va Reyting logikasi (Faqat sahifa to'liq yuklanganda ishlaydi)
        user_attempts = QuizAttempt.objects.filter(user=user).order_by('-completed_at')
        avg_score = user_attempts.aggregate(Avg('score'))['score__avg'] or 0
        total_tests = user_attempts.count()
        recent_attempts = user_attempts[:5]

        top_3 = User.objects.filter(
            department=user.department,
            role='KURSANT'
        ).annotate(
            student_avg_score=Avg('quizattempt__score'),
            student_total_tests=Count('quizattempt')
        ).filter(student_total_tests__gt=0).order_by('-student_avg_score')[:3]

        lessons = Lesson.objects.filter(target_departments=user.department).distinct()

        # Barcha ma'lumotlarni context'ga qo'shamiz
        context.update({
            'lessons': lessons,
            'avg_score': avg_score,
            'total_tests': total_tests,
            'recent_attempts': recent_attempts,
            'top_3': top_3,
        })

        return render(request, 'core/home.html', context)

    elif user.role in ['INSTRUCTOR', 'COMMANDER']:
        return redirect('instructor_dashboard')

    return render(request, 'core/home.html')

@login_required
def student_analytics(request):
    all_attempts = QuizAttempt.objects.filter(user=request.user).order_by('completed_at')

    overview_stats = all_attempts.aggregate(
        avg_score=Avg('score'),
        best_score=Max('score'),
        total_attempts=Count('id')
    )

    subject_stats = QuizAttempt.objects.filter(user=request.user).values('quiz__title').annotate(
        avg_score=Avg('score')
    )

    timeline_data = {
        'labels': [attempt.completed_at.strftime('%d/%m') for attempt in all_attempts[:15]],
        'scores': [float(attempt.score) for attempt in all_attempts[:15]],
    }

    subject_data = {
        'labels': [stat['quiz__title'] for stat in subject_stats],
        'scores': [float(stat['avg_score']) for stat in subject_stats],
    }

    context = {
        'avg_score': overview_stats['avg_score'] or 0,
        'best_score': overview_stats['best_score'] or 0,
        'total_attempts': overview_stats['total_attempts'],
        'timeline_data_json': json.dumps(timeline_data),
        'subject_data_json': json.dumps(subject_data),
    }
    return render(request, 'core/analytics.html', context)

# ###################################

from django.db.models import Avg, Count

# 2. REYTING SAHIFASI
def ranking_view(request):
    # Har bir foydalanuvchining o'rtacha ballini hisoblash
    rankings = User.objects.filter(role='KURSANT').annotate(
        avg_score=Avg('quizattempt__score'),
        total_tests=Count('quizattempt')
    ).filter(total_tests__gt=0).order_by('-avg_score')

    top_3 = rankings[:3]
    others = rankings[3:]

    return render(request, 'core/ranking.html', {
        'top_3': top_3,
        'others': others
    })


####################################


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all().order_by('id')
    total_questions = questions.count()

    step_key = f'quiz_{quiz_id}_step'
    ans_key = f'quiz_{quiz_id}_answers'

    step = request.session.get(step_key, 0)

    # --- TEST YAKUNLANISHI VA HISOBLASH ---
    if step >= total_questions:
        user_answers = request.session.get(ans_key, {})
        correct_count = 0

        for question in questions:
            selected_choice_id = user_answers.get(str(question.id))
            if selected_choice_id:
                # Tanlangan variant to'g'riligini tekshiramiz
                is_correct = Choice.objects.filter(
                    id=selected_choice_id,
                    question=question,
                    is_correct=True
                ).exists()
                if is_correct:
                    correct_count += 1

        # Ballni foizda hisoblash (score = FloatField bo'lgani uchun)
        final_score = (correct_count / total_questions * 100) if total_questions > 0 else 0.0

        # Natijani bazaga saqlash
        # Modelingizdagi save() metodi avtomatik is_passed ni tekshiradi
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            score=final_score
        )

        # Natijalarni session'dan o'chirish
        request.session[step_key] = 0
        request.session[ans_key] = {}

        return redirect('quiz_result', quiz_id=quiz.id)

    # --- JORIY SAVOLNI KO'RSATISH ---
    current_question = questions[step]
    progress = int(((step + 1) / total_questions) * 100)

    if request.method == 'POST':
        selected_choice_id = request.POST.get('choice')
        if selected_choice_id:
            # Javobni session'ga yozish
            answers = request.session.get(ans_key, {})
            answers[str(current_question.id)] = selected_choice_id
            request.session[ans_key] = answers

            # Keyingi step'ga o'tish
            request.session[step_key] = step + 1
            return redirect('take_quiz', quiz_id=quiz.id)

    return render(request, 'quiz/take_quiz.html', {
        'quiz': quiz,
        'question': current_question,
        'step': step + 1,
        'total': total_questions,
        'progress': progress
    })


@login_required
def quiz_result(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    all_attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('-completed_at')

    current_attempt = all_attempts.first()  # Hozirgi
    best_attempt = all_attempts.order_by('-score').first()  # Rekord

    # Grafik uchun oxirgi 5 ta (eskidan yangiga)
    history = list(all_attempts[:5])
    history.reverse()

    context = {
        'quiz': quiz,
        'score': current_attempt.score,
        'is_passed': current_attempt.is_passed,
        'history': history,
        'best_score': best_attempt.score,
        'attempt': current_attempt,
    }
    return render(request, 'quiz/result.html', context)




# 2. Fanga tegishli darslar ro'yxati
@login_required
def subject_lessons(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    # 1. RUXSATLAR MANTIQI (O'zgarmadi)
    if request.user.role == 'KURSANT':
        # Kursant faqat o'z kafedrasiga ruxsat berilgan darslarni ko'radi
        lesson_list = subject.lessons.filter(target_departments=request.user.department).order_by('-created_at')
    else:
        # O'qituvchi va Komandir hamma darslarni ko'ra oladi
        lesson_list = subject.lessons.all().order_by('-created_at')

    # 2. SENIOR PAGINATION LOGIC
    # Har bir sahifada 9 ta dars ko'rsatamiz
    paginator = Paginator(lesson_list, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 3. CONTEXT (Template uchun ma'lumotlar)
    context = {
        'subject': subject,
        'lessons': page_obj, # Template-dagi {% for lesson in lessons %} tsikli uchun
        'page_obj': page_obj, # Pagination tugmalari uchun
        'is_paginated': page_obj.has_other_pages(), # Sahifalar 1 tadan ko'p bo'lsa True qaytaradi
    }

    return render(request, 'core/subject_lessons.html', context)


# 3. Darsning ichki sahifasi (Video va Konspekt)
# views.py ichida
@login_required
def lesson_detail(request, lesson_id):  # BU YERDA lesson_id BO'LISHI SHART
    lesson = get_object_or_404(Lesson, id=lesson_id)
    quiz = getattr(lesson, 'quiz', None)

    return render(request, 'core/lesson_detail.html', {
        'lesson': lesson,
        'quiz': quiz
    })

@login_required
def instructor_dashboard(request):
    # Faqat o'qituvchi va komandirlarga ruxsat
    if request.user.role not in ['INSTRUCTOR', 'COMMANDER']:
        return redirect('home')

    # O'qituvchining hamma fanlarini olish (Saralash uchun)
    teacher_subjects = Subject.objects.filter(instructors=request.user)

    # Tanlangan fanni olish (Query parameter orqali)
    selected_subject_id = request.GET.get('subject_filter')

    # Darslarni olish
    lessons = Lesson.objects.filter(author=request.user).order_by('-created_at')

    # Agar fan tanlangan bo'lsa, darslarni o'sha fan bo'yicha saralash
    if selected_subject_id:
        lessons = lessons.filter(subject_id=selected_subject_id)

    return render(request, 'core/instructor_dashboard.html', {
        'lessons': lessons,
        'teacher_subjects': teacher_subjects,
        'selected_subject_id': selected_subject_id,
    })

# 5. Yangi dars qo'shish
@login_required
def add_lesson(request):
    if request.user.role not in ['INSTRUCTOR', 'COMMANDER']:
        raise PermissionDenied("Siz dars qo'sha olmaysiz!")



    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.author = request.user  # Muallifni avtomatik biriktiramiz
            lesson.save()
            form.save_m2m()  # ManyToMany (Kafedralar) bog'liqligini saqlash uchun
            return redirect('instructor_dashboard')
    else:
        form = LessonForm(user=request.user)

    return render(request, 'core/add_lesson.html', {'form': form})


from django.db.models import Avg  # Ballarni o'rtachasini hisoblash uchun
from .models import QuizAttempt  # Test natijalari modeli


@login_required
def profile(request):
    user = request.user

    # Foydalanuvchining barcha urinishlarini bazadan olamiz
    user_attempts = QuizAttempt.objects.filter(user=user)

    # 1. O'rtacha natija (Hamma urinishlar bo'yicha)
    avg_score = user_attempts.aggregate(Avg('score'))['score__avg'] or 0

    # 2. Muvaffaqiyatli o'zlashtirilgan UNIKAL darslar soni
    # .values('quiz') -> faqat quiz IDlarini oladi
    # .distinct() -> takrorlanuvchi IDlarni (bitta darsni ko'p yechgan bo'lsa) bitta deb hisoblaydi
    passed_quizzes_count = user_attempts.filter(is_passed=True).values('quiz').distinct().count()

    # 3. Jami urinishlar soni (Bunga tegmadik, u o'z holicha qoladi)
    total_attempts = user_attempts.count()

    context = {
        'user': user,
        'avg_score': round(avg_score, 1),
        'passed_quizzes': passed_quizzes_count, # Endi bu raqam to'g'ri (unikal) chiqadi
        'total_attempts': total_attempts,
    }

    return render(request, 'core/profile.html', context)


# 7. Darsni tahrirlash (Ixtiyoriy lekin kerakli)
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
    # 1. Darsni bazadan qidiramiz
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # 2. Huquqlarni tekshiramiz:
    # - Foydalanuvchi Admin (Superuser) bo'lsa
    # - Yoki Foydalanuvchi Komandir bo'lsa
    # - Yoki Foydalanuvchi aynan shu darsning MUALLIFI bo'lsa
    if request.user.is_superuser or request.user.role == 'COMMANDER' or lesson.author == request.user:

        if request.method == 'POST':
            lesson.delete()
            return redirect('instructor_dashboard')

        # O'chirishni tasdiqlash sahifasi
        return render(request, 'core/confirm_delete.html', {'lesson': lesson})

    else:
        # Agar ruxsatsiz foydalanuvchi o'chirmoqchi bo'lsa (masalan, boshqa o'qituvchi)
        raise PermissionDenied("Sizda ushbu darsni o'chirish huquqi yo'q!")


@login_required
def profile_edit(request):
    if request.method == 'POST':
        # Post ma'lumotlari va fayllarni formaga beramiz
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # Profil ko'rish sahifasiga qaytadi
    else:
        # Eski ma'lumotlar bilan formani to'ldiramiz
        form = ProfileEditForm(instance=request.user)

    return render(request, 'core/profile_edit.html', {'form': form})
