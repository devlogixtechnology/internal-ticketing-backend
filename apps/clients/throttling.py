from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

class OnboardingRateThrottle(UserRateThrottle):
    scope = 'onboarding'
    rate = '10/minute'