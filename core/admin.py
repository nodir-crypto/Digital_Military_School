from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Department, User, Lesson, Subject
from .models import Quiz, Question, Choice, QuizAttempt

# 1. Javob variantlarini savolning ichida ko'rsatish (Inline)
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4  # Default holatda 4 ta bo'sh qator chiqaradi (A, B, C, D variantlar uchun)
    max_num = 10 # Maksimal 10 tagacha variant qo'shish mumkin

# 2. Savollarni Quiz (Test) ichida ko'rsatish
class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True # Savolni alohida tahrirlashga havola beradi

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'duration', 'pass_percentage', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'lesson__title']
    inlines = [QuestionInline] # Test yaratayotganda savollarni ham shu yerda qo'shish mumkin

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'difficulty']
    list_filter = ['quiz', 'difficulty']
    search_fields = ['text', 'quiz__title']
    inlines = [ChoiceInline] # Savol yaratayotganda variantlarni shu yerda qo'shish mumkin

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'score', 'is_passed', 'completed_at']
    list_filter = ['is_passed', 'completed_at', 'quiz']
    search_fields = ['user__username', 'quiz__title']
    readonly_fields = ['completed_at'] # Natija o'zgartirilmasligi uchun faqat o'qishga (Read-only) qilamiz

# Agar Choice alohida ko'rinishi kerak bo'lsa (ixtiyoriy)
# admin.site.register(Choice)

# 1. Kafedralar (Department)
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


# 2. Foydalanuvchilar (User) - Parol va Harbiy ma'lumotlar bilan ishlash
class CustomUserAdmin(UserAdmin):
    # Asosiy ro'yxatda ko'rinadigan ustunlar
    list_display = ('username', 'last_name', 'first_name', 'rank', 'role', 'department', 'is_staff')

    # Filtrlash paneli (o'ng tomonda)
    list_filter = ('role', 'rank', 'department', 'is_staff')

    # Foydalanuvchini tahrirlashda qo'shimcha maydonlarni qo'shish
    fieldsets = UserAdmin.fieldsets + (
        ('Harbiy ma’lumotlar', {'fields': ('role', 'rank', 'department', 'avatar')}),
    )

    # Yangi foydalanuvchi yaratishda qo'shimcha maydonlar
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Harbiy ma’lumotlar', {'fields': ('role', 'rank', 'department', 'avatar')}),
    )


# Foydalanuvchi modelini Custom admin bilan bog'lash
admin.site.register(User, CustomUserAdmin)


# 3. Fanlar (Subject)
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'get_instructors')
    list_filter = ('department',)
    search_fields = ('name',)
    # O'qituvchilarni tanlash uchun qulay interfeys
    filter_horizontal = ('instructors',)

    # Jadvalda o'qituvchilarni ko'rsatish uchun yordamchi funksiya
    def get_instructors(self, obj):
        return ", ".join([u.last_name for u in obj.instructors.all()])

    get_instructors.short_description = "Mas'ul o'qituvchilar"


# 4. Darslar (Lesson)
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'author', 'created_at')
    list_filter = ('subject', 'author', 'target_departments')
    search_fields = ('title', 'content')
    # Kafedralarni tanlashni osonlashtiradi
    filter_horizontal = ('target_departments',)
    # Avtomatik sana ierarxiyasi
    date_hierarchy = 'created_at'