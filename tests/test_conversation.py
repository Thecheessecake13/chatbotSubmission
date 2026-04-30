import uuid
from types import SimpleNamespace

from app.models import Document, DocumentStatus, Message, MessageRole
from app.services import conversation as conversation_service


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, history=None):
        self.history = history or []
        self.added = []
        self.commits = 0

    def get(self, model, object_id):
        return None

    def scalars(self, statement):
        return _ScalarResult(self.history)

    def add(self, item):
        if getattr(item, 'id', None) is None:
            item.id = uuid.uuid4()
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if getattr(item, 'id', None) is None:
                item.id = uuid.uuid4()

    def commit(self):
        self.commits += 1


def _message(role: MessageRole, content: str) -> Message:
    return Message(id=uuid.uuid4(), conversation_id=uuid.uuid4(), role=role, content=content)


def test_retrieval_query_includes_recent_conversation_context():
    history = [
        _message(MessageRole.user, 'How many vacation days do full-time employees receive?'),
        _message(MessageRole.assistant, 'Full-time employees receive 20 paid vacation days per year [source 1].'),
    ]

    query = conversation_service.build_retrieval_query('Does any of it carry over?', history)

    assert 'vacation days' in query
    assert 'Does any of it carry over?' in query


def test_ask_returns_grounded_no_answer_without_calling_llm(monkeypatch):
    document = Document(
        id=uuid.uuid4(),
        filename='policy.pdf',
        content_type='application/pdf',
        storage_path='/tmp/policy.pdf',
        status=DocumentStatus.ready,
    )
    db = _FakeDb()
    captured = {}

    def fake_search(db_arg, document_id, query, top_k, min_score):
        captured.update({'query': query, 'top_k': top_k, 'min_score': min_score})
        return []

    def fail_answer_question(question, hits, history):
        raise AssertionError('LLM should not be called when retrieval has no confident context')

    monkeypatch.setattr(conversation_service, 'search', fake_search)
    monkeypatch.setattr(conversation_service, 'answer_question', fail_answer_question)
    monkeypatch.setattr(conversation_service, 'get_settings', lambda: SimpleNamespace(top_k=5, min_retrieval_score=0.42))

    response = conversation_service.ask_document(db, document, 'What is the renewal date?', None, None)

    assert response.answer == 'The document does not provide enough information to answer that question.'
    assert response.citations == []
    assert captured['min_score'] == 0.42
    assert captured['top_k'] == 5
    assert db.commits == 1
