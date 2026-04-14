from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import (
    Department, User, Lesson, Subject,
    DepartmentResource, GlobalLibrary,
    Quiz, Question, Choice, QuizAttempt, OfficialMessage
)

# ###########################################
# 1. TEST TIZIMI INLINE'LARI
# ###########################################
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    max_num = 10


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True


# ###########################################
# 2. TEST MODELLARI ADMINI
# ###########################################
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'duration', 'pass_percentage', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'lesson__title']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'difficulty']
    list_filter = ['quiz', 'difficulty']
    search_fields = ['text', 'quiz__title']
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'score', 'is_passed', 'completed_at']
    list_filter = ['is_passed', 'completed_at', 'quiz']
    search_fields = ['user__username', 'quiz__title']
    readonly_fields = ['completed_at']


# ###########################################
# 3. KAFEDRA ADMINI
# ###########################################
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


# ###########################################
# 4. CUSTOM USER ADMIN (PROFESSIONAL FIX)
# ###########################################
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Senior Fix: 'admin.site.register' o'rniga '@admin.register' dekoratori ishlatildi.
    Rollar va Harbiy ma'lumotlar qismi markazlashtirildi.
    """
    list_display = ('username', 'last_name', 'first_name', 'rank', 'role', 'department', 'is_staff')
    list_filter = ('role', 'rank', 'department', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'rank') # Qidiruv qo'shildi

    fieldsets = UserAdmin.fieldsets + (
        ('Harbiy ma’lumotlar', {'fields': ('role', 'rank', 'department', 'teaches_in', 'avatar', 'is_starshina')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Harbiy ma’lumotlar', {'fields': ('role', 'rank', 'department', 'teaches_in', 'avatar', 'is_starshina')}),
    )

    filter_horizontal = ('teaches_in', 'groups', 'user_permissions')


# ###########################################
# 5. FANLAR ADMINI
# ###########################################
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_departments', 'get_instructors')
    list_filter = ('available_in_departments',)
    search_fields = ('name',)
    filter_horizontal = ('available_in_departments', 'instructors')

    def get_instructors(self, obj):
        return ", ".join([u.last_name for u in obj.instructors.all()])
    get_instructors.short_description = "Mas'ul o'qituvchilar"

    def get_departments(self, obj):
        return ", ".join([d.name for d in obj.available_in_departments.all()])
    get_departments.short_description = "O'qitiladigan Kafedralar"


# ###########################################
# 6. DARSLAR ADMINI
# ###########################################
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'author', 'created_at')
    list_filter = ('subject', 'author', 'target_departments')
    search_fields = ('title', 'content')
    filter_horizontal = ('target_departments',)
    date_hierarchy = 'created_at'


# ###########################################
# 7. RESURSLAR VA KUTUBXONA
# ###########################################
class BaseResourceAdmin(admin.ModelAdmin):
    """Barcha resurslar uchun umumiy klas (DRY prinsipi)"""
    search_fields = ('title', 'uploaded_by__username')
    list_filter = ('file_type', 'created_at')
    date_hierarchy = 'created_at'
    list_per_page = 20

    def download_btn(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" class="btn btn-sm" style="background-color: #10b981; color:white; padding: 2px 10px; border-radius: 5px; text-decoration:none;" download>Yuklash</a>',
                obj.file.url
            )
        return "Fayl yo'q"
    download_btn.short_description = 'Hujjat'

    def type_badge(self, obj):
        colors = {'pdf': '#ef4444', 'doc': '#3b82f6', 'ppt': '#f59e0b', 'video': '#8b5cf6', 'audio': '#10b981'}
        color = colors.get(obj.file_type, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.file_type.upper()
        )
    type_badge.short_description = 'Format'


@admin.register(DepartmentResource)
class DepartmentResourceAdmin(BaseResourceAdmin):
    list_display = ('get_thumbnail', 'title', 'department', 'type_badge', 'uploaded_by', 'download_btn')
    list_filter = BaseResourceAdmin.list_filter + ('department',)

    def get_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 40px; height: 55px; border-radius: 4px; object-fit: cover;" />',
                obj.image.url)
        return "—"
    get_thumbnail.short_description = 'Muqova'

    fieldsets = (
        ('Asosiy ma\'lumotlar', {'fields': ('title', 'department', 'uploaded_by')}),
        ('Fayl va Muqova', {'fields': ('file', 'image', 'file_type')}),
    )


@admin.register(GlobalLibrary)
class GlobalLibraryAdmin(BaseResourceAdmin):
    list_display = ('title', 'type_badge', 'uploaded_by', 'created_at', 'download_btn')
    fieldsets = (
        ('Asosiy ma\'lumotlar', {'fields': ('title', 'description', 'uploaded_by')}),
        ('Fayl sozlamalari', {'fields': ('file', 'file_type')}),
    )


# ###########################################
# 8. RASMIY XABARLAR ADMINI
# ###########################################
@admin.register(OfficialMessage)
class OfficialMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'receiver__username', 'subject')