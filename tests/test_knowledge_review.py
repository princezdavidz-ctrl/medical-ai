from uuid import uuid4

import pytest

from app.knowledge.review import validate_review_separation


def test_review_and_publication_require_three_distinct_people():
    submitter, reviewer, publisher = uuid4(), uuid4(), uuid4()
    validate_review_separation(
        submitter_id=submitter, reviewer_id=reviewer, publisher_id=publisher
    )


def test_submitter_cannot_review_or_publish():
    user = uuid4()
    with pytest.raises(PermissionError):
        validate_review_separation(submitter_id=user, reviewer_id=user)
    with pytest.raises(PermissionError):
        validate_review_separation(
            submitter_id=user, reviewer_id=uuid4(), publisher_id=user
        )


def test_reviewer_cannot_publish_own_approval():
    with pytest.raises(PermissionError):
        validate_review_separation(
            submitter_id=uuid4(), reviewer_id=(reviewer := uuid4()), publisher_id=reviewer
        )
