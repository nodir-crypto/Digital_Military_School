from django import forms
from django.contrib.auth import get_user_model
from .models import Lesson, Subject, Department, GlobalLibrary, DepartmentResource

User = get_user_model()

class ProfileEditForm(forms.ModelForm):
    """
    Foydalanuvchi profilini tahrirlash formasi (O'zgarishsiz qoldi).
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'avatar']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control rounded-pill px-4', 'placeholder': 'Ism'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control rounded-pill px-4', 'placeholder': 'Familiya'}),
            'email': forms.EmailInput(attrs={'class': 'form-control rounded-pill px-4', 'placeholder': 'example@mail.com'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = "Ism"
        self.fields['last_name'].label = "Familiya"
        self.fields['email'].label = "Elektron pochta"
        self.fields['avatar'].label = "Profil rasmi"


class LessonForm(forms.ModelForm):
    """
    Dars qo'shish va tahrirlash formasi (O'zgarishsiz qoldi).
    """
    class Meta:
        model = Lesson
        fields = ['subject', 'title', 'content', 'video', 'presentation', 'target_departments']
        widgets = {
            'target_departments': forms.CheckboxSelectMultiple(),
            'subject': forms.Select(attrs={'class': 'form-select rounded-pill px-3'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['subject'].queryset = Subject.objects.filter(instructors=user)
            if self.instance.pk and self.instance.subject:
                self.fields['target_departments'].queryset = self.instance.subject.available_in_departments.all()
            else:
                self.fields['target_departments'].queryset = Department.objects.all()

        self._apply_widget_styling()

    def _apply_widget_styling(self):
        for field_name, field in self.fields.items():
            if field_name == 'target_departments':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif field_name == 'subject':
                field.widget.attrs.update({'class': 'form-select rounded-pill px-3'})
            else:
                field.widget.attrs.update({'class': 'form-control rounded-4'})

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if video:
            valid_extensions = ['mp4', 'mkv', 'avi']
            ext = video.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError(f"Faqat quyidagi formatlarni yuklash mumkin: {', '.join(valid_extensions).upper()}")
        return video

    def clean_presentation(self):
        file = self.cleaned_data.get('presentation')
        if file:
            valid_extensions = ['pdf', 'pptx', 'ppt', 'docx']
            ext = file.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError(f"Faqat quyidagi fayllarni yuklash mumkin: {', '.join(valid_extensions).upper()}")
        return file


# ====================================================================
# YANGI QO'SHILGAN QISMLAR: KUTUBXONA FORMALARI
# ====================================================================

class GlobalLibraryForm(forms.ModelForm):
    class Meta:
        model = GlobalLibrary
        fields = ['title', 'file', 'image', 'file_type', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control rounded-pill px-4', 'placeholder': 'Resurs nomi'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select rounded-pill px-3'}), # form-select klassi shart
            'description': forms.Textarea(attrs={'class': 'form-control rounded-4', 'rows': 3}),
        }

class DepartmentResourceForm(forms.ModelForm):
    """Kafedra resurslarini qo'shish va tahrirlash uchun"""
    class Meta:
        model = DepartmentResource
        fields = ['title', 'file', 'image', 'file_type', 'department']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control rounded-pill px-4', 'placeholder': 'Resurs nomi'}),
            'department': forms.Select(attrs={'class': 'form-select rounded-pill px-3'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select rounded-pill px-3'}),
        }