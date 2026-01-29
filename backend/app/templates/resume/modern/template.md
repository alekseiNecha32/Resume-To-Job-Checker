# {{ name }}

{{ contact | join(' | ') }}

{% for section in sections %}
## {{ section.title }}

{% if section.id == 'professional-summary' %}
{{ section.get('items', []) | map(attribute='text') | join(' ') }}
{% else %}
{% for item in section.get('items', []) %}
- {{ item.text }}
{% endfor %}
{% endif %}

{% endfor %}
