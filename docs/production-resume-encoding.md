# Resume analysis: MySQL error 1366

The reported `Incorrect string value: '\xF0\x9F\x92\xB0...'` is the UTF-8
encoding of 💰. Legacy MySQL text columns can reject four-byte characters even
though Django's connection uses `charset=utf8mb4` (already set in prod.py).

Migration `product.0019_resume_text_utf8mb4` upgrades legacy CharField/TextField
columns on Resume, ResumeAnalysis and ResumeDraft, along with their table defaults.
It preserves field types/nullability and leaves keys and JSON columns alone.
Already-compatible columns are skipped. SQLite is unchanged. Reversing the
migration deliberately retains Unicode support to avoid losing stored characters.

## Production rollout

Deploy the commit containing this migration. The existing PythonAnywhere deployment
workflow already runs `manage.py migrate --noinput` before reloading the web app.
For a manual deployment, after updating the production checkout, run in its backend
directory using the production virtualenv and existing production environment:

```sh
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py showmigrations product
```

Confirm `[X] 0019_resume_text_utf8mb4`, reload the PythonAnywhere web app, and restart
the existing Django-Q always-on task if its code was updated. Use the normal database
backup process before migration; MySQL ALTER TABLE may rebuild/lock a populated table,
so schedule a low-traffic window for large tables.

To inspect the actual column encodings from the production MySQL console:

```sql
SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('product_resume', 'product_resumeanalysis', 'product_resumedraft')
  AND CHARACTER_SET_NAME IS NOT NULL;
```

Verify `job_description`, `resume_text`, `generated_prompt`, `parsed_text` and draft
`title` use `utf8mb4`. Retry the original job description containing 💰. Do not strip
emoji or disable strict SQL mode: that hides the schema issue or loses user input.

The attached traceback is dated August 22, 2026; it does not establish the current
production schema. The migration is safe to rerun and skips already-correct columns.
