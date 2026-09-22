from copy import deepcopy
from datetime import date, timedelta
import json
import pytest
from risk_decision.wizard_core.policy import load_policy
from risk_decision.wizard_core.wizard import initial_payload
from risk_decision.wizard_core.lifecycle import add_action, complete_action, review_case, revise, register_row
from risk_decision.wizard_core.intake import Extraction, validate_extraction, apply_confirmed, extract_local
from risk_decision.wizard_core.storage import init_case_paths, write_draft, read_draft, LockedVersionError


def case():
    p = initial_payload(load_policy())
    p['evaluation_snapshot'] = {'created_at': '2020-01-01T00:00:00+00:00', 'risk_category': 'high'}
    p['decision'] = {'decided_at': '2020-01-01', 'review_date': '2020-01-02'}
    return p


def test_completion_needs_evidence_and_does_not_change_score():
    p = case(); before = deepcopy(p['evaluation_snapshot'])
    a = add_action(p, 'Confirm delivery', 'Sam', '2020-01-01')
    with pytest.raises(ValueError): complete_action(p, a['id'], '', 'Sam')
    complete_action(p, a['id'], 'Written confirmation', 'Sam')
    assert p['evaluation_snapshot'] == before
    with pytest.raises(ValueError, match='new assessment'):
        review_case(p, 'Hoda', 'Delivery confirmed', 'not_observed', True)


def test_reassessment_preserves_history_and_allows_closure():
    p = case(); a = add_action(p, 'Confirm', 'Sam', '2020-01-01')
    complete_action(p, a['id'], 'Confirmation', 'Sam')
    q = revise(p)
    assert p['version'] == 1 and q['version'] == 2
    assert q['evaluation_snapshot'] is None
    q['evaluation_snapshot'] = {'created_at': '2099-01-01T00:00:00+00:00', 'risk_category': 'low'}
    q['decision'] = {'decided_at': '2099-01-01'}
    review_case(q, 'Hoda', 'Delivery received', 'not_observed', True)
    assert register_row(q)['status'] == 'closed'
    assert not register_row(q)['review_due']
    assert revise(q)['lifecycle']['status'] == 'open'


def test_register_tracks_overdue_and_missing_human_decision():
    p = case(); p['decision'] = {}
    add_action(p, 'Call', 'Sam', '2020-01-01')
    r = register_row(p)
    assert r['overdue_actions'] == 1 and r['awaiting_decision']


def test_closure_guards():
    p = case()
    with pytest.raises(ValueError): review_case(p, 'Hoda', 'Unknown', 'unknown', True)
    add_action(p, 'Call', 'Sam', '2020-01-01')
    with pytest.raises(ValueError): review_case(p, 'Hoda', 'Observed', 'occurred', True)
    review_case(p, 'Hoda', 'Awaiting reply', 'unknown', False, date.today()+timedelta(days=1))
    assert len(p['lifecycle']['reviews']) == 1


def test_grounding_and_no_score_fields():
    with pytest.raises(ValueError):
        validate_extraction('Supplier late.', {'event': {'text':'Late', 'quote':'Bankrupt'}})
    with pytest.raises(ValueError): validate_extraction('Supplier late.', {'probability': .9})
    e = validate_extraction('Supplier late.', {'event': {'text':'Late delivery', 'quote':'Supplier late.'}})
    p = initial_payload(load_policy())
    q = apply_confirmed(p, 'Supplier late.', e, {'event':'Late delivery'}, 'Hoda')
    assert q['likelihood'] == p['likelihood'] and q['impact'] == p['impact']
    assert p['definition']['event'] == '' and q['definition']['event'] == 'Late delivery'


def test_locked_inputs_cannot_be_unlocked_in_place(tmp_path):
    paths = init_case_paths(str(tmp_path)); p = case()
    p['wizard']['locked_at_end'] = True
    write_draft(paths, p['case_id'], 1, p)
    q = deepcopy(p); q['wizard']['locked_at_end'] = False
    with pytest.raises(LockedVersionError): write_draft(paths, p['case_id'], 1, q)
    q = revise(p); write_draft(paths, q['case_id'], 2, q)
    assert read_draft(paths, p['case_id'], 1)['wizard']['locked_at_end']


def test_ollama_adapter_contract(monkeypatch):
    class Result:
        stdout = json.dumps({'event': {'text':'Late', 'quote':'Late'}})
    def fake(args, **kwargs):
        assert args == ['ollama', 'run', 'local-model']
        assert kwargs['timeout'] == 90
        return Result()
    monkeypatch.setattr('subprocess.run', fake)
    assert extract_local('Late', 'local-model').event.text == 'Late'
    with pytest.raises(ValueError): extract_local('Late', '--help')
