import csv
import io

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import Question, Submission, TestCase, TestCaseResult


class CsvImportForm(forms.Form):
    csv_file = forms.FileField()


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1
    fields = ["name", "stdin", "expected_output", "is_sample", "is_hidden", "order"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["title", "difficulty", "is_active", "test_case_count", "created_at"]
    list_filter = ["difficulty", "is_active"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TestCaseInline]
    change_form_template = "admin/core/question/change_form.html"

    def test_case_count(self, obj):
        return obj.test_cases.count()

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
                content = form.cleaned_data["csv_file"].read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(content))
                created = 0
                for row in reader:
                    TestCase.objects.create(
                        question=question,
                        name=row.get("name", ""),
                        stdin=row.get("stdin", ""),
                        expected_output=row.get("expected_output", ""),
                        is_sample=row.get("is_sample", "").lower() in {"1", "true", "yes", "y"},
                        is_hidden=row.get("is_hidden", "true").lower() in {"1", "true", "yes", "y"},
                        order=int(row.get("order") or 0),
                    )
                    created += 1
                self.message_user(request, f"Imported {created} test cases.", level=messages.SUCCESS)
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
    list_display = ["question", "kind", "status", "passed_count", "total_count", "execution_time_ms", "created_at"]
    list_filter = ["kind", "status", "question"]
    search_fields = ["question__title", "code"]
    readonly_fields = ["question", "kind", "code", "status", "stdout", "stderr", "execution_time_ms", "passed_count", "total_count", "created_at"]
    inlines = [TestCaseResultInline]
