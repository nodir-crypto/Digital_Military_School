from django.urls import path
from . import views

urlpatterns = [
    # 1. ASOSIY VA DASHBOARD
    path('', views.home, name='home'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),

    # 2. FANLAR VA DARSLAR (KURSANT/O'QITUVCHI)
    path('subject/<int:subject_id>/', views.subject_lessons, name='subject_lessons'),
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),

    # 3. DARSLAR BILAN ISHLASH (O'QITUVCHI - CRUD)
    path('instructor/add-lesson/', views.add_lesson, name='add_lesson'),
    path('lesson/<int:lesson_id>/edit/', views.edit_lesson, name='edit_lesson'),
    path('lesson/<int:lesson_id>/delete/', views.delete_lesson, name='delete_lesson'),

    # 4. PROFIL VA TAHRIRLASH
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # 5. TEST TIZIMI (QUIZ)
    path('quiz/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('quiz/<int:quiz_id>/result/', views.quiz_result, name='quiz_result'),

    # 6. ANALITIKA VA REYTING (Yangi funksiyalar)
    path('statistics/', views.student_analytics, name='student_analytics'),
    path('ranking/', views.ranking_view, name='ranking_view'),

    path('instructor/quiz-builder/<int:lesson_id>/', views.quiz_builder, name='quiz_builder'),
    path('instructor/quiz-delete/<int:lesson_id>/', views.delete_quiz, name='delete_quiz'),
]