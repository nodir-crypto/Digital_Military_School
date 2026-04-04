


from django import forms
from .models import Lesson, Subject, Department
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        # Modelda bor maydonlarni aniq ko'rsatamiz
        fields = ['first_name', 'last_name', 'avatar','email']

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control rounded-pill px-4',
                'placeholder': 'Ism'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control rounded-pill px-4',
                'placeholder': 'example@mail.com'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control rounded-pill px-4',
                'placeholder': 'Familiya'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
            }),
        }

    def __init__(self, *args, **kwargs):
        super(ProfileEditForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].label = "Ism"
        self.fields['last_name'].label = "Familiya"
        self.fields['avatar'].label = "Profil rasmi"


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['subject', 'title', 'content', 'video', 'presentation', 'target_departments']

        widgets = {
            'target_departments': forms.CheckboxSelectMultiple(),  # Checkbox ga qaytdik
            'subject': forms.Select(attrs={'class': 'form-select rounded-pill px-3'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # O'qituvchi faqat o'ziga biriktirilgan fanlarni ko'rishi uchun
        if user:
            # 1. O'qituvchi faqat o'zi biriktirilgan fanlarni ko'radi (Sizdagi kod)
            self.fields['subject'].queryset = Subject.objects.filter(instructors=user)

            # 2. O'qituvchi faqat o'z kafedrasini tanlay oladigan qilish (Yangi qo'shiladi)
            if user.department:
                self.fields['target_departments'].queryset = Department.objects.filter(id=user.department.id)
                # Avtomatik tanlangan holatda turishi uchun:
                self.fields['target_departments'].initial = [user.department.id]

        # Har bir maydonga chiroyli klass qo'shamiz
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

        # Checkboxlar uchun alohida klass
        self.fields['target_departments'].widget.attrs.update({'class': 'form-check-input'})

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if video:
            extension = video.name.split('.')[-1].lower()
            if extension not in ['mp4', 'mkv', 'avi']:
                raise forms.ValidationError("Faqat MP4, MKV yoki AVI formatidagi videolarni yuklash mumkin!")
        return video

    def clean_presentation(self):
        file = self.cleaned_data.get('presentation')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['pdf', 'pptx', 'ppt', 'docx']:
                raise forms.ValidationError("Faqat PDF, PPTX yoki DOCX formatidagi fayllarni yuklash mumkin!")
        return file

