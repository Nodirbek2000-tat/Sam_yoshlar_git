from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView

from apps.core.constants import Status

from .forms import OrganizationForm, ProblemAnswersForm, SolutionForm
from .models import (PROBLEM_QUESTIONS, Initiative, Organization, Problem,
                     Solution)


class IndexView(TemplateView):
    """/tashabbuslar — ikki yo'nalish kartasi."""

    template_name = 'initiatives/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        problems_total = Problem.objects.count()
        solved = Problem.objects.filter(status__in=[Status.DONE, Status.APPROVED]).count()
        solutions_total = Solution.objects.count()
        accepted = Solution.objects.filter(status=Status.APPROVED).count()

        context['voice_votes'] = Initiative.objects.aggregate(
            total=Sum('vote_count'))['total'] or 0
        context['voice_ideas'] = Initiative.objects.filter(is_published=True).count()

        context['cards'] = [
            {
                'title': "Tashabbus bildirish",
                'icon': 'ic-spark',
                'description': "Muammo, g'oya, taklif yoki startap fikringizni bildiring — "
                               "14 yo'nalishdan birini tanlang.",
                'details': "Har bir tashabbus reytingga tushadi. Ovoz ko'paygan sari "
                           "yo'nalishning tirik ekotizimi o'sib boradi.",
                'gradient': "linear-gradient(135deg, #0b1220 0%, #14243a 45%, #1b8a6b 100%)",
                'shadow': "rgba(53, 183, 166, 0.4)",
                'url': 'initiatives:youth',
                'featured': True,
                'stats': [
                    {'label': "Bildirilgan tashabbuslar", 'value': context['voice_ideas']},
                    {'label': "Berilgan ovozlar", 'value': context['voice_votes']},
                ],
            },
            {
                'title': "Yoshlar tashabbuslari",
                'icon': 'ic-trophy',
                'description': "Barcha tashabbuslar o'rinlar bo'yicha: eng ko'p ovoz olgani "
                               "birinchi o'rinda turadi.",
                'details': "Ovoz bering, taklif yozing — har bir yo'nalishning tirik ekotizimi "
                           "siz bilan birga o'sadi.",
                'gradient': "linear-gradient(135deg, #2E7D32 0%, #43A047 50%, #66BB6A 100%)",
                'shadow': "rgba(46, 125, 50, 0.35)",
                'url': 'initiatives:youth',
                'stats': [
                    {'label': "Bildirilgan tashabbuslar", 'value': context['voice_ideas']},
                    {'label': "Berilgan ovozlar", 'value': context['voice_votes']},
                ],
            },
            {
                'title': "Tashkilotlar",
                'icon': 'ic-bank',
                'description': "Tashkilotlar o'zlaridagi mavjud muammolarni aniq faktlar bilan "
                               "kiritadi. Yoshlar esa ularga yechim taklif etadi.",
                'details': "Jarayonlardagi to'siqlar, inson resurslari, texnologiya va boshqa "
                           "sohalar bo'yicha muammolarni ko'ring va taklif bering.",
                'gradient': "linear-gradient(135deg, #1565C0 0%, #1E88E5 50%, #42A5F5 100%)",
                'shadow': "rgba(21, 101, 192, 0.35)",
                'url': 'initiatives:problems',
                'stats': [
                    {'label': "Kiritilgan muammolar", 'value': problems_total},
                    {'label': "Berilgan takliflar", 'value': solutions_total},
                ],
            },
        ]
        return context


def organization_form(request):
    """/tashabbuslar/tashkilotlar — 11 qadamli anketa (bitta sahifa, JS qadamlari)."""
    if request.method == 'POST':
        org_form = OrganizationForm(request.POST)
        answers_form = ProblemAnswersForm(request.POST)
        if org_form.is_valid() and answers_form.is_valid():
            organization = org_form.save(commit=False)
            if request.user.is_authenticated:
                organization.user = request.user
            organization.save()
            answers_form.create_problems(organization)
            messages.success(request, "Muammolaringiz qabul qilindi!")
            return redirect('initiatives:organization_success')
        messages.error(request, "Formani to'liq to'ldiring — ba'zi maydonlarda xatolik bor.")
    else:
        org_form = OrganizationForm()
        answers_form = ProblemAnswersForm()

    steps = []
    for item in PROBLEM_QUESTIONS:
        steps.append({
            'number': item['number'] + 1,   # 1-qadam tashkilot ma'lumotlari
            'icon': item['icon'],
            'category': item['category'],
            'title': item['category'].label if hasattr(item['category'], 'label') else '',
            'question': item['question'],
            'field': answers_form[f"problem_{item['category']}"],
        })

    context = {
        'org_form': org_form,
        'answers_form': answers_form,
        'steps': steps,
        'total_steps': len(steps) + 1,
    }
    return render(request, 'initiatives/organizations.html', context)


def organization_success(request):
    return render(request, 'initiatives/organization_success.html')


def problem_list(request):
    """/tashabbuslar/muammolar — tashkilotlar kiritgan muammolar ro'yxati.

    Ko'rish hamma uchun ochiq. Taklif berish uchun ro'yxatdan o'tish kerak.
    """
    problems = (Problem.objects.filter(is_published=True)
                .select_related('organization')
                .annotate(solution_count=Count('solutions'))
                .order_by('-created_at'))

    return render(request, 'initiatives/problem_list.html', {
        'problems': problems,
        'total_problems': problems.count(),
        'total_solutions': Solution.objects.count(),
        'total_orgs': Organization.objects.count(),
    })


def problem_detail(request, pk):
    """/tashabbuslar/muammolar/<pk> — muammo va unga berilgan takliflar."""
    problem = get_object_or_404(
        Problem.objects.select_related('organization'), pk=pk, is_published=True,
    )

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, "Taklif berish uchun avval tizimga kiring.")
            return redirect_to_login(request.get_full_path())

        form = SolutionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            solution = form.save(commit=False)
            solution.problem = problem
            solution.author = request.user
            solution.save()
            messages.success(request, "Taklifingiz muvaffaqiyatli yuborildi!")
            return redirect('initiatives:solution_success')
        messages.error(request, "Formada xatolik bor — tekshirib qayta yuboring.")
    else:
        form = SolutionForm(user=request.user)

    return render(request, 'initiatives/problem_detail.html', {
        'problem': problem,
        'solutions': (problem.solutions
                      .filter(status=Status.APPROVED)
                      .select_related('author')
                      .order_by('-created_at')),
        'solutions_count': problem.solutions.count(),
        'form': form,
        'others': (Problem.objects.filter(is_published=True)
                   .exclude(pk=problem.pk)
                   .select_related('organization')
                   .annotate(solution_count=Count('solutions'))
                   .order_by('-created_at')[:4]),
    })


def solution_success(request):
    return render(request, 'initiatives/solution_success.html')
