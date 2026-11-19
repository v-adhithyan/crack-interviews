"""Deterministic, loss-aware resume consolidation. No AI or external requests."""
import copy
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from .resume_builder import validate_content, MAX_BODY


def normalized(value):
    value = re.sub(r'^\s*[-*•]\s+', '', value)
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def fingerprint(draft):
    return hashlib.sha256(json.dumps([draft.title, draft.content, draft.revision, draft.template_version, draft.is_base], sort_keys=True).encode()).hexdigest()


def snapshot(draft):
    return {'title': draft.title, 'content': validate_content(draft.content), 'revision': draft.revision,
            'template_version': draft.template_version, 'is_base': draft.is_base, 'fingerprint': fingerprint(draft)}


def similarity(left, right):
    # Ignore name/contact/formatting: these otherwise dominate almost every resume.
    def tokens(content):
        parts = [content['summary']]
        for section in ('skills', 'experience', 'projects', 'education'):
            parts.extend(' '.join(row.values()) for row in content.get(section, []))
        return set(re.findall(r'[\w+#.]+', normalized(' '.join(parts))))
    a, b = tokens(left), tokens(right)
    return len(a & b) / len(a | b) if a | b else 0


def suggest(snapshots):
    bases = {key: value for key, value in snapshots.items() if value['is_base']}
    result = {}
    for key, value in snapshots.items():
        if value['is_base']:
            continue
        scores = sorted(((similarity(value['content'], base['content']), identifier) for identifier, base in bases.items()), reverse=True)
        score, best = scores[0]
        confident = score >= .18 and (len(scores) == 1 or score - scores[1][0] >= .05)
        result[key] = {'base': best if confident else '', 'score': round(score * 100), 'closest': best}
    return result


def metadata(section, row):
    text_field = 'items' if section == 'skills' else 'bullets' if section in ('experience', 'projects') else None
    return {key: value for key, value in row.items() if key != text_field}


def same_metadata(section, left, right):
    return {k: normalized(v) for k, v in metadata(section, left).items()} == {k: normalized(v) for k, v in metadata(section, right).items()}


def fragments(section, row):
    if section == 'skills':
        return [s.strip() for s in re.split(r'[,;\n]', row['items']) if s.strip()]
    return [s.strip() for s in row['bullets'].splitlines() if s.strip()]


def candidate_list(snapshots, assignments):
    candidates, seen = [], {}

    def add(base_id, source_id, operation, label, value, current='', warning=''):
        key = json.dumps([base_id, operation, normalized(value)], sort_keys=True)
        if key in seen:
            if source_id not in seen[key]['sources']:
                seen[key]['sources'].append(source_id)
            return
        if len(candidates) >= 600:
            raise ValidationError('This group has more than 600 suggestions. Prune fewer source resumes in one review.')
        item = {'id': str(len(candidates)), 'base': base_id, 'sources': [source_id], 'operation': operation,
                'label': label, 'value': value, 'current': current, 'warning': warning}
        candidates.append(item); seen[key] = item

    for source_id, base_id in assignments.items():
        if not base_id:
            continue
        source, base = snapshots[source_id]['content'], snapshots[base_id]['content']
        for key, value in source['contact'].items():
            old = base['contact'][key]
            if value and normalized(value) != normalized(old):
                add(base_id, source_id, {'type': 'field', 'path': ['contact', key]}, 'Contact: ' + key,
                    value, old, 'Choose one replacement for this field.' if old else '')
        if source['summary'] and normalized(source['summary']) != normalized(base['summary']):
            add(base_id, source_id, {'type': 'field', 'path': ['summary']}, 'Professional summary', source['summary'],
                base['summary'], 'Alternative summary: choose at most one, rather than appending both.' if base['summary'] else '')
        for section in ('skills', 'experience', 'projects', 'education'):
            for row in source.get(section, []):
                if not any(row.values()):
                    continue
                matches = [r for r in base.get(section, []) if same_metadata(section, r, row)]
                label = section.title() + ': ' + ' · '.join(v for v in metadata(section, row).values() if v)
                if not matches:
                    identity = {'skills': 'label', 'experience': 'company', 'projects': 'name', 'education': 'school'}[section]
                    conflicting = [r for r in base.get(section, []) if normalized(r[identity]) == normalized(row[identity])]
                    add(base_id, source_id, {'type': 'row', 'section': section, 'row': row}, label,
                        '\n'.join(f'{k}: {v}' for k, v in row.items() if v),
                        '\n'.join(json.dumps(r, ensure_ascii=False) for r in conflicting),
                        'Different details for an existing entry (for example dates or role). Accept only if this is a separate entry; otherwise leave it out and resolve manually.' if conflicting else '')
                elif section != 'education':
                    existing = [text for r in matches for text in fragments(section, r)]
                    for text in fragments(section, row):
                        if normalized(text) in {normalized(v) for v in existing}:
                            continue
                        nearest = max(existing, key=lambda v: SequenceMatcher(None, normalized(v), normalized(text)).ratio(), default='')
                        similar = nearest and SequenceMatcher(None, normalized(nearest), normalized(text)).ratio() >= .72
                        add(base_id, source_id, {'type': 'append', 'section': section, 'row': metadata(section, row)}, label,
                            text, nearest if similar else '', 'Similar wording or changed metrics: review both claims before adding.' if similar else '')
    for index, item in enumerate(candidates):
        op = item['operation']
        if op['type'] != 'row':
            continue
        section = op['section']
        identity = {'skills': 'label', 'experience': 'company', 'projects': 'name', 'education': 'school'}[section]
        for other in candidates[:index]:
            other_op = other['operation']
            if (item['base'] == other['base'] and other_op['type'] == 'row' and other_op['section'] == section
                    and normalized(op['row'][identity]) == normalized(other_op['row'][identity])
                    and not same_metadata(section, op['row'], other_op['row'])):
                for entry in (item, other):
                    entry['warning'] = entry['warning'] or 'Conflicting details across source drafts. Accept both only if they are separate entries; otherwise choose one.'
            elif (item['base'] == other['base'] and other_op['type'] == 'row' and other_op['section'] == section
                    and section in ('experience', 'projects') and same_metadata(section, op['row'], other_op['row'])):
                left, right = fragments(section, op['row']), fragments(section, other_op['row'])
                if any(normalized(a) != normalized(b) and SequenceMatcher(None, normalized(a), normalized(b)).ratio() >= .72 for a in left for b in right):
                    for entry in (item, other):
                        entry['warning'] = entry['warning'] or 'Similar bullets with changed wording or metrics in another draft. Review before combining.'

    # Flag competing replacements and similar suggestions across different source drafts too.
    for index, item in enumerate(candidates):
        for other in candidates[:index]:
            if item['base'] == other['base'] and item['operation'] == other['operation']:
                if item['operation']['type'] == 'field' or SequenceMatcher(None, normalized(item['value']), normalized(other['value'])).ratio() >= .72:
                    item['warning'] = item['warning'] or 'Alternative or similar suggestion from another draft. Review before adding both.'
                    other['warning'] = other['warning'] or 'Alternative or similar suggestion from another draft. Review before adding both.'
    return candidates


def consolidate(plan, selected):
    allowed = {item['id'] for item in plan.candidates}
    if not set(selected) <= allowed:
        raise ValidationError('Unknown suggestion. Restart the review.')
    base_ids = sorted(set(plan.assignments.values()) - {''})
    contents = {key: copy.deepcopy(plan.snapshots[key]['content']) for key in base_ids}
    replacements = set()
    for item in plan.candidates:
        if item['id'] not in selected:
            continue
        content, op = contents[item['base']], item['operation']
        if op['type'] == 'field':
            key = (item['base'], tuple(op['path']))
            if key in replacements:
                raise ValidationError('Choose only one replacement for each contact field or summary.')
            replacements.add(key)
            if len(op['path']) == 1:
                content[op['path'][0]] = item['value']
            else:
                content[op['path'][0]][op['path'][1]] = item['value']
        else:
            section = op['section']
            rows = content.setdefault(section, [])
            match = next((r for r in rows if same_metadata(section, r, op['row'])), None)
            if op['type'] == 'row' and match is None:
                rows.append(copy.deepcopy(op['row']))
            elif section != 'education':
                if match is None:
                    raise ValidationError('An entry is missing. Restart the review.')
                incoming = fragments(section, op['row']) if op['type'] == 'row' else [item['value']]
                text_field = 'items' if section == 'skills' else 'bullets'
                values = fragments(section, match)
                for value in incoming:
                    if normalized(value) not in {normalized(v) for v in values}:
                        values.append(value)
                match[text_field] = (', ' if section == 'skills' else '\n').join(values)
    outputs = [{'base': key, 'title': (plan.snapshots[key]['title'][:105] + ' (consolidated)')[:120],
             'template_version': plan.snapshots[key]['template_version'], 'content': validate_content(value)} for key, value in contents.items()]

    for output in outputs:
        payload = {'title': output['title'], 'content': output['content'], 'revision': 1}
        if len(json.dumps(payload).encode()) > MAX_BODY:
            raise ValidationError('A consolidated resume would exceed the editor size limit. Select fewer additions.')
    return outputs
