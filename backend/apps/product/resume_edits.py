"""Exact, field-scoped edits against an immutable analyzed builder snapshot."""
import copy
import hashlib
import json
from collections import Counter

from django.core.exceptions import ValidationError
from .resume_builder import validate_content


def editable_targets(snapshot):
    if not snapshot:
        return {}
    validate_content(snapshot['content'])
    content = snapshot['content']
    targets = {'summary': content['summary']} if content['summary'] else {}
    for job, entry in enumerate(content['experience']):
        for line, text in enumerate(entry['bullets'].splitlines(keepends=True)):
            original = text.rstrip('\r\n')
            if original.strip():
                targets[f'experience_{job}_bullet_{line}'] = original
    return targets


def validate_edit_shape(edits):
    if not isinstance(edits, list) or len(edits) > 100:
        raise ValidationError('resume_edits must be a list of at most 100 edits.')
    limits = {'target_id': 100, 'original': 8000, 'replacement': 8000, 'reason': 2000}
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != set(limits):
            raise ValidationError('Each resume edit requires target_id, original, replacement and reason.')
        for key, limit in limits.items():
            if not isinstance(edit[key], str) or not edit[key].strip() or len(edit[key]) > limit:
                raise ValidationError(f'Invalid resume edit {key}.')


def replace_target(content, target, replacement):
    if target == 'summary':
        content['summary'] = replacement
    else:
        _, job, _, line = target.split('_')
        entry = content['experience'][int(job)]
        lines = entry['bullets'].splitlines(keepends=True)
        old = lines[int(line)]
        ending = old[len(old.rstrip('\r\n')):]
        lines[int(line)] = replacement + ending
        entry['bullets'] = ''.join(lines)


def review_edits(analysis):
    edits = analysis.result_data.get('resume_edits', [])
    validate_edit_shape(edits)
    targets = editable_targets(analysis.builder_snapshot)
    counts = Counter(edit['target_id'] for edit in edits)
    rows = []
    for edit in edits:
        target = edit['target_id']
        problem = ''
        if target not in targets:
            problem = 'This target is not part of the analyzed builder resume.'
        elif counts[target] != 1:
            problem = 'Multiple suggestions target this field.'
        elif targets[target] != edit['original']:
            problem = 'Original text does not exactly match the analyzed resume.'
        elif edit['original'] == edit['replacement']:
            problem = 'This suggestion makes no change.'
        elif target != 'summary' and edit['replacement'].splitlines() != [edit['replacement']]:
            problem = 'A bullet replacement must remain one line.'
        else:
            candidate = copy.deepcopy(analysis.builder_snapshot['content'])
            replace_target(candidate, target, edit['replacement'])
            try:
                validate_content(candidate)
            except ValidationError as exc:
                problem = ' '.join(exc.messages)
        rows.append({**edit, 'problem': problem})
    return rows


def plan_token(analysis):
    raw = json.dumps({'snapshot': analysis.builder_snapshot, 'result': analysis.ai_response_json}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def apply_edits(analysis, selected):
    rows = {row['target_id']: row for row in review_edits(analysis)}
    if not selected or len(selected) != len(set(selected)) or any(target not in rows or rows[target]['problem'] for target in selected):
        raise ValidationError('Select valid suggestions from the review page.')
    content = copy.deepcopy(analysis.builder_snapshot['content'])
    for target in selected:
        replace_target(content, target, rows[target]['replacement'])
    validate_content(content)
    return content


def skill_key(value):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def recommended_skills(analysis):
    import re
    import unicodedata
    existing = {
        skill_key(item)
        for group in analysis.builder_snapshot['content']['skills']
        for item in re.split(r'[,;\n•|]', group['items']) if item.strip()
    }
    raw = analysis.result_data.get('recommended_keywords_to_add_naturally', [])
    if not isinstance(raw, list):
        return []
    rows, seen = [], set()
    for index, value in enumerate(raw[:100]):
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            continue
        value = value.strip()
        if any(unicodedata.category(c).startswith('C') or c in '\n\r,;•|' for c in value):
            continue
        key = skill_key(value)
        if key in seen:
            continue
        seen.add(key)
        rows.append({'id': str(index), 'text': value, 'existing': key in existing})
    return rows


def add_recommended_skills(analysis, content, selected, group, confirmed):
    if not selected:
        return content
    options = {row['id']: row for row in recommended_skills(analysis)}
    if len(selected) != len(set(selected)) or any(item not in options or options[item]['existing'] for item in selected):
        raise ValidationError('Select available recommended skills from the review page.')
    if not confirmed:
        raise ValidationError('Confirm that the selected skills reflect your experience.')
    if group == 'new':
        content['skills'].append({'label': 'Additional skills', 'items': ''})
        target = content['skills'][-1]
    elif group in {str(index) for index in range(len(content['skills']))}:
        target = content['skills'][int(group)]
    else:
        raise ValidationError('Choose a valid Skills group.')
    additions = [options[item]['text'] for item in sorted(selected, key=int)]
    target['items'] = ', '.join(([target['items']] if target['items'].strip() else []) + additions)
    validate_content(content)
    return content
