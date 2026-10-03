# Template changes

- Use double quotes in Django `translate` and `extends` tags (djLint T002).
- Always name closing blocks, for example `{% endblock content %}` (djLint T003).
- After editing Django templates, run `python -m djlint templates apps/main/templates --lint` and resolve reported errors before finishing. Keep lint rules enabled.
- Keep visible text translatable and update the Ukrainian catalog in `locale/uk/LC_MESSAGES/django.po`. Run `python scripts/compile_translations.py` after catalog changes.
- Preserve keyboard focus, disabled states, reduced motion and forced colors when styling form controls.

# UI design

- Use a modern, consistent design across application pages, with appropriate icons and semantic color accents for status indicators. Always include readable status text; do not rely on color alone.
- Follow the temperature control page structure: back link, page heading with related navigation/actions, then content sections. Keep related controller navigation in the heading, rather than a footer or side card.
- Keep section structure and spacing consistent across operational pages. Home, About, and Changelog pages may use layouts suited to their content.
- Keep buttons in each action group the same height and use consistent padding, icon spacing, and responsive wrapping.


# View and service architecture

- Organize HTML views in `apps/main/views/` by domain, following the structure of `apps/main/models/`; export public views from `views/__init__.py`.
- Organize API views in `apps/api/views/` by domain and export public views from `views/__init__.py`.
- For every app, create new views inside a `views/` package with domain modules; do not introduce standalone `views.py` or sibling `*_views.py` files.
- Keep JSON endpoints and responses in `apps/api` and register them in `apps/api/urls.py`. Do not return `JsonResponse` from main views.
- Extract logic shared by main and API into domain services in `apps/main/services/`. Services return data or raise domain errors; HTTP responses belong to views.
- Do not import main views into API views or services.
