from django.urls import path
from .views import RegisterView, CheckCreditRiskScoreView, CheckTotalOutstandingLoanView, EmailCreditViewReportView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('check-credit-score/', CheckCreditRiskScoreView.as_view(), name='check_credit_risk_score'),
    path('check-total-outstanding-loan/', CheckTotalOutstandingLoanView.as_view(), name='check_total_outstanding_loan'),
    path('email-creditview-report/', EmailCreditViewReportView.as_view(), name='email_creditview_report'),

]
