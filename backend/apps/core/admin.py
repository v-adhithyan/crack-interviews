import csv
import io
import json

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from .models import Question, Submission, TestCase, TestCaseResult


class CsvImportForm(forms.Form):
    csv_file = forms.FileField(required=False, help_text="Upload a CSV file.")
    csv_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 14, "class": "vLargeTextField"}),
        help_text="Or paste CSV content here.",
    )
    replace_existing = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Delete existing test cases for this question before importing.",
    )

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get("csv_file")
        csv_text = cleaned_data.get("csv_text", "").strip()
        if not csv_file and not csv_text:
            raise ValidationError("Upload a CSV file or paste CSV content.")
        if csv_file and csv_text:
            raise ValidationError("Use either a CSV file or pasted CSV content, not both.")
        return cleaned_data

    def csv_content(self):
        csv_file = self.cleaned_data.get("csv_file")
        if csv_file:
            return csv_file.read().decode("utf-8-sig")
        return self.cleaned_data.get("csv_text", "")


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1
    fields = ["name", "stdin", "function_args", "expected_value", "expected_output", "is_sample", "is_hidden", "order"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["title", "difficulty", "execution_mode", "function_name", "is_active", "test_case_count", "test_case_csv", "created_at"]
    list_filter = ["difficulty", "execution_mode", "is_active"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TestCaseInline]
    change_form_template = "admin/core/question/change_form.html"
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "difficulty", "is_active")}),
        ("Execution", {"fields": ("execution_mode", "function_name")}),
        ("Starter code", {"fields": ("starter_code", "java_starter_code", "python_starter_code")}),
    )

    def test_case_count(self, obj):
        return obj.test_cases.count()

    def test_case_csv(self, obj):
        url = reverse("admin:core_question_import_test_cases", args=[obj.pk])
        return format_html('<a class="button" href="{}">Import CSV</a>', url)

    test_case_csv.short_description = "Test cases"

    def get_urls(self):
        return [
            path("<int:question_id>/import-test-cases/", self.admin_site.admin_view(self.import_test_cases), name="core_question_import_test_cases"),
            *super().get_urls(),
        ]

    def import_test_cases(self, request, question_id):
        question = self.get_object(request, question_id)
        if question is None:
            self.message_user(request, "Question not found.", level=messages.ERROR)
            return redirect("..")

        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                content = form.csv_content()
                reader = csv.DictReader(io.StringIO(content))
                required_fields = {"name", "expected_output", "is_sample", "is_hidden", "order"}
                missing_fields = required_fields - set(reader.fieldnames or [])
                if missing_fields:
                    self.message_user(
                        request,
                        f"Missing CSV columns: {', '.join(sorted(missing_fields))}.",
                        level=messages.ERROR,
                    )
                    return render(request, "admin/core/question/import_test_cases.html", {"form": form, "question": question})

                created = 0
                with transaction.atomic():
                    if form.cleaned_data["replace_existing"]:
                        question.test_cases.all().delete()
                    for row in reader:
                        function_args = row.get("function_args", "").strip()
                        expected_value = row.get("expected_value", "").strip()
                        TestCase.objects.create(
                            question=question,
                            name=row.get("name", ""),
                            stdin=row.get("stdin", ""),
                            function_args=json.loads(function_args) if function_args else None,
                            expected_value=json.loads(expected_value) if expected_value else None,
                            expected_output=row.get("expected_output", ""),
                            is_sample=row.get("is_sample", "").lower() in {"1", "true", "yes", "y"},
                            is_hidden=row.get("is_hidden", "true").lower() in {"1", "true", "yes", "y"},
                            order=int(row.get("order") or 0),
                        )
                        created += 1
                action = "Replaced and imported" if form.cleaned_data["replace_existing"] else "Imported"
                self.message_user(request, f"{action} {created} test cases.", level=messages.SUCCESS)
                return redirect(f"../../{question_id}/change/")
        else:
            form = CsvImportForm()

        return render(request, "admin/core/question/import_test_cases.html", {"form": form, "question": question})


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ["question", "name", "is_sample", "is_hidden", "order"]
    list_filter = ["is_sample", "is_hidden", "question"]
    search_fields = ["name", "question__title"]


class TestCaseResultInline(admin.TabularInline):
    model = TestCaseResult
    extra = 0
    can_delete = False
    readonly_fields = ["test_case", "status", "stdout", "stderr", "expected_output", "execution_time_ms"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["question", "kind", "language", "status", "passed_count", "total_count", "execution_time_ms", "solve_time_seconds", "created_at"]
    list_filter = ["kind", "language", "status", "question"]
    search_fields = ["question__title", "code"]
    readonly_fields = ["question", "kind", "language", "code", "status", "stdout", "stderr", "execution_time_ms", "solve_time_seconds", "passed_count", "total_count", "created_at"]
    inlines = [TestCaseResultInline]
