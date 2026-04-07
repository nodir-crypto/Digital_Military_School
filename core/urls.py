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

    # 7. TEST BUILDER (O'QITUVCHI UCHUN)
    path('instructor/quiz-builder/<int:lesson_id>/', views.quiz_builder, name='quiz_builder'),
    path('instructor/quiz-delete/<int:lesson_id>/', views.delete_quiz, name='delete_quiz'),

    # 8. KUTUBXONA VA RESURSLAR
    path('resources/', views.resource_hub, name='resource_hub'),
    path('resources/upload/', views.upload_resource, name='upload_resource'),

    # 9. DINAMIK AJAX (O'qituvchi fan tanlaganda kafedralarni yuklash)
    # MUHIM: add_lesson.html dagi fetch URL manzili aynan shu name bilan bog'lanadi
    path('ajax/get-departments/', views.get_departments_by_subject, name='get_departments_ajax'),

    # 10. Global resurslar uchun
    path('resource/global/<int:pk>/edit/', views.edit_global_resource, name='edit_global_resource'),
    path('resource/global/<int:pk>/delete/', views.delete_global_resource, name='delete_global_resource'),

    # 11.  Kafedra resurslari uchun
    path('resource/dept/<int:pk>/edit/', views.edit_dept_resource, name='edit_dept_resource'),
    path('resource/dept/<int:pk>/delete/', views.delete_dept_resource, name='delete_dept_resource'),
]