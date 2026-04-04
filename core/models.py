from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models


class Quiz(models.Model):
    lesson = models.OneToOneField('Lesson', on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255)
    # Professional funksiya: Test uchun umumiy vaqt (minutda)
    duration = models.PositiveIntegerField(default=15, help_text="Testni yechish uchun ajratilgan vaqt (minutda)")
    pass_percentage = models.PositiveIntegerField(default=70, validators=[MaxValueValidator(100)])

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"

    def __str__(self):
        return f"{self.title} | {self.lesson.title}"


class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('EASY', 'Oson'),
        ('MEDIUM', 'O\'rtacha'),
        ('HARD', 'Qiyin'),
    ]
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    # Professional funksiya: Savolga tushuntirish (testdan so'ng xatosini ko'rishi uchun)
    explanation = models.TextField(blank=True, null=True, help_text="To'g'ri javobga izoh")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='MEDIUM')

    def __str__(self):
        return self.text[:100]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField()
    is_passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # O'tish balini tekshirish mantig'i
        self.is_passed = self.score >= self.quiz.pass_percentage
        super().save(*args, **kwargs)

# ###########################################333
def validate_video_size(value):
    filesize = value.size
    # Maksimal hajm: 100 MB (100 * 1024 * 1024 byte)
    if filesize > 104857600:
        raise ValidationError("Video hajmi 100 MB dan oshmasligi kerak!")

def validate_file_size(value):
    filesize = value.size
    # Maksimal hajm: 10 MB (Taqdimotlar uchun)
    if filesize > 10485760:
        raise ValidationError("Fayl hajmi 10 MB dan oshmasligi kerak!")


# 1. Kafedralar modeli
class Department(models.Model):
    name = models.CharField("Kafedra nomi", max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kafedra"
        verbose_name_plural = "Kafedralar"


# 2. Foydalanuvchi modeli (Custom User)
class User(AbstractUser):
    ROLE_CHOICES = (
        ('KURSANT', 'Kursant'),
        ('INSTRUCTOR', 'Instruktor'),
        ('COMMANDER', 'Komandir')
    )

    role = models.CharField("Roli", max_length=20, choices=ROLE_CHOICES, default='KURSANT')
    rank = models.CharField("Harbiy unvon", max_length=50, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name="Tegishli kafedrasi"
    )
    # O'qituvchi qaysi kafedralarga dars berish huquqiga ega (Rollar uchun muhim)
    teaches_in = models.ManyToManyField(
        Department,
        blank=True,
        related_name='instructors_list',
        verbose_name="Dars beradigan kafedralari"
    )
    avatar = models.ImageField("Profil rasmi", upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        # Ism-familiya bo'lsa shuni, bo'lmasa usernameni qaytaradi
        if self.first_name and self.last_name:
            return f"{self.rank} {self.last_name} {self.first_name}"
        return self.username


# 3. Fanlar modeli
class Subject(models.Model):
    name = models.CharField("Fan nomi", max_length=200)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name="Kafedra"
    )
    # Fanga biriktirilgan o'qituvchilar
    instructors = models.ManyToManyField(
        User,
        limit_choices_to={'role': 'INSTRUCTOR'},
        blank=True,
        related_name='assigned_subjects',
        verbose_name="Mas'ul o'qituvchilar"
    )
    description = models.TextField("Fan haqida", blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"


# 4. Darslar modeli
class Lesson(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name="Mas'ul Fan"
    )
    title = models.CharField("Dars mavzusi", max_length=255)
    content = models.TextField("Dars matni (Konspekt)", blank=True, null=True)
    video = models.FileField("Video darslik", upload_to='videos/', null=True, blank=True)
    presentation = models.FileField("Taqdimot fayli", upload_to='slides/', null=True, blank=True)

    # Qaysi kafedra kursantlari bu darsni ko'ra oladi?
    target_departments = models.ManyToManyField(
        Department,
        related_name='visible_lessons',
        verbose_name="Ko'ra oladigan kafedralar"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_lessons',
        verbose_name="Muallif"
    )

    video = models.FileField(
        upload_to='lessons/videos/',
        null=True,
        blank=True,
        validators=[validate_video_size]  # Tekshiruv qo'shildi
    )
    presentation = models.FileField(
        upload_to='lessons/files/',
        null=True,
        blank=True,
        validators=[validate_file_size]  # Tekshiruv qo'shildi
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ['-created_at']  # Yangi darslar har doim tepada chiqadi

