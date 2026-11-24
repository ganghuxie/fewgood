from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_auth_menu_binds_all_events_after_dialog_is_moved_to_body():
    source = (ROOT / 'site/src/components/AuthMenu.astro').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', source, flags=re.DOTALL).group(1)
    after_append = script.split('document.body.append(backdrop, dialog);', 1)[1]

    for binding in (
        "login.addEventListener('click'",
        "closeButtons.forEach(button => button.addEventListener('click'",
        "form.addEventListener('submit'",
        "dialog.querySelector('[data-auth-forgot]').addEventListener('click'",
        "recoveryForm.addEventListener('submit'",
        "dialog.querySelectorAll('[data-auth-oauth]').forEach(button => button.addEventListener('click'",
        "root.querySelector('[data-auth-signout]').addEventListener('click'",
    ):
        assert binding in after_append

    moved_control_queries = re.compile(
        r"root\.querySelector(?:All)?\(\s*['\"]\[data-auth-(?:forgot|oauth)\]"
    )
    assert not moved_control_queries.search(after_append)
    assert "dialog.querySelector('[name=email]').value.trim()" in after_append
