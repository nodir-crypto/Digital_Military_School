from django.db.models import Avg, Count
from django.contrib.auth import get_user_model


def ranking_context(request):
    User = get_user_model()
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'KURSANT':
        # Reytingni hisoblash
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