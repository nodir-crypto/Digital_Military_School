from django.db.models import Avg, Count
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
from .models import OfficialMessage  # Rasmiy xabarlar modeli


def ranking_context(request):
    """
    Kursantning umumiy reytingdagi o'rnini hisoblaydi.
    Mavjud funksionallik to'liq saqlab qolindi.
    """
    User = get_user_model()
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'KURSANT':
        # Reytingni hisoblash (Faqat test topshirgan kursantlar uchun)
        rankings = User.objects.filter(role='KURSANT').annotate(
            avg_score=Avg('quizattempt__score'),
            total_tests=Count('quizattempt')
        ).filter(total_tests__gt=0).order_by('-avg_score')

        user_rank = 0
        total_students = rankings.count()

        for i, student in enumerate(rankings, 1):
            if student.id == request.user.id:
                user_rank = i
                break

        return {
            'user_rank': user_rank,
            'total_students': total_students,
        }
    return {}


def notification_context(request):
    """
    Institut va Kafedra boshliqlari uchun o'qilmagan xabarlar sonini hisoblaydi.
    """
    if request.user.is_authenticated:
        # User modelidagi related_name orqali o'qilmagan xabarlar sonini olish
        unread_count = OfficialMessage.objects.filter(
            receiver=request.user,
            is_read=False
        ).count()
        return {'unread_notifications': unread_count}
    return {'unread_notifications': 0}


def system_status_context(request):
    """
    Tizimning umumiy holati (online foydalanuvchilar va boshqalar).
    Faqat boshqaruv xodimlari uchun ma'lumot uzatadi.
    """
    User = get_user_model()
    context = {}

    if request.user.is_authenticated and request.user.role in ['INST_HEAD', 'DEPT_HEAD']:
        # Oxirgi 5 daqiqada faol bo'lganlar
        five_minutes_ago = timezone.now() - datetime.timedelta(minutes=5)
        context['online_users_count'] = User.objects.filter(last_online__gte=five_minutes_ago).count()

    return context