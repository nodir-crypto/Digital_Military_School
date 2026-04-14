from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

# Senior Note: handler404 ni import qilish shart emas,
# u shunchaki o'zgaruvchi sifatida aniqlanadi.
from django.conf.urls import handler404

urlpatterns = [
    path('login-success/', views.login_success, name='login_success'),

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

    # 6. ANALITIKA VA REYTING
    path('statistics/', views.student_analytics, name='student_analytics'),
    path('ranking/', views.ranking_view, name='ranking_view'),

    # 7. TEST BUILDER (O'QITUVCHI UCHUN)
    path('instructor/quiz-builder/<int:lesson_id>/', views.quiz_builder, name='quiz_builder'),
    path('instructor/quiz-delete/<int:lesson_id>/', views.delete_quiz, name='delete_quiz'),

    # 8. KUTUBXONA VA RESURSLAR
    path('resources/', views.resource_hub, name='resource_hub'),
    path('resources/upload/', views.upload_resource, name='upload_resource'),

    # 9. DINAMIK AJAX
    path('ajax/get-departments/', views.get_departments_by_subject, name='get_departments_ajax'),

    # 10. GLOBAL RESURSLAR CRUD
    path('resource/global/<int:pk>/edit/', views.edit_global_resource, name='edit_global_resource'),
    path('resource/global/<int:pk>/delete/', views.delete_global_resource, name='delete_global_resource'),

    # 11. KAFEDRA RESURSLARI CRUD
    path('resource/dept/<int:pk>/edit/', views.edit_dept_resource, name='edit_dept_resource'),
    path('resource/dept/<int:pk>/delete/', views.delete_dept_resource, name='delete_dept_resource'),

    # 12. PASSWORD RESET (OTP TIZIMI)
    path('forget-password/', views.forget_password_view, name='forget_password'),
    path('verify-otp/<str:token>/', views.verify_otp_view, name='verify_otp'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),

    # 13. INSTITUT BOSHQARUVI (MANAGEMENT)
    path('management/', views.management_dashboard, name='management_dashboard'),
    path('management/dept/<int:dept_id>/', views.department_detail_view, name='department_detail_view'),
    path('management/subject/<int:subject_id>/dept/<int:dept_id>/', views.subject_performance_detail, name='subject_performance_detail'),
    path('management/message/send/', views.send_official_message, name='send_official_message'),

    # 13. KAFEDIRA BOSHQARUVI (MANAGEMENT)
    path('management/dept-head/', views.dept_head_dashboard, name='dept_head_dashboard'),
    path('management/mark-read/<int:message_id>/', views.mark_order_as_read, name='mark_order_as_read'),
    path('management/send-notice/', views.send_dept_notice, name='send_dept_notice'),


    path('management/user-details/<int:user_id>/', views.get_user_details, name='get_user_details'),
]

# 404 xatolikni ushlab qoluvchi handler
handler404 = 'core.views.custom_404_handler'

# Senior Tip: Development rejimida static va media fayllarni qo'shish shart.
# Usiz kafedra logotiplari va video darslar brauzerda yuklanmaydi.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)