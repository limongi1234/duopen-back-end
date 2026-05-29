from unittest.mock import MagicMock


def test_backoff_countdown_exponencial():
    from app.tasks.celery_app import backoff_countdown, RETRY_BACKOFF_MAX

    # 2, 4, 8, 16, ... (base 2, dobrando a cada tentativa)
    assert backoff_countdown(0) == 2
    assert backoff_countdown(1) == 4
    assert backoff_countdown(2) == 8
    assert backoff_countdown(3) == 16
    # respeita o teto máximo
    assert backoff_countdown(100) == RETRY_BACKOFF_MAX


def test_run_ml_analysis_success():
    from app.tasks.ml_tasks import run_ml_analysis

    # Celery com bind=True injeta self automaticamente; chamar sem mock_self
    result = run_ml_analysis("obra-123")

    assert result == {"obra_id": "obra-123", "status": "completed"}


def test_run_ml_retraining_success():
    from app.tasks.ml_tasks import run_ml_retraining

    result = run_ml_retraining()

    assert result == {"status": "completed"}


def test_run_ml_analysis_retries_on_error():
    import app.tasks.ml_tasks as ml_module
    from app.tasks.ml_tasks import run_ml_analysis

    mock_log = MagicMock()
    mock_log.info.side_effect = RuntimeError("forced error")
    original_log = ml_module.log
    ml_module.log = mock_log

    try:
        run_ml_analysis("obra-123")
    except Exception:
        pass  # Celery levanta Retry quando não há worker
    finally:
        ml_module.log = original_log

    mock_log.error.assert_called_once()


def test_generate_embeddings_success():
    from app.tasks.embedding_tasks import generate_embeddings

    result = generate_embeddings("doc-456", "conteúdo do documento")

    assert result == {"documento_id": "doc-456", "status": "completed"}


def test_generate_embeddings_retries_on_error():
    import app.tasks.embedding_tasks as emb_module
    from app.tasks.embedding_tasks import generate_embeddings

    mock_log = MagicMock()
    mock_log.info.side_effect = RuntimeError("forced error")
    original_log = emb_module.log
    emb_module.log = mock_log

    try:
        generate_embeddings("doc-456", "texto")
    except Exception:
        pass
    finally:
        emb_module.log = original_log

    mock_log.error.assert_called_once()
