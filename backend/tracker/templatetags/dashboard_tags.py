from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def dashboard_url(context):
    request = context.get('request')
    if not request:
        return 'lead_dashboard'
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return 'lead_dashboard'
    if user.groups.filter(name__iexact='technician').exists() and not (user.is_staff or user.is_superuser):
        return 'tech_dashboard'
    return 'lead_dashboard'


