import os
import secrets
import datetime
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models


# ###########################################
# VALIDATORS (O'zgarishsiz qoldi)
# ###########################################

def validate_video_size(value):
    if value.size > 104857600:
        raise ValidationError("Video hajmi 100 MB dan oshmasligi kerak!")


def validate_file_size(value):
    if value.size > 10485760:
        raise ValidationError("Fayl hajmi 10 MB dan oshmasligi kerak!")


# ###########################################
# KAFEDRA VA FOYDALANUVCHI (PROFESSIONAL QO'SHIMCHALAR)
# ###########################################

class Department(models.Model):
    name = models.CharField("Kafedra nomi", max_length=100)
    logo = models.ImageField("Kafedra logotipi", upload_to='dept_logos/', null=True, blank=True)
    description = models.TextField("Kafedra haqida qisqacha", blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kafedra"
        verbose_name_plural = "Kafedralar"


class User(AbstractUser):
    # SENIOR TIP: Rollarni o'zgaruvchi (constant) sifatida saqlash xatolikni oldini oladi
    KURSANT = 'KURSANT'
    INSTRUCTOR = 'INSTRUCTOR'
    DEPT_HEAD = 'DEPT_HEAD'
    INST_HEAD = 'INST_HEAD'

    ROLE_CHOICES = (
        (KURSANT, 'Kursant'),
        (INSTRUCTOR, 'Instruktor'),
        (DEPT_HEAD, 'Kafedra Boshlig\'i'),
        (INST_HEAD, 'Institut Boshlig\'i'),
    )

    # verbose_name qo'shildi, bu admin panelda ustun nomini chiroyli ko'rsatadi
    role = models.CharField(
        "Foydalanuvchi Roli",
        max_length=21,
        choices=ROLE_CHOICES,
        default=KURSANT
    )
    rank = models.CharField("Harbiy unvon", max_length=50, blank=True)

    is_starshina = models.BooleanField("Starshina statusi", default=False)
    last_online = models.DateTimeField("Oxirgi faollik", null=True, blank=True)

    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='members', verbose_name="Tegishli kafedrasi"
    )
    teaches_in = models.ManyToManyField(
        Department, blank=True, related_name='instructors_list',
        verbose_name="Dars beradigan kafedralari"
    )
    avatar = models.ImageField("Profil rasmi", upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.rank} {self.last_name} {self.first_name}"
        return self.username


# ###########################################
# COMMAND MESSAGING (BUYRUQ VA XABARLAR)
# ###########################################

class OfficialMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_official_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_official_messages')
    subject = models.CharField("Xabar mavzusi", max_length=255, blank=True)
    body = models.TextField("Xabar matni")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.created_at.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name = "Rasmiy Xabar"
        verbose_name_plural = "Rasmiy Xabarlar"
        ordering = ['-created_at']


# ###########################################
# FANLAR MODELI
# ###########################################

class Subject(models.Model):
    name = models.CharField("Fan nomi", max_length=200)
    available_in_departments = models.ManyToManyField(
        Department,
        related_name='subjects',
        verbose_name="Ushbu fan o'qitiladigan kafedralar",
        help_text="Tarix fanini qaysi kafedralar ko'ra olishini belgilang"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='old_subjects',
        verbose_name="Asosiy kafedra (Eski)", null=True, blank=True
    )
    instructors = models.ManyToManyField(
        User, limit_choices_to={'role': 'INSTRUCTOR'},
        blank=True, related_name='assigned_subjects',
        verbose_name="Mas'ul o'qituvchilar"
    )
    description = models.TextField("Fan haqida", blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"


# ###########################################
# DARSLAR MODELI
# ###########################################

class Lesson(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='lessons', verbose_name="Mas'ul Fan"
    )
    title = models.CharField("Dars mavzusi", max_length=255)
    content = models.TextField("Dars matni (Konspekt)", blank=True, null=True)

    target_departments = models.ManyToManyField(
        Department, related_name='visible_lessons', verbose_name="Ko'ra oladigan kafedralar"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_lessons', verbose_name="Muallif"
    )
    video = models.FileField(
        upload_to='lessons/videos/', null=True, blank=True, validators=[validate_video_size]
    )
    presentation = models.FileField(
        upload_to='lessons/files/', null=True, blank=True, validators=[validate_file_size]
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ['-created_at']


# ###########################################
# TESTLAR TIZIMI
# ###########################################

class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255)
    duration = models.PositiveIntegerField(default=15, help_text="Test vaqti (minut)")
    pass_percentage = models.PositiveIntegerField(default=70, validators=[MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} | {self.lesson.title}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    explanation = models.TextField(blank=True, null=True)
    difficulty = models.CharField(max_length=10, choices=[('EASY', 'Oson'), ('MEDIUM', 'O\'rtacha'), ('HARD', 'Qiyin')],
                                  default='MEDIUM')


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)


class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField()
    is_passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.is_passed = self.score >= self.quiz.pass_percentage
        super().save(*args, **kwargs)


# ###########################################
# RESURSLAR VA KUTUBXONA
# ###########################################

FILE_TYPE_CHOICES = [
    ('pdf', 'PDF Kitob'),
    ('doc', 'Word hujjat'),
    ('video', 'Video darslik'),
    ('audio', 'Audio darslik'),
    ('ppt', 'Prezentatsiya'),
]


class BaseResource(models.Model):
    title = models.CharField("Resurs nomi", max_length=255)
    file = models.FileField("Fayl", upload_to='resources/%Y/%m/', validators=[validate_file_size])
    file_type = models.CharField("Fayl turi", max_length=10, choices=FILE_TYPE_CHOICES, default='pdf')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class DepartmentResource(BaseResource):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='dept_resources')
    image = models.ImageField("Muqova", upload_to='resource_covers/', null=True, blank=True)


class GlobalLibrary(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='resources/%Y/%m/')
    image = models.ImageField(upload_to='resource_covers/', null=True, blank=True)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='pdf')
    description = models.TextField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


# ###########################################
# Password reset
# ###########################################

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_valid(self):
        expiration_time = self.created_at + datetime.timedelta(minutes=10)
        return not self.is_verified and timezone.now() < expiration_time

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)